#!/usr/bin/env python3
"""Compare historian-lab exports from two or more raters (Table 5 and Appendix F).

For each rater: attention checks, wins-losses-ties of Kamer (full_llm) against
the Smallville-style ablation (ga_llm), and that rater's own TrueSkill run. Across
raters: Cohen's kappa on the per-pair verdict (Kamer / tie / GA), the per-pair
mean preference with a bootstrap interval over pairs, and the standing-order
verdicts side by side.

  PYTHONPATH=. python3 scripts/historian_agreement.py ida_label.json marcella_label.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from scripts.score_historian_labels import update

CRITERIA = (("bel", "believability"), ("hist", "procedure"))
VERDICTS = ("G", "tie", "K")


def verdict(row: dict, crit: str) -> str | None:
    choice = row.get(crit)
    if choice == "tie":
        return "tie"
    if choice not in ("L", "R"):
        return None
    side = row["left"] if choice == "L" else row["right"]
    return "K" if side == "full_llm" else "G"


def trueskill(verdicts: list[str]) -> tuple[float, float, float]:
    skill: dict[str, tuple[float, float]] = defaultdict(lambda: (25.0, 25 / 3))
    for v in verdicts:
        if v == "K":
            update(skill, "K", "G")
        elif v == "G":
            update(skill, "G", "K")
        else:
            update(skill, "K", "G", draw=True)
    return skill["K"][0], skill["G"][0], skill["K"][1]


def kappa(a: list[str], b: list[str], weighted: bool = False) -> float:
    idx = {c: i for i, c in enumerate(VERDICTS)}
    n, k = len(a), len(VERDICTS)
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    rows = [sum(r) for r in obs]
    cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = [[abs(i - j) if weighted else float(i != j) for j in range(k)] for i in range(k)]
    observed = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k)) / n
    expected = sum(w[i][j] * rows[i] * cols[j] for i in range(k) for j in range(k)) / n**2
    return 1 - observed / expected


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+")
    p.add_argument("--boot", type=int, default=20000)
    args = p.parse_args()
    raters = [json.loads(Path(f).read_text(encoding="utf-8")) for f in args.files]
    names = [r.get("reviewer") or Path(f).stem for r, f in zip(raters, args.files)]
    pairs = sorted(
        set.intersection(*(set(r.get("interviews", {})) for r in raters)),
    )
    ranked = [k for k in pairs if not raters[0]["interviews"][k].get("catch")]
    ranked = [k for k in ranked if all(verdict(r["interviews"][k], "bel") for r in raters)]
    print(f"raters {len(raters)}; shared pairs {len(ranked)} (attention checks excluded)")

    for name, r in zip(names, raters):
        rows = r["interviews"].values()
        checks = [x for x in rows if x.get("catch")]
        ok = sum(
            ("catch" in x["left"] and x["bel"] == "R") or ("catch" in x["right"] and x["bel"] == "L") for x in checks
        )
        print(f"\n{name}: attention checks {ok}/{len(checks)}")
        # TrueSkill is order-dependent: replay each rater's pairs in export order, as
        # score_historian_labels.py does.
        own = [k for k in r["interviews"] if k in set(ranked)]
        for crit, label in CRITERIA:
            v = [verdict(r["interviews"][k], crit) for k in own]
            c = Counter(v)
            mu_k, mu_g, sig = trueskill(v)
            print(f"  {label:13} K-G-tie {c['K']}-{c['G']}-{c['tie']}  TrueSkill K {mu_k:.2f} GA {mu_g:.2f} sigma {sig:.2f}")

    rng = random.Random(0)
    for crit, label in CRITERIA:
        v = [[verdict(r["interviews"][k], crit) for k in ranked] for r in raters]
        print(f"\n{label}")
        if len(raters) == 2:
            agree = sum(x == y for x, y in zip(*v))
            opposite = sum({x, y} == {"K", "G"} for x, y in zip(*v))
            print(
                f"  exact agreement {agree}/{len(ranked)}; opposite verdicts {opposite}; "
                f"kappa {kappa(*v):.2f}; linear-weighted kappa {kappa(*v, weighted=True):.2f}"
            )
        score = {"K": 1, "tie": 0, "G": -1}
        item = [sum(score[r[i]] for r in v) / len(v) for i in range(len(ranked))]
        means = sorted(sum(rng.choice(item) for _ in item) / len(item) for _ in range(args.boot))
        lo, hi = means[int(0.025 * args.boot)], means[int(0.975 * args.boot)]
        net = Counter((s > 0) - (s < 0) for s in item)
        print(
            f"  mean preference for Kamer {sum(item) / len(item):.2f} [{lo:.2f}, {hi:.2f}] "
            f"(pairs net Kamer {net[1]}, net GA {net[-1]}, net zero {net[0]})"
        )

    print("\nstanding-order vignettes (in order / on record / anachronism)")
    for k in sorted(set.intersection(*(set(r.get("procedure", {})) for r in raters))):
        rows = [r["procedure"][k] for r in raters]
        cells = " | ".join(f"{x['in_order']}/{x['on_record']}/{x['anachronism']}" for x in rows)
        print(f"  {k} {rows[0].get('hidden', ''):22} {cells}")
    print("\nrules")
    for k in sorted(set.intersection(*(set(r.get("rules", {})) for r in raters))):
        print(f"  {k:13} " + "  ".join(r["rules"][k]["verdict"] for r in raters))


if __name__ == "__main__":
    main()
