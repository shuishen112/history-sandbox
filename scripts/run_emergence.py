#!/usr/bin/env python3
"""Rumour-diffusion sweep used for Figure 2 (5 seeds)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from maroon.config import SimConfig
from maroon.eval.emergence import run_rumour_experiment
from maroon.sim.engine import Simulation


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--seeds", default="7,11,19,29,31")
    p.add_argument("--out", default="runs/emergence")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    all_runs = []
    for seed in [int(s) for s in args.seeds.split(",")]:
        cfg = SimConfig(seed=seed, n_agents=args.n, n_days=args.days)
        sim = Simulation(cfg)
        result = run_rumour_experiment(sim, days=args.days)
        rec = {
            "seed": seed,
            "final": result["final"],
            "hourly": result["hourly"],
            "embellishment": result["embellishment"],
            "coordination": result["coordination"],
            "ties": result["ties"],
        }
        all_runs.append(rec)
        print(f"seed {seed} final={result['final']} emb={result['embellishment']:.3f}")
    (out / f"n{args.n}_d{args.days}.json").write_text(json.dumps(all_runs, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
