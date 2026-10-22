#!/usr/bin/env python3
"""Rewrite S1 LLM interviews into 1899 off-record Dutch (not floor speeches).

  PYTHONPATH=. python scripts/rewrite_kamer_interviews.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from maroon.agents.llm import PERIOD_INTERVIEW_SYSTEM, OpenAICompatBackend

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runs/kamer/s1_llm.json"
OUT = ROOT / "runs/kamer/s1_llm_period.json"

VOCATIVE = re.compile(
    r"^\s*(mijnheer|mynheer|waarde|geachte)\s+(de\s+)?voorzitter\s*[,!]?\s*",
    re.I,
)


def rewrite_one(be: OpenAICompatBackend, row: dict, cat: str, question: str, draft: str) -> str:
    prompt = (
        f"Role: {row.get('status')} named {row.get('name')}.\n"
        f"Interview category: {cat}.\n"
        f"Question: {question}\n"
        f"Draft (modern / floor-style; rewrite):\n{draft}\n\n"
        "Rewrite as an off-record 1899 answer. Keep the factual gist. "
        "Do not open by addressing the Chair."
    )
    text = be.complete(prompt)
    text = VOCATIVE.sub("", text or "").strip()
    return text or draft


def main() -> None:
    from kamer.eval.interview import INTERVIEW_QUESTIONS

    be = OpenAICompatBackend(system=PERIOD_INTERVIEW_SYSTEM)
    if not be.api_key:
        raise SystemExit("No API key (OPENAI_API_KEY / MAROON_API_KEY / OPEN_API_KEY).")
    blob = json.loads(SRC.read_text(encoding="utf-8"))
    n = 0
    voc_before = 0
    voc_after = 0
    for run in blob.get("runs") or []:
        rows = (run.get("interviews") or {}).get("rows") or []
        for row in rows:
            answers = row.get("answers") or {}
            for cat, qs in INTERVIEW_QUESTIONS.items():
                drafts = answers.get(cat) or [""]
                q = qs[0]
                out = []
                for draft in drafts:
                    if VOCATIVE.search(draft or ""):
                        voc_before += 1
                    text = rewrite_one(be, row, cat, q, draft)
                    if VOCATIVE.search(text):
                        voc_after += 1
                        text = VOCATIVE.sub("", text).strip()
                    out.append(text)
                    n += 1
                    if n % 25 == 0:
                        print(f"rewritten {n} calls={be.n_calls} cache={be.n_cache} fail={be.n_fail}", flush=True)
                answers[cat] = out
            row["answers"] = answers
    OUT.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT),
                "n": n,
                "vocative_before": voc_before,
                "vocative_after": voc_after,
                "calls": be.n_calls,
                "cache": be.n_cache,
                "fail": be.n_fail,
                "err": be.last_error,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
