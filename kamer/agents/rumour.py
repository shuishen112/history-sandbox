"""Corridor talk: provenance-tracked rumours that may never enter the Handelingen."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from kamer.agents.role import stratum
from kamer.config import RUMOUR_DISTORT_P


DISTORTABLE = ("time", "person", "amount", "place")


@dataclass
class RumourHop:
    agent_id: str
    step: int
    content: str
    distortion: dict[str, Any] = field(default_factory=dict)


@dataclass
class Rumour:
    id: str
    topic: str
    canonical: dict[str, Any]
    content: str
    origin_agent: str
    origin_step: int
    hops: list[RumourHop] = field(default_factory=list)

    @property
    def hop_count(self) -> int:
        return max(0, len(self.hops) - 1)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "canonical": self.canonical,
            "content": self.content,
            "origin_agent": self.origin_agent,
            "origin_step": self.origin_step,
            "hop_count": self.hop_count,
            "hops": [h.__dict__ for h in self.hops],
        }


def render_rumour(facts: dict[str, Any]) -> str:
    person = facts.get("person", "a minister")
    event = facts.get("event", "will resign")
    when = facts.get("time", "this week")
    amount = facts.get("amount", "")
    place = facts.get("place", "the wandelgang")
    extra = f" ({amount})" if amount else ""
    return f"{person} {event}{extra}; word of it is circulating in {place} {when}."


def distort(facts: dict[str, Any], rng: random.Random, p: float) -> tuple[dict[str, Any], dict[str, Any]]:
    new = dict(facts)
    changes: dict[str, Any] = {}
    if rng.random() > p:
        return new, changes
    key = rng.choice([k for k in DISTORTABLE if k in new] or ["time"])
    options = {
        "time": ["today", "tomorrow", "after the vote", "before Christmas", "next sitting"],
        "person": ["the Minister of Colonies", "the Minister of Finance", "the chairman", "an ARP member"],
        "amount": ["a deficit of 3 million", "a deficit of 5 million", "no deficit at all"],
        "place": ["the wandelgang", "Afdeeling A", "the press gallery", "the ministers' rooms"],
    }
    old = new.get(key)
    choices = [c for c in options.get(key, ["soon"]) if c != old]
    if choices:
        new[key] = rng.choice(choices)
        changes[key] = {"from": old, "to": new[key]}
    return new, changes


class RumourNetwork:
    def __init__(self, distort_p: float = RUMOUR_DISTORT_P) -> None:
        self.distort_p = distort_p
        self.rumours: dict[str, Rumour] = {}
        self.known: dict[str, set[str]] = {}
        self.inbox: dict[str, list[tuple[Rumour, str]]] = {}
        self.views: dict[str, dict[str, dict[str, Any]]] = {}

    def seed(self, agent_id: str, facts: dict[str, Any], step: int, topic: str = "leak") -> Rumour:
        rid = uuid.uuid4().hex[:12]
        content = render_rumour(facts)
        r = Rumour(
            id=rid,
            topic=topic,
            canonical=dict(facts),
            content=content,
            origin_agent=agent_id,
            origin_step=step,
            hops=[RumourHop(agent_id, step, content)],
        )
        self.rumours[rid] = r
        self.known.setdefault(agent_id, set()).add(rid)
        self.views.setdefault(agent_id, {})[rid] = dict(facts)
        return r

    def aware(self, agent_id: str, topic: str | None = None) -> bool:
        for rid in self.known.get(agent_id, ()):
            if topic is None or self.rumours[rid].topic == topic:
                return True
        return False

    def pop_inbox(self, agent_id: str) -> list[tuple[Rumour, str]]:
        items = self.inbox.pop(agent_id, [])
        return items

    def transmit(
        self,
        speaker: Any,
        hearer: Any,
        rng: random.Random,
        step: int,
        on_floor: bool,
        in_corridor: bool,
    ) -> Rumour | None:
        known = list(self.known.get(speaker.id, ()))
        if not known:
            return None
        rid = rng.choice(known)
        r = self.rumours[rid]
        if rid in self.known.get(hearer.id, ()):
            return None
        # Official floor speech is not gossip; leaks travel in the wandelgang.
        if on_floor and not in_corridor:
            p = 0.02
        elif in_corridor:
            p = 0.28
        else:
            p = 0.10
        if stratum(hearer.status) in {"government", "institutional"} and in_corridor:
            p *= 0.35
        if hearer.status == "Journalist" and in_corridor:
            p = max(p, 0.55)
        if rng.random() > p:
            return None
        facts = dict(self.views.get(speaker.id, {}).get(rid, r.canonical))
        facts, changes = distort(facts, rng, self.distort_p)
        content = render_rumour(facts)
        r.hops.append(RumourHop(hearer.id, step, content, changes))
        self.known.setdefault(hearer.id, set()).add(rid)
        self.views.setdefault(hearer.id, {})[rid] = facts
        self.inbox.setdefault(hearer.id, []).append((r, speaker.name))
        return r

    def embellishment_rate(self) -> float:
        hops = [h for r in self.rumours.values() for h in r.hops[1:]]
        if not hops:
            return 0.0
        return sum(1 for h in hops if h.distortion) / len(hops)
