"""Corridor-vs-floor leak diffusion (S1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kamer.sim.engine import Simulation


def awareness_by_stratum(sim: "Simulation") -> dict[str, float]:
    last = sim.metrics[-1]["aware"] if sim.metrics else {}
    return last


def daily_curve(sim: "Simulation") -> list[dict]:
    by_day: dict[int, dict] = {}
    for m in sim.metrics:
        by_day[m["day"]] = m
    return [by_day[d] for d in sorted(by_day)]


def floor_mention_rate(sim: "Simulation") -> float:
    """Share of Handelingen lines that mention the leak."""
    n = 0
    hit = 0
    for page in sim.press.pages:
        for line in page.lines:
            n += 1
            blob = line.get("text", "").lower()
            if any(w in blob for w in ("wandelgang", "aftreden", "tekort", "resign", "deficit", "leak")):
                hit += 1
    return hit / n if n else 0.0
