#!/usr/bin/env python3
"""Run S1 (two-week sandbox) at Smallville scale N=25, then optional N=200."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from maroon.config import SimConfig
from maroon.eval.audit import audit_utterances
from maroon.eval.emergence import run_rumour_experiment
from maroon.eval.interview import run_interviews
from maroon.sim.engine import Simulation
from maroon.world.island import build_island


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--condition", default="full")
    p.add_argument("--out", default="runs/s1")
    args = p.parse_args()

    cfg = SimConfig(seed=args.seed, n_agents=args.n, n_days=args.days).apply_preset(args.condition)
    sim = Simulation(cfg)
    world_counts = sim.world.tree.counts()
    result = run_rumour_experiment(sim, days=args.days)
    interviews = run_interviews(sim, n=min(25, args.n))
    audit = audit_utterances(sim)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "condition": args.condition,
        "world": world_counts,
        "emergence": {
            "final": result["final"],
            "embellishment": result["embellishment"],
            "transmissions": result["transmissions"],
            "ties": result["ties"],
            "coordination": result["coordination"],
            "hourly": result["hourly"],
        },
        "interviews": {
            "n": interviews["n"],
            "mean_institutional_awareness": interviews["mean_institutional_awareness"],
            "rows": interviews["rows"],
        },
        "audit": audit,
        "newspaper": sim.world.newspaper,
        "n_agents": len(sim.agents),
        "days": args.days,
        "seed": args.seed,
    }
    (out / f"{args.condition}_seed{args.seed}.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    sim.save(out / f"state_{args.condition}_seed{args.seed}.json")
    print(json.dumps({k: payload[k] for k in ("world", "n_agents", "days", "audit") if k in payload}, indent=2))
    print("emergence.final", json.dumps(result["final"], indent=2))
    print("ties", result["ties"])
    print("coordination", result["coordination"])
    print("IA", interviews["mean_institutional_awareness"])
    print("wrote", out)


if __name__ == "__main__":
    # Touch builder so counts are import-safe even without a run.
    _ = build_island
    main()
