#!/usr/bin/env python3
"""Presentism runs: GA vs Kamer without guards vs Kamer with guards (kamer/PRESENTISM_EVAL.md).

Every completion is logged with its pre-filter text, so the anachronism audit
can be computed BEFORE the filter fires. Three backends:

  count   offline. Counts the completions a live run would request, by kind.
  replay  offline. Re-runs a condition against an existing LLM cache
          (default runs/kamer/llm_cache.jsonl, read only) and keeps only cache
          hits; misses fall back to the heuristic text exactly as the original
          run did after its 400-completion cap.
  live    PAID. gpt-4o-mini via the OpenAI-compatible API. Requires --live and
          --max-completions; aborts when the budget is reached. New completions
          go to a separate cache file; the backbone cache is only read.

Examples (from the repo root):
  PYTHONPATH=. python3 scripts/run_presentism.py --backend count
  PYTHONPATH=. python3 scripts/run_presentism.py --backend replay --conditions ga,kamer_noguard \
      --debate-context off --kinds all --tag replay_backbone
  PYTHONPATH=. python3 scripts/run_presentism.py --backend live --live --max-completions 40000
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

from kamer.agents.period_guard import ArchivalRAG, regeneration_note, surface_hits
from kamer.config import SimConfig
from kamer.eval import presentism as P
from kamer.eval.interview import INTERVIEW_QUESTIONS, procedural_score
from kamer.sim.engine import Simulation
from maroon.agents.llm import GA_SYSTEM, KAMER_SYSTEM, PERIOD_INTERVIEW_SYSTEM, OpenAICompatBackend

CONDITIONS = {
    # Smallville-style ablation, as in the backbone check (GA_SYSTEM prompt)
    "ga": {"preset": "ga", "system": GA_SYSTEM, "rag": False, "filter": False},
    # exactly the backbone-check `full` condition: world rules on, guards off
    "kamer_noguard": {"preset": "full", "system": KAMER_SYSTEM, "rag": False, "filter": False},
    # world rules + archival RAG + anachronism filter (paper, "Period-faithfulness guards")
    "kamer_full": {"preset": "full", "system": KAMER_SYSTEM, "rag": True, "filter": True},
    # optional control: GA world with the Kamer period prompt (prompt vs world)
    "ga_periodprompt": {"preset": "ga", "system": KAMER_SYSTEM, "rag": False, "filter": False},
}
ALL_KINDS = ("floor", "committee", "dialogue", "solo_talk", "interview")
# solo_talk (Agent.step "talk" with no partner) only sets the UI bubble: no memory, no record.
DEFAULT_KINDS = ("floor", "committee", "dialogue", "interview")
INSTRUCTION_MARKERS = ("Write one floor utterance", "One spoken aside", "Answer in first person")
BACKBONE_CACHE = Path("runs/kamer/llm_cache.jsonl")


class BudgetExceeded(RuntimeError):
    pass


class OfflineBackend(OpenAICompatBackend):
    """Never touches the network. replay: cache hits only. count: always ''."""

    def __init__(self, model: str, system: str, mode: str, caches: list[Path]) -> None:
        super().__init__(model=model, base_url="http://127.0.0.1:9", api_key="offline", system=system,
                         cache_path="/nonexistent/presentism-offline.jsonl")
        self.mode = mode
        self.utter_cap = 0
        for path in caches:
            _preload(self, path)

    def complete(self, prompt: str) -> str:
        key = self._key(prompt)
        if key in self._cache:
            self.n_cache += 1
            return self._cache[key] if self.mode == "replay" else ""
        return ""

    def _remember(self, key: str, text: str) -> None:  # pragma: no cover - never called
        raise RuntimeError("offline backend must not write caches")


def _preload(backend: OpenAICompatBackend, path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            backend._cache.setdefault(rec["k"], rec["v"])


class PresentismBackend:
    """Proxy installed as every agent's backend: guards + per-completion log."""

    name = "openai_compat"

    def __init__(self, inner, sim, cond: dict, args, attested: set[str], rag: ArchivalRAG | None, meta: dict):
        self.inner = inner
        self.sim = sim
        self.cond = cond
        self.args = args
        self.attested = attested
        self.rag = rag if cond["rag"] else None
        self.meta = meta
        self.ctx: dict | None = None
        self.log: list[dict] = []
        self.counts: collections.Counter = collections.Counter()

    # Agent._uses_llm / _llm_budget_left read these
    @property
    def api_key(self) -> str:
        return self.inner.api_key or "offline"

    @property
    def utter_cap(self) -> int:
        return self.inner.utter_cap

    @property
    def n_calls(self) -> int:
        return self.inner.n_calls

    def __getattr__(self, item):
        return getattr(self.inner, item)

    # -- one completion through the inner backend, with source tag
    def _call(self, prompt: str) -> tuple[str, str]:
        key = self.inner._key(prompt)
        hit = key in self.inner._cache
        if self.args.backend == "count":
            return "", "count_hit" if hit else "count_miss"
        if hit:
            return self.inner.complete(prompt), "cache"
        if self.args.backend == "replay":
            return "", "miss"
        if self.args.spent + self.inner.n_calls >= self.args.max_completions:
            raise BudgetExceeded(f"--max-completions {self.args.max_completions} reached")
        fails = self.inner.n_fail
        text = self.inner.complete(prompt)
        if self.inner.n_fail > fails:
            return "", "fail"  # OpenAICompatBackend echoes the prompt's last line on failure
        return text, "api"

    def _insert(self, prompt: str, block: str) -> str:
        if not block:
            return prompt
        for marker in INSTRUCTION_MARKERS:
            i = prompt.find(marker)
            if i >= 0:
                return prompt[:i] + block + "\n" + prompt[i:]
        return prompt + "\n" + block

    def _previous_speech(self, agent) -> dict | None:
        page = self.sim.press.current
        if page is None:
            return None
        for line in reversed(page.lines):
            if line.get("speaker") != agent.name:
                return line
        return None

    def complete(self, prompt: str) -> str:
        ctx = self.ctx or {"kind": "other"}
        kind = ctx["kind"]
        agent = ctx.get("agent")
        if kind not in self.args.kinds:
            self.counts[(kind, "skipped")] += 1
            return ""
        rec = {
            **self.meta,
            "step": self.sim.world.clock.step,
            "time": self.sim.world.clock.iso(),
            "day": self.sim.world.clock.day_index(),
            "agent": getattr(agent, "id", ""),
            "name": getattr(agent, "name", ""),
            "status": getattr(agent, "status", ""),
            "house": getattr(agent, "house", "commons"),
            "kind": kind,
            "question_cat": ctx.get("question_cat", ""),
            "loc": getattr(agent, "location", ""),
            "on_record": False,
        }
        if kind in {"floor", "committee"} and self.args.debate_context == "on" and agent is not None:
            prev = self._previous_speech(agent)
            if prev:
                rec["prev_speaker"] = prev.get("speaker", "")
                prompt = self._insert(
                    prompt,
                    f'The previous speaker on the floor, {prev.get("speaker")} ({prev.get("role")}), said: '
                    f'"{(prev.get("text") or "")[:300]}"',
                )
        if self.rag is not None:
            hits = self.rag.query(prompt, k=2)
            rec["rag"] = [{"idx": h["idx"], "year": h["year"], "text": h["text"]} for h in hits]
            prompt = self._insert(prompt, self.rag.block(hits))
        raw, source = self._call(prompt)
        rec["source"] = source
        rec["raw"] = raw
        text = raw
        rec["filter_raw"] = surface_hits(raw, self.attested) if raw else []
        rec["n_regen"] = 0
        if self.cond["filter"] and rec["filter_raw"]:
            words = list(rec["filter_raw"])
            for _ in range(self.args.max_regen):
                again, src2 = self._call(prompt + regeneration_note(words))
                rec.setdefault("regen_sources", []).append(src2)
                if not again:
                    break
                rec["n_regen"] += 1
                text = again
                words = surface_hits(text, self.attested)
                if not words:
                    break
        rec["text"] = text
        rec["filter_final"] = surface_hits(text, self.attested) if text else []
        if self.args.log_prompts:
            rec["prompt"] = prompt
        self.counts[(kind, source)] += 1
        self.log.append(rec)
        return text

    def interview(self, agent, question: str, retrieved: str) -> str:
        old = self.inner.system
        self.inner.system = PERIOD_INTERVIEW_SYSTEM
        try:
            return self.complete(
                f"{agent.persona}\nRole: {agent.status}. Location: {agent.location}.\n"
                "This is not a speech. A researcher has paused you and asked a question.\n"
                f"Retrieved memories:\n{retrieved}\nQuestion: {question}\n"
                "Answer in first person from memory only. Do not invent unseen places. "
                "Do not address the Voorzitter."
            )
        finally:
            self.inner.system = old


def _install(sim: Simulation, proxy: PresentismBackend) -> None:
    sim.backend = proxy
    for agent in sim.agents.values():
        agent.backend = proxy
        speech, talk = agent.compose_speech, agent.compose_talk

        def compose_speech(world, _a=agent, _f=speech):
            loc = world.tree.subarea_of(_a.location).id
            proxy.ctx = {"kind": "floor" if world.is_on_record(loc) else "committee", "agent": _a}
            try:
                return _f(world)
            finally:
                proxy.ctx = None

        def compose_talk(world, other=None, _a=agent, _f=talk):
            proxy.ctx = {"kind": "dialogue" if other is not None else "solo_talk", "agent": _a}
            try:
                return _f(world, other)
            finally:
                proxy.ctx = None

        agent.compose_speech = compose_speech
        agent.compose_talk = compose_talk

    record = sim.press.record_speech

    def record_speech(world, agent, text):
        ok = record(world, agent, text)
        if not ok:
            return ok
        step = world.clock.step
        for rec in reversed(proxy.log):
            if rec["step"] != step:
                break
            if rec["agent"] == agent.id and rec["kind"] == "floor" and rec["text"] and rec["text"][:480] == text:
                rec["on_record"] = True
                return ok
        proxy.counts[("floor", "fallback_on_record")] += 1
        proxy.log.append({**proxy.meta, "step": step, "time": world.clock.iso(), "day": world.clock.day_index(),
                          "agent": agent.id, "name": agent.name, "status": agent.status,
                          "house": getattr(agent, "house", "commons"), "kind": "floor", "source": "fallback",
                          "raw": text, "text": text, "on_record": True})
        return ok

    sim.press.record_speech = record_speech


def run_one(cond_name: str, seed: int, args, attested: set[str], rag: ArchivalRAG | None) -> dict:
    cond = CONDITIONS[cond_name]
    cfg = SimConfig(seed=seed, n_agents=args.n, n_days=args.days, llm="heuristic").apply_preset(cond["preset"])
    cfg.enable_archival_rag = cond["rag"]
    cfg.enable_anachronism_filter = cond["filter"]
    sim = Simulation(cfg)
    if args.backend == "live":
        inner = OpenAICompatBackend(model=args.model, base_url=args.base_url, system=cond["system"],
                                    cache_path=str(args.out_cache))
        if not inner.api_key:
            sys.exit("live backend: no OPENAI_API_KEY / MAROON_API_KEY")
        for path in args.read_caches:
            _preload(inner, path)
        inner.utter_cap = args.utter_cap
    else:
        inner = OfflineBackend(args.model, cond["system"], args.backend, args.read_caches)
        inner.utter_cap = args.utter_cap
    meta = {"condition": cond_name, "seed": seed, "backend": args.backend, "model": args.model,
            "debate_context": args.debate_context}
    proxy = PresentismBackend(inner, sim, cond, args, attested, rag, meta)
    _install(sim, proxy)
    t0 = time.time()
    sim.seed_leak()
    sim.run_days(args.days)
    if args.interviews:
        for agent in list(sim.agents.values())[: args.n]:
            for cat, qs in INTERVIEW_QUESTIONS.items():
                for q in qs:
                    # Simulation.interview -> proxy.interview -> proxy.complete
                    proxy.ctx = {"kind": "interview", "agent": agent, "question_cat": cat}
                    ans = sim.interview(agent.id, q)
                    proxy.ctx = None
                    if cat == "institutional_awareness" and proxy.log and proxy.log[-1]["agent"] == agent.id:
                        proxy.log[-1]["proc"] = procedural_score(agent.status, ans or "")
    lines = [ln for page in sim.press.pages for ln in page.lines]
    if sim.press.current:
        lines += sim.press.current.lines
    llm_record = sum(1 for r in proxy.log if r.get("on_record") and r.get("source") in {"api", "cache"})
    summary = {
        **meta,
        "n_record_lines": len(lines),
        "n_record_llm": llm_record,
        "n_record_fallback": sum(1 for r in proxy.log if r.get("source") == "fallback"),
        "counts": {f"{k}:{s}": v for (k, s), v in sorted(proxy.counts.items())},
        "completions_requested": sum(
            v for (k, s), v in proxy.counts.items() if s not in {"skipped", "fallback_on_record"}
        ) + sum(len(r.get("regen_sources", [])) for r in proxy.log),
        "regenerations": sum(r.get("n_regen", 0) for r in proxy.log),
        "api_calls": getattr(inner, "n_calls", 0),
        "api_fail": getattr(inner, "n_fail", 0),
        "seconds": round(time.time() - t0, 1),
    }
    args.spent += getattr(inner, "n_calls", 0)
    out = args.out_dir / f"{cond_name}_s{seed}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for rec in proxy.log:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (args.out_dir / f"{cond_name}_s{seed}.summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def attested_set(path: Path) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8"))["attested"])
    texts = [r["text"] for r in P.holdout_texts()]
    att, df = P.attested_terms(texts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"attested": sorted(att), "doc_freq": df, "n_holdout": len(texts)}, indent=2),
                    encoding="utf-8")
    return att


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["count", "replay", "live"], default="count")
    p.add_argument("--live", action="store_true", help="required with --backend live (paid API)")
    p.add_argument("--max-completions", type=int, default=0, help="hard budget per run (live)")
    p.add_argument("--conditions", default="ga,kamer_noguard,kamer_full")
    p.add_argument("--seeds", default="7,11,19")
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--kinds", default=",".join(DEFAULT_KINDS), help="comma list or 'all'")
    p.add_argument("--debate-context", choices=["on", "off"], default="on")
    p.add_argument("--no-interviews", dest="interviews", action="store_false")
    p.add_argument("--max-regen", type=int, default=1)
    p.add_argument("--utter-cap", type=int, default=0, help="0 = every floor turn uses the LLM")
    p.add_argument("--model", default=os.environ.get("MAROON_MODEL", "gpt-4o-mini"))
    p.add_argument("--base-url", default=os.environ.get("MAROON_BASE_URL", ""))
    p.add_argument("--read-cache", action="append", default=None,
                   help=f"cache(s) to read (default {BACKBONE_CACHE})")
    p.add_argument("--tag", default="")
    p.add_argument("--out-cache", default="runs/presentism/llm_cache.jsonl",
                   help="cache this run writes (use one per process when running in parallel)")
    p.add_argument("--log-prompts", action="store_true")
    p.add_argument("--hash-seed", default="0", help="PYTHONHASHSEED for reproducible bench seating")
    args = p.parse_args()

    if args.hash_seed != "random" and os.environ.get("PYTHONHASHSEED") != args.hash_seed:
        # Seating used to use salted hash(id); Kamer now uses stable_mod. Keep the pin anyway.
        os.execve(sys.executable, [sys.executable, *sys.argv], {**os.environ, "PYTHONHASHSEED": args.hash_seed})
    if args.backend == "live" and not (args.live and args.max_completions > 0):
        sys.exit("--backend live spends API credit: pass --live and --max-completions N")
    args.kinds = set(ALL_KINDS) if args.kinds == "all" else {k.strip() for k in args.kinds.split(",") if k.strip()}
    args.read_caches = [Path(x) for x in (args.read_cache or [str(BACKBONE_CACHE)])]
    tag = args.tag or (time.strftime("live_%Y%m%d") if args.backend == "live" else args.backend)
    args.out_dir = Path("runs/presentism") / tag
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.out_cache = Path(args.out_cache)
    args.spent = 0
    if args.backend == "live":
        args.read_caches = [c for c in args.read_caches if c.resolve() != args.out_cache.resolve()]

    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    for c in conds:
        if c not in CONDITIONS:
            sys.exit(f"unknown condition {c}; choose from {sorted(CONDITIONS)}")
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    attested = attested_set(Path("runs/presentism/attested.json"))
    rag = None
    if any(CONDITIONS[c]["rag"] for c in conds):
        t0 = time.time()
        rag = ArchivalRAG()
        print(f"archival RAG: {len(rag.passages)} passages (TK 1860-1889) in {time.time() - t0:.1f}s", flush=True)
    summaries = [run_one(c, s, args, attested, rag) for c in conds for s in seeds]
    (args.out_dir / "runs.json").write_text(
        json.dumps({"args": {k: (sorted(v) if isinstance(v, set) else str(v)) for k, v in vars(args).items()},
                    "runs": summaries}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("wrote", args.out_dir)


if __name__ == "__main__":
    main()
