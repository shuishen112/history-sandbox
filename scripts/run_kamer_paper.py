"""Paper experiments: S1 ablations, S2 fidelity, S3 chair intervention, audits."""

from __future__ import annotations

import json
from pathlib import Path

from kamer.config import SimConfig
from kamer.eval.emergence import daily_curve, floor_mention_rate
from kamer.eval.fidelity import anachronism_rate, archive_role_mix, compare, sim_role_mix
from kamer.eval.interview import run_interviews
from kamer.sim.engine import Simulation

SEEDS = [7, 11, 19, 29, 31]
PRESETS = ["full", "ga", "no_affordance", "no_automaton", "no_rumour"]
OUT = Path("runs/kamer/paper_exps.json")


def handelingen_lines(sim: Simulation) -> list[dict]:
    lines = []
    for page in sim.press.pages:
        lines.extend(page.lines)
    return lines


def naive_lines(sim: Simulation) -> list[dict]:
    extra = []
    for e in sim.world.events:
        if e["kind"] == "dialogue":
            a = sim.agents.get(e.get("a"))
            extra.append(
                {
                    "role": a.status if a else "MP",
                    "text": "corridor talk",
                    "party": getattr(a, "party", "") if a else "",
                }
            )
    return extra


def run_one(seed: int, preset: str, days: int = 7, n: int = 25, **kw) -> dict:
    cfg = SimConfig(seed=seed, n_agents=n, n_days=days, **kw).apply_preset(preset)
    sim = Simulation(cfg)
    sim.seed_leak()
    sim.run_days(days)
    curve = daily_curve(sim)
    last = curve[-1]["aware"] if curve else {}
    lines = handelingen_lines(sim)
    interviews = run_interviews(sim, n)
    refusals = sum(1 for a in sim.agents.values() if a.last_refusal)
    texts = [ln.get("text") or "" for ln in lines]
    return {
        "seed": seed,
        "preset": preset,
        "final_aware": last,
        "member_end": last.get("member", 0.0),
        "press_end": last.get("press", 0.0),
        "government_end": last.get("government", 0.0),
        "floor_mention": floor_mention_rate(sim),
        "embellishment": sim.world.rumours.embellishment_rate(),
        "mean_procedural": interviews["mean_procedural"],
        "n_lines": len(lines),
        "lines": lines,
        "naive_extra": naive_lines(sim),
        "refusals": refusals,
        "anachronism": anachronism_rate(texts),
        "n_steps": sim.world.clock.step,
        "kw": kw,
    }


def mean_key(runs: list[dict], key: str) -> float:
    vals = [r[key] for r in runs if key in r]
    return sum(vals) / len(vals) if vals else 0.0


def main() -> None:
    print("archive holdout…", flush=True)
    holdout = archive_role_mix(year_min=1890, year_max=1899)
    calib = archive_role_mix(year_min=1860, year_max=1889)
    print("holdout speeches", holdout["n_speeches"], "calib", calib["n_speeches"], flush=True)

    by_preset: dict[str, list[dict]] = {}
    for preset in PRESETS:
        print("S1", preset, flush=True)
        by_preset[preset] = [run_one(s, preset) for s in SEEDS]

    # Rule-ABM: empirical calib mix vs holdout (no simulation).
    rule = compare(
        {
            "role_mix": calib["role_mix"],
            "lengths": calib["lengths"],
            "journalist_share": 0.0,
            "n_speeches": calib["n_speeches"],
        },
        holdout,
    )

    fidelity = {}
    for preset, runs in by_preset.items():
        sims = [compare(sim_role_mix(r["lines"]), holdout) for r in runs]
        fidelity[preset] = {
            "role_jsd": sum(x["role_jsd"] for x in sims) / len(sims),
            "length_w1": sum(x["length_w1"] for x in sims) / len(sims),
            "journalist_share": sum(x["journalist_share"] for x in sims) / len(sims),
        }
    naive_sims = [compare(sim_role_mix(r["lines"], r["naive_extra"]), holdout) for r in by_preset["full"]]
    fidelity["naive"] = {
        "role_jsd": sum(x["role_jsd"] for x in naive_sims) / len(naive_sims),
        "length_w1": sum(x["length_w1"] for x in naive_sims) / len(naive_sims),
        "journalist_share": sum(x["journalist_share"] for x in naive_sims) / len(naive_sims),
    }
    fidelity["rule_abm"] = rule

    print("interventions…", flush=True)
    interventions = []
    for strict in (0.25, 0.5, 1.0, 2.0, 4.0):
        for distort in (0.05, 0.18):
            runs = [
                run_one(s, "full", chair_strictness=strict, rumour_distort_p=distort)
                for s in SEEDS[:3]
            ]
            interventions.append(
                {
                    "chair_strictness": strict,
                    "distort": distort,
                    "floor_mention": mean_key(runs, "floor_mention"),
                    "member_end": mean_key(runs, "member_end"),
                }
            )

    s1 = {}
    for preset, runs in by_preset.items():
        s1[preset] = {
            "member_end": mean_key(runs, "member_end"),
            "press_end": mean_key(runs, "press_end"),
            "government_end": mean_key(runs, "government_end"),
            "floor_mention": mean_key(runs, "floor_mention"),
            "embellishment": mean_key(runs, "embellishment"),
            "mean_procedural": mean_key(runs, "mean_procedural"),
            "anachronism": mean_key(runs, "anachronism"),
            "refusals": mean_key(runs, "refusals"),
            "n_lines": mean_key(runs, "n_lines"),
        }

    out = {
        "holdout": {k: v for k, v in holdout.items() if k != "lengths"},
        "calib": {k: v for k, v in calib.items() if k != "lengths"},
        "s1": s1,
        "fidelity": fidelity,
        "interventions": interventions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # drop bulky line dumps
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:4000])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
