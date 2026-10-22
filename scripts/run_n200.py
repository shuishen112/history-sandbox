#!/usr/bin/env python3
import json
import time
from pathlib import Path

from maroon.config import SimConfig
from maroon.eval.emergence import run_rumour_experiment
from maroon.sim.engine import Simulation

t0 = time.time()
sim = Simulation(SimConfig(n_agents=200, seed=7, n_days=7))
result = run_rumour_experiment(sim, days=7)
payload = {
    "seconds": round(time.time() - t0, 2),
    "n": 200,
    "days": 7,
    "final": result["final"],
    "embellishment": result["embellishment"],
    "coordination": result["coordination"],
    "ties": result["ties"],
    "hourly": result["hourly"],
}
Path("runs/emergence").mkdir(parents=True, exist_ok=True)
Path("runs/emergence/n200_d7_seed7.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("done", payload["seconds"], "aware", payload["final"].get("aware"), "coord", payload["coordination"], flush=True)
