#!/usr/bin/env python3
import time
from maroon.config import SimConfig
from maroon.eval.emergence import run_rumour_experiment
from maroon.sim.engine import Simulation

t0 = time.time()
sim = Simulation(SimConfig(n_agents=25, seed=7))
result = run_rumour_experiment(sim, days=14)
print(
    "sec", round(time.time() - t0, 2),
    "rumours", len(sim.world.rumours.rumours),
    "tx", sim.world.rumours.transmissions,
    "mems", sum(len(a.memory.items) for a in sim.agents.values()),
    "aware", result["final"].get("aware"),
    "log", len(sim.world.log),
    flush=True,
)
