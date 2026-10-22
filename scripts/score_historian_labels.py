#!/usr/bin/env python3
"""Aggregate exported historian-lab JSON files into TrueSkill tables.

  PYTHONPATH=. python scripts/score_historian_labels.py exports/*.json
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def update(skill: dict[str, tuple[float, float]], winner: str, loser: str, draw: bool = False) -> None:
    """One TrueSkill pair, default μ=25, σ=25/3, β=25/6, τ=25/300."""
    mu_w, sig_w = skill[winner]
    mu_l, sig_l = skill[loser]
    beta2 = (25 / 6) ** 2
    c2 = 2 * beta2 + sig_w**2 + sig_l**2
    c = math.sqrt(c2)
    t = (mu_w - mu_l) / c
    if draw:
        v = math.sqrt(2 / math.pi) * math.exp(-(t**2) / 2)
        w = v * (v + t * 0.0)
        # draw: use truncated-Gaussian draw update (ε≈0.1)
        eps = 0.1
        denom = math.sqrt(2 * math.pi)
        v = (math.exp(-((t - eps) ** 2) / 2) - math.exp(-((t + eps) ** 2) / 2)) / denom
        w = v**2
    else:
        # cdf/pdf of standard normal
        pdf = math.exp(-(t**2) / 2) / math.sqrt(2 * math.pi)
        cdf = 0.5 * (1 + math.erf(t / math.sqrt(2)))
        v = pdf / max(cdf, 1e-12)
        w = v * (v + t)
    mu_w = mu_w + (sig_w**2 / c) * v
    mu_l = mu_l - (sig_l**2 / c) * v
    sig_w = math.sqrt(max(1e-6, sig_w**2 * (1 - (sig_w**2 / c2) * w)))
    sig_l = math.sqrt(max(1e-6, sig_l**2 * (1 - (sig_l**2 / c2) * w)))
    skill[winner] = (mu_w, sig_w)
    skill[loser] = (mu_l, sig_l)


def main(paths: list[str]) -> None:
    files = [Path(p) for p in paths]
    if not files:
        print("usage: score_historian_labels.py exports/*.json", file=sys.stderr)
        sys.exit(2)
    believ: dict[str, tuple[float, float]] = defaultdict(lambda: (25.0, 25 / 3))
    proc: dict[str, tuple[float, float]] = defaultdict(lambda: (25.0, 25 / 3))
    n_rank = n_catch_ok = n_catch = 0
    n_speakers = n_proc = 0
    for path in files:
        blob = json.loads(path.read_text(encoding="utf-8"))
        interviews = blob.get("interviews") or blob.get("rankings") or {}
        if isinstance(interviews, dict):
            interview_rows = list(interviews.values())
        else:
            interview_rows = interviews
        for row in interview_rows:
            n_rank += 1
            left_h = row.get("left") or row.get("left_hidden") or ""
            right_h = row.get("right") or row.get("right_hidden") or ""
            bel = row.get("bel") or row.get("believability") or ""
            hist = row.get("hist") or row.get("procedure") or ""
            if row.get("catch"):
                n_catch += 1
                if "catch" in str(left_h) and bel in {"R", "right"}:
                    n_catch_ok += 1
                elif "catch" in str(right_h) and bel in {"L", "left"}:
                    n_catch_ok += 1
            mapping = {"L": "left", "R": "right", "left": "left", "right": "right", "tie": "tie"}
            for choice, table in ((mapping.get(bel), believ), (mapping.get(hist), proc)):
                a, b = left_h, right_h
                if not a or not b or str(a).startswith("catch") or str(b).startswith("catch"):
                    continue
                if choice == "left":
                    update(table, a, b)
                elif choice == "right":
                    update(table, b, a)
                elif choice == "tie":
                    update(table, a, b, draw=True)
        speakers = blob.get("speakers") or {}
        n_speakers += len(speakers) if isinstance(speakers, dict) else len(speakers)
        procedure = blob.get("procedure") or {}
        n_proc += len(procedure) if isinstance(procedure, dict) else len(procedure)

    def show(title: str, table: dict[str, tuple[float, float]]) -> None:
        print(f"\n{title}")
        print(f"{'condition':20} {'μ':>6} {'σ':>6}")
        for k, (mu, sig) in sorted(table.items(), key=lambda kv: -kv[1][0]):
            print(f"{k:20} {mu:6.2f} {sig:6.2f}")

    print(f"files {len(files)} rankings {n_rank} speakers {n_speakers} procedure {n_proc}")
    print(f"attention checks {n_catch_ok}/{n_catch}")
    show("Believability", believ)
    show("Procedural plausibility", proc)


if __name__ == "__main__":
    main(sys.argv[1:])
