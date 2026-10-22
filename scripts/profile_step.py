#!/usr/bin/env python3
import cProfile
import pstats
import time

from maroon.config import SimConfig
from maroon.sim.engine import Simulation


def main() -> None:
    t0 = time.time()
    sim = Simulation(SimConfig(n_agents=25, seed=7))
    print("init", round(time.time() - t0, 3), "agents", len(sim.agents), flush=True)
    t1 = time.time()
    sim.step()
    print("step1", round(time.time() - t1, 3), flush=True)
    pr = cProfile.Profile()
    pr.enable()
    t2 = time.time()
    for _ in range(12):
        sim.step()
    pr.disable()
    print("12steps", round(time.time() - t2, 3), "mems", sum(len(a.memory.items) for a in sim.agents.values()), flush=True)
    stats = pstats.Stats(pr).sort_stats("tottime")
    stats.print_stats(20)


if __name__ == "__main__":
    main()
