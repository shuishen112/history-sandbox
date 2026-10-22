"""S1: one week of Tweede Kamer sittings, N=25, corridor leak."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kamer.config import SimConfig
from kamer.eval.emergence import daily_curve, floor_mention_rate
from kamer.eval.interview import run_interviews
from kamer.sim.engine import Simulation


def run_one(seed: int, n: int, days: int, preset: str = "full") -> dict:
    cfg = SimConfig(seed=seed, n_agents=n, n_days=days).apply_preset(preset)
    sim = Simulation(cfg)
    seed_id = sim.seed_leak()
    sim.run_days(days)
    curve = daily_curve(sim)
    interviews = run_interviews(sim, n)
    return {
        "seed": seed,
        "preset": preset,
        "n": n,
        "days": days,
        "seed_agent": seed_id,
        "curve": [{"day": c["day"], "aware": c["aware"], "handelingen": c["n_handelingen_lines"]} for c in curve],
        "final_aware": curve[-1]["aware"] if curve else {},
        "embellishment": sim.world.rumours.embellishment_rate(),
        "floor_mention_rate": floor_mention_rate(sim),
        "n_handelingen_lines": sum(len(p.lines) for p in sim.press.pages),
        "n_corridor_talks": sum(1 for e in sim.world.events if e["kind"] == "dialogue" and not e.get("on_record")),
        "mean_procedural": interviews["mean_procedural"],
        "n_refusals": sum(1 for e in sim.world.events if False),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--seeds", type=str, default="7,11,19,29,31")
    p.add_argument("--preset", type=str, default="full")
    p.add_argument("--out", type=str, default="runs/kamer/s1.json")
    args = p.parse_args()
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    runs = [run_one(s, args.n, args.days, args.preset) for s in seeds]
    # means at day 1 and last day
    def mean_aware(day: int, key: str) -> float:
        vals = []
        for r in runs:
            for c in r["curve"]:
                if c["day"] == day:
                    vals.append(c["aware"].get(key, 0.0))
        return sum(vals) / len(vals) if vals else 0.0

    last = runs[0]["curve"][-1]["day"] if runs and runs[0]["curve"] else 0
    summary = {
        "n_runs": len(runs),
        "member_d1": mean_aware(1, "member"),
        "member_end": mean_aware(last, "member"),
        "government_d1": mean_aware(1, "government"),
        "government_end": mean_aware(last, "government"),
        "press_d1": mean_aware(1, "press"),
        "press_end": mean_aware(last, "press"),
        "institutional_d1": mean_aware(1, "institutional"),
        "institutional_end": mean_aware(last, "institutional"),
        "mean_embellishment": sum(r["embellishment"] for r in runs) / len(runs),
        "mean_floor_mention": sum(r["floor_mention_rate"] for r in runs) / len(runs),
        "mean_procedural": sum(r["mean_procedural"] for r in runs) / len(runs),
        "runs": runs,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, indent=2))


if __name__ == "__main__":
    main()
