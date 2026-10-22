#!/usr/bin/env python3
"""Score presentism logs against the Tweede Kamer 1890-1899 holdout (kamer/PRESENTISM_EVAL.md).

Inputs: utterance logs written by scripts/run_presentism.py (*.jsonl) and,
optionally, the interview rows saved in runs/kamer/s1_llm.json (seed 7 of the
backbone check). Only LLM text is scored (source api/cache); heuristic
fallbacks and archival excerpts are counted separately as coverage.

  PYTHONPATH=. python3 scripts/eval_presentism.py --logs runs/presentism/replay_backbone \
      --s1-llm runs/kamer/s1_llm.json
"""

from __future__ import annotations

import argparse
import collections
import json
import time
from pathlib import Path

from kamer.eval import presentism as P

LLM_SOURCES = {"api", "cache", "s1_llm.json"}
UNITS = {
    "record": lambda r: r["kind"] == "floor" and r.get("on_record"),
    "floor": lambda r: r["kind"] in {"floor", "committee"},
    "dialogue": lambda r: r["kind"] in {"dialogue", "solo_talk"},
    "interview": lambda r: r["kind"] == "interview",
}
PRESET_TO_CONDITION = {"full": "kamer_noguard", "ga": "ga"}
ORDER = ["ga", "ga_periodprompt", "kamer_noguard", "kamer_full"]
BINARY = {
    "modern_vocab": lambda f: bool(f["vocab_hits"]),
    "modern_vocab_audit_half": lambda f: bool(f["vocab_audit"]),
    "register_adversarial": lambda f: f["register"]["adversarial"],
    "register_consensus": lambda f: f["register"]["consensus"],
}


def load_logs(dirs: list[Path]) -> tuple[list[dict], list[dict]]:
    recs, summaries = [], []
    for d in dirs:
        for path in sorted(d.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    recs.append(json.loads(line))
        for path in sorted(d.glob("*.summary.json")):
            summaries.append(json.loads(path.read_text(encoding="utf-8")))
    return recs, summaries


def load_s1_interviews(path: Path) -> list[dict]:
    """Interview rows of the gpt-4o-mini backbone check (only seeds run with interviews)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for run in data.get("runs", []):
        cond = PRESET_TO_CONDITION.get(run.get("preset"), run.get("preset"))
        for row in run.get("interviews", {}).get("rows", []):
            for cat, answers in row.get("answers", {}).items():
                for ans in answers:
                    if not ans or ans.startswith("Answer in first person"):  # API-failure echo
                        continue
                    out.append({
                        "condition": cond, "seed": run["seed"], "backend": "s1_llm.json",
                        "agent": row["id"], "name": row["name"], "status": row["status"], "house": "commons",
                        "kind": "interview", "question_cat": cat, "source": "s1_llm.json",
                        "raw": ans, "text": ans, "on_record": False,
                    })
    return out


def holdout_reference(cache: Path) -> tuple[dict, set[str], dict]:
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        return data["aggregate"], set(data["attested"]), data
    t0 = time.time()
    rows = P.holdout_texts()
    att_path = cache.parent / "attested.json"
    if att_path.exists():
        att_data = json.loads(att_path.read_text(encoding="utf-8"))
        attested, df = set(att_data["attested"]), att_data["doc_freq"]
    else:
        attested, df = P.attested_terms(r["text"] for r in rows)
        att_path.parent.mkdir(parents=True, exist_ok=True)
        att_path.write_text(json.dumps({"attested": sorted(attested), "doc_freq": df, "n_holdout": len(rows)},
                                       indent=2), encoding="utf-8")
    feats = [P.text_features(P.window(r["text"]), attested) for r in rows]
    agg = P.aggregate(feats)
    by_role = {role: P.aggregate([f for f, r in zip(feats, rows) if r["role"] == role])
               for role in ("mp", "government")}
    data = {
        "aggregate": agg, "by_role": by_role, "attested": sorted(attested), "doc_freq": df,
        "n_speeches": len(rows), "window_chars": P.WINDOW, "seconds": round(time.time() - t0, 1),
        "note": "TK 1890-1899, MP + government speeches >= 80 chars, persona-excerpt sittings excluded, "
                "first 480 characters (the simulated floor-utterance length)",
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return agg, attested, data


def self_desc(recs: list[dict]) -> dict:
    errs = collections.Counter()
    n_bad = 0
    examples = []
    for r in recs:
        e = P.self_description_errors(r["text"], r.get("status", ""), r.get("house", "commons"))
        if e:
            n_bad += 1
            errs.update(e)
            if len(examples) < 6:
                examples.append({"status": r.get("status"), "errors": e, "text": r["text"][:240]})
    n = len(recs)
    sg = sum(1 for r in recs if P.sg_as_chamber(r["text"]))
    return {"n": n, "error_rate": n_bad / n if n else None, "ci95": P.wilson(n_bad, n),
            "codes": dict(errs.most_common()), "examples": examples,
            "sg_as_chamber_rate": sg / n if n else None}


def score_group(recs: list[dict], attested: set[str], field: str) -> dict:
    feats = [P.text_features(r[field], attested) for r in recs]
    agg = P.aggregate(feats)
    by_seed: dict[int, list[dict]] = collections.defaultdict(list)
    for f, r in zip(feats, recs):
        by_seed[r.get("seed", 0)].append(f)
    agg["per_seed"] = {
        str(s): {k: P.aggregate(fs).get(k) for k in ("n", "modern_vocab", "modern_spelling_share",
                                                     "modern_vocative_share", "register_adversarial",
                                                     "register_consensus")}
        for s, fs in sorted(by_seed.items())
    }
    agg["ci95"] = {
        k: P.bootstrap_ci([[1.0 if fn(f) else 0.0 for f in fs] for fs in by_seed.values()])
        for k, fn in BINARY.items()
    }
    flagged = [(f, r) for f, r in zip(feats, recs) if f["vocab_hits"]]
    agg["examples_modern"] = [{"hits": f["vocab_hits"], "text": r[field][:260]} for f, r in flagged[:5]]
    return agg


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}"


def ci(c) -> str:
    return "" if not c else f" [{100 * c[0]:.0f}–{100 * c[1]:.0f}]"


def markdown(result: dict) -> str:
    hold = result["holdout"]
    cols = ("distinct completions", "modern vocab %", "audit-half %", "modern spelling %", "modern vocative %",
            "adversarial %", "consensus %")
    out = [f"# Presentism audit — {result['label']}", "",
           f"Holdout: {result['holdout_meta']['n_speeches']} TK speeches 1890–1899 "
           f"(first {result['holdout_meta']['window_chars']} chars). "
           f"Lexicon terms attested in the holdout and not counted: {', '.join(result['attested']) or 'none'}.",
           ""]

    def row(name: str, a: dict, floor: bool = True) -> str:
        c = a.get("ci95", {})
        return "| " + " | ".join([
            name, str(a.get("n", 0)),
            pct(a.get("modern_vocab")) + ci(c.get("modern_vocab")),
            pct(a.get("modern_vocab_audit_half")) + ci(c.get("modern_vocab_audit_half")),
            pct(a.get("modern_spelling_share")),
            pct(a.get("modern_vocative_share")) if floor else "–",
            pct(a.get("register_adversarial")) + ci(c.get("register_adversarial")),
            pct(a.get("register_consensus")) + ci(c.get("register_consensus")),
        ]) + " |"

    for unit in ("record", "floor", "dialogue", "interview"):
        block = [(c, result["conditions"][c][unit]) for c in result["order"] if unit in result["conditions"][c]]
        block = [(c, u) for c, u in block if u["pre"].get("n")]
        if not block:
            continue
        out += [f"## {unit}", "", "| condition | " + " | ".join(cols) + " |",
                "|" + "---|" * (len(cols) + 1)]
        if unit in {"record", "floor"}:
            out.append(row("Handelingen 1890–1899", hold))
        floor = unit in {"record", "floor"}
        for c, u in block:
            name = f"{c} (pre-filter)" if u.get("filtered") else c
            out.append(row(f"{name} · {u['n_turns']} turns", u["pre"], floor))
            if u.get("filtered"):
                out.append(row(f"{c} (post-filter)", u["post"], floor))
        out.append("")
    out += ["## self-description errors (interviews)", "",
            "| condition | self-knowledge answers | error % | all answers | error % | S-G as chamber % | top codes |",
            "|---|---|---|---|---|---|---|"]
    for c in result["order"]:
        sd = result["conditions"][c].get("self_desc")
        if not sd:
            continue
        top = ", ".join(f"{k}×{v}" for k, v in list(sd["all"]["codes"].items())[:4])
        out.append(f"| {c} | {sd['self_knowledge']['n']} | {pct(sd['self_knowledge']['error_rate'])}"
                   f"{ci(sd['self_knowledge']['ci95'])} | {sd['all']['n']} | {pct(sd['all']['error_rate'])} | "
                   f"{pct(sd['all']['sg_as_chamber_rate'])} | {top} |")
    out += ["", "## coverage (LLM vs heuristic lines in the simulated Handelingen)", "",
            "| condition | seed | record lines | LLM | fallback | completions requested |", "|---|---|---|---|---|---|"]
    for s in result["coverage"]:
        out.append(f"| {s['condition']} | {s['seed']} | {s.get('n_record_lines')} | {s.get('n_record_llm')} | "
                   f"{s.get('n_record_fallback')} | {s.get('completions_requested')} |")
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--logs", action="append", default=[], help="directory of run_presentism.py logs")
    p.add_argument("--s1-llm", default="", help="runs/kamer/s1_llm.json (adds its interview rows)")
    p.add_argument("--holdout-cache", default="runs/presentism/holdout_features.json")
    p.add_argument("--out", default="")
    p.add_argument("--label", default="")
    args = p.parse_args()

    dirs = [Path(d) for d in args.logs]
    recs, summaries = load_logs(dirs)
    if args.s1_llm:
        # a replay of the backbone check re-creates the same interviews from the cache: count once
        have = {(r["condition"], r["seed"]) for r in recs if r["kind"] == "interview" and r.get("source") == "cache"}
        recs += [r for r in load_s1_interviews(Path(args.s1_llm)) if (r["condition"], r["seed"]) not in have]
    hold, attested, hold_meta = holdout_reference(Path(args.holdout_cache))

    llm = [r for r in recs if r.get("source") in LLM_SOURCES and (r.get("raw") or r.get("text"))]
    conds = sorted({r["condition"] for r in llm}, key=lambda c: (ORDER.index(c) if c in ORDER else 99, c))
    result = {
        "label": args.label or ", ".join(str(d) for d in dirs) or args.s1_llm,
        "holdout": hold,
        "holdout_meta": {k: hold_meta[k] for k in ("n_speeches", "window_chars", "note")},
        "holdout_by_role": hold_meta.get("by_role"),
        "attested": sorted(attested),
        "lexicon": P.lexicon_table(),
        "order": conds,
        "conditions": {},
        "coverage": sorted(summaries, key=lambda s: (s["condition"], s["seed"])),
        "n_records": len(recs),
        "n_llm_records": len(llm),
        "sources": dict(collections.Counter(r.get("source") for r in recs)),
    }
    for c in conds:
        cr = [r for r in llm if r["condition"] == c]
        block = {}
        for unit, sel in UNITS.items():
            ur_all = [r for r in cr if sel(r)]
            if not ur_all:
                continue
            # Unit of analysis: distinct completions. A cache hit repeated across steps
            # (identical prompt, identical text) is one sample of the model, not many.
            seen, ur = set(), []
            for r in ur_all:
                key = (r.get("seed"), r.get("agent") if unit == "interview" else "", r["raw"])
                if key not in seen:
                    seen.add(key)
                    ur.append(r)
            filtered = any(r.get("n_regen") or r.get("filter_raw") for r in ur) and c == "kamer_full"
            block[unit] = {
                "n_turns": len(ur_all),
                "n_unique": len(ur),
                "filtered": filtered,
                "pre": score_group(ur, attested, "raw"),
                "post": score_group(ur, attested, "text") if filtered else None,
                "filter_fired": sum(1 for r in ur if r.get("filter_raw")),
                "regenerated": sum(1 for r in ur if r.get("n_regen")),
                "residual_after_filter": sum(1 for r in ur if r.get("filter_final")),
                # does Kamer-full just paste its archival context? (shared 8-gram with a retrieved passage)
                "rag_copy_rate": (
                    sum(1 for r in ur if P.copies_passage(r["text"], [h.get("text", "") for h in r["rag"]]))
                    / len(ur) if any(r.get("rag") for r in ur) else None
                ),
            }
        iv = [r for r in cr if r["kind"] == "interview"]
        if iv:
            block["self_desc"] = {
                "self_knowledge": self_desc([r for r in iv if r.get("question_cat") == "self-knowledge"]),
                "all": self_desc(iv),
            }
        result["conditions"][c] = block

    out = Path(args.out) if args.out else (dirs[0] / "eval.json" if dirs else Path("runs/presentism/eval.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    md = markdown(result)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print("wrote", out, "and", out.with_suffix(".md"))


if __name__ == "__main__":
    main()
