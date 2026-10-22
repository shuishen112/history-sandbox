#!/usr/bin/env python3
"""Sequential S1 + emergence driver with progress prints."""

from __future__ import annotations

import json
import time
from pathlib import Path

from maroon.config import SimConfig
from maroon.eval.audit import audit_utterances
from maroon.eval.emergence import run_rumour_experiment
from maroon.eval.interview import run_interviews
from maroon.sim.engine import Simulation


def one(condition: str, seed: int, n: int, days: int, out: Path) -> dict:
    t0 = time.time()
    cfg = SimConfig(seed=seed, n_agents=n, n_days=days).apply_preset(condition)
    sim = Simulation(cfg)
    counts = sim.world.tree.counts()
    result = run_rumour_experiment(sim, days=days)
    interviews = run_interviews(sim, n=min(25, n))
    audit = audit_utterances(sim)
    payload = {
        "condition": condition,
        "seed": seed,
        "n_agents": n,
        "days": days,
        "seconds": round(time.time() - t0, 2),
        "world": counts,
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
        "maroon_events": sum(1 for a in sim.agents.values() if a.status == "Maroon"),
        "statuses": {s: sum(1 for a in sim.agents.values() if a.status == s) for s in
                     ["Enslaved", "SelfHired", "Maroon", "Recaptured", "Manumitted", "FreeColoured", "White"]},
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{condition}_seed{seed}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        f"done {condition} seed={seed} {payload['seconds']}s "
        f"aware={result['final'].get('aware')} "
        f"IA={interviews['mean_institutional_awareness']:.2f} "
        f"coord={result['coordination']['n_arrived']} "
        f"emb={result['embellishment']:.2f}",
        flush=True,
    )
    return payload


def main() -> None:
    out = Path("runs/s1")
    one("full", 7, 25, 14, out)
    one("ga", 7, 25, 14, out)
    one("no_affordance", 7, 25, 14, out)
    em = Path("runs/emergence")
    runs = []
    for seed in (7, 11, 19, 29, 31):
        payload = one("full", seed, 25, 14, em)
        runs.append(
            {
                "seed": seed,
                "final": payload["emergence"]["final"],
                "hourly": payload["emergence"]["hourly"],
                "embellishment": payload["emergence"]["embellishment"],
                "coordination": payload["emergence"]["coordination"],
                "ties": payload["emergence"]["ties"],
            }
        )
    em.mkdir(parents=True, exist_ok=True)
    (em / "n25_d14.json").write_text(json.dumps(runs, indent=2), encoding="utf-8")
    print("wrote", em / "n25_d14.json", flush=True)


if __name__ == "__main__":
    main()
