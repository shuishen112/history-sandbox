"""S1 interviews: procedural awareness, not recovered inner lives."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kamer.sim.engine import Simulation


INTERVIEW_QUESTIONS = {
    "self-knowledge": ["Wie bent u, en welke functie bekleedt u in de Kamer?"],
    "memory": ["Wat hebt u deze week in de wandelgang of op de vloer vernomen?"],
    "plans": ["Wat zult u morgen tijdens de vergadering doen?"],
    "reactions": ["U wilt het woord, maar de Voorzitter herkent u niet. Wat doet u?"],
    "reflections": ["Waarover hebt u de laatste dagen nagedacht?"],
    "institutional_awareness": [
        "Mag een journalist het woord voeren op de vloer? En een lid, zonder erkenning van de Voorzitter?"
    ],
}


def procedural_score(status: str, answer: str) -> float:
    t = answer.lower()
    mentions = any(
        w in t
        for w in (
            "voorzitter",
            "woord",
            "reglement",
            "spreekrecht",
            "tribune",
            "floor",
            "chair",
            "recognize",
        )
    )
    if status == "Journalist":
        return 1.0 if mentions and any(w in t for w in ("geen", "niet", "tribune", "not")) else 0.0
    return 1.0 if mentions else 0.0


def run_interviews(sim: "Simulation", n: int = 25) -> dict:
    agents = list(sim.agents.values())[:n]
    rows = []
    scores = []
    for agent in agents:
        answers = {cat: [sim.interview(agent.id, q) for q in qs] for cat, qs in INTERVIEW_QUESTIONS.items()}
        sc = procedural_score(agent.status, answers["institutional_awareness"][0])
        scores.append(sc)
        rows.append({"id": agent.id, "name": agent.name, "status": agent.status, "answers": answers, "proc": sc})
    return {"n": len(rows), "mean_procedural": sum(scores) / len(scores) if scores else 0.0, "rows": rows}
