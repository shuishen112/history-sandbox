#!/usr/bin/env python3
"""S1 with an OpenAI-compatible LLM backbone.

Requires OPENAI_API_KEY or MAROON_API_KEY. Optional:
  MAROON_MODEL (default gpt-4o-mini)
  MAROON_BASE_URL / OPENAI_BASE_URL

  PYTHONPATH=. python scripts/run_kamer_llm_s1.py --seeds 7 --presets full,ga
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from kamer.config import SimConfig
from kamer.eval.emergence import daily_curve, floor_mention_rate
from kamer.eval.fidelity import anachronism_rate, sim_role_mix
from kamer.eval.interview import run_interviews
from kamer.sim.engine import Simulation
from maroon.agents.llm import OpenAICompatBackend


def probe(model: str, base_url: str) -> OpenAICompatBackend:
    be = OpenAICompatBackend(model=model, base_url=base_url)
    if not be.api_key:
        sys.exit(
            "No API key. Export OPENAI_API_KEY, MAROON_API_KEY, or OPEN_API_KEY "
            "(and optionally MAROON_BASE_URL, MAROON_MODEL)."
        )
    # Do not use KAMER_SYSTEM here: it forces 1899 Dutch and the model then
    # refuses a one-word ping. Heuristic fallback echoes the last prompt line.
    old = be.system
    be.system = "Connectivity check. Reply with exactly the token pong."
    prompt = "Say pong."
    try:
        text = be.complete(prompt)
    finally:
        be.system = old
    echoed = (not text) or text.strip() == prompt or prompt.lower() in text.lower()
    if be.n_fail or echoed:
        sys.exit(f"API probe failed: {be.last_error or text!r}")
    print(f"probe ok model={be.model} base={be.base_url} reply={text[:80]!r}", flush=True)
    return be


def handelingen_lines(sim: Simulation) -> list[dict]:
    lines: list[dict] = []
    for page in sim.press.pages:
        lines.extend(page.lines)
    return lines


def run_one(
    seed: int,
    n: int,
    days: int,
    preset: str,
    model: str,
    base_url: str,
    do_interviews: bool = True,
) -> dict:
    cfg = SimConfig(
        seed=seed,
        n_agents=n,
        n_days=days,
        llm="openai",
        llm_model=model,
        llm_base_url=base_url,
    ).apply_preset(preset)
    print(f"run seed={seed} preset={preset} days={days}…", flush=True)
    sim = Simulation(cfg)
    seed_id = sim.seed_leak()
    sim.run_days(days)
    curve = daily_curve(sim)
    interviews = run_interviews(sim, n) if do_interviews else {"n": 0, "mean_procedural": 0.0, "rows": []}
    lines = handelingen_lines(sim)
    mix = sim_role_mix(lines)
    be = sim.backend
    last = curve[-1]["aware"] if curve else {}
    return {
        "seed": seed,
        "preset": preset,
        "backend": getattr(be, "name", ""),
        "model": getattr(be, "model", ""),
        "llm_calls": getattr(be, "n_calls", 0),
        "llm_cache": getattr(be, "n_cache", 0),
        "llm_fail": getattr(be, "n_fail", 0),
        "utter_cap": getattr(be, "utter_cap", 0),
        "last_error": getattr(be, "last_error", ""),
        "seed_agent": seed_id,
        "final_aware": last,
        "member_end": last.get("member", 0.0),
        "press_end": last.get("press", 0.0),
        "government_end": last.get("government", 0.0),
        "floor_mention": floor_mention_rate(sim),
        "embellishment": sim.world.rumours.embellishment_rate(),
        "mean_procedural": interviews["mean_procedural"],
        "n_lines": len(lines),
        "journalist_share": mix["journalist_share"],
        "anachronism": anachronism_rate(ln.get("text") or "" for ln in lines),
        "n_refusals": sum(1 for a in sim.agents.values() if a.last_refusal),
        "curve": [{"day": c["day"], "aware": c["aware"], "handelingen": c["n_handelingen_lines"]} for c in curve],
        "interviews": interviews,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--seeds", type=str, default="7")
    p.add_argument("--presets", type=str, default="full,ga")
    p.add_argument("--model", type=str, default=os.environ.get("MAROON_MODEL", "gpt-4o-mini"))
    p.add_argument("--base-url", type=str, default=os.environ.get("MAROON_BASE_URL", ""))
    p.add_argument("--out", type=str, default="runs/kamer/s1_llm.json")
    p.add_argument("--skip-probe", action="store_true")
    p.add_argument("--skip-interviews", action="store_true")
    args = p.parse_args()
    if not args.skip_probe:
        probe(args.model, args.base_url)
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    presets = [x.strip() for x in args.presets.split(",") if x.strip()]
    runs = []
    for s in seeds:
        for pr in presets:
            rec = run_one(
                s, args.n, args.days, pr, args.model, args.base_url,
                do_interviews=not args.skip_interviews,
            )
            slim = {k: rec[k] for k in rec if k not in {"interviews", "curve"}}
            print(json.dumps(slim, ensure_ascii=False), flush=True)
            runs.append(rec)
    summary = {
        "model": args.model,
        "n_runs": len(runs),
        "by_preset": {},
        "runs": runs,
    }
    for pr in presets:
        chunk = [r for r in runs if r["preset"] == pr]
        if not chunk:
            continue
        summary["by_preset"][pr] = {
            "member_end": sum(r["member_end"] for r in chunk) / len(chunk),
            "press_end": sum(r["press_end"] for r in chunk) / len(chunk),
            "floor_mention": sum(r["floor_mention"] for r in chunk) / len(chunk),
            "journalist_share": sum(r["journalist_share"] for r in chunk) / len(chunk),
            "mean_procedural": sum(r["mean_procedural"] for r in chunk) / len(chunk),
            "anachronism": sum(r["anachronism"] for r in chunk) / len(chunk),
            "n_lines": sum(r["n_lines"] for r in chunk) / len(chunk),
            "llm_calls": sum(r["llm_calls"] for r in chunk),
            "llm_fail": sum(r["llm_fail"] for r in chunk),
        }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"out": str(out), **{k: v for k, v in summary.items() if k != "runs"}}, indent=2))


if __name__ == "__main__":
    main()
