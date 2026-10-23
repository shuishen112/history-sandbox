"""Stateful objects of the Binnenhof sandbox (paper Table 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


OBJECT_MACHINES: dict[str, dict[str, Any]] = {
    "gavel": {
        "states": ["resting", "opening", "adjourned"],
        "default": "resting",
        "changed_by": ["chair"],
    },
    "speaker_list": {
        "states": ["empty", "open", "closed"],
        "default": "empty",
        "changed_by": ["chair", "clerk"],
    },
    "kamerstuk": {
        "states": ["tabled", "in_debate", "voted", "withdrawn"],
        "default": "tabled",
        "changed_by": ["government", "chair"],
    },
    "stenograph": {
        "states": ["idle", "recording", "paused"],
        "default": "idle",
        "changed_by": ["stenographer"],
    },
    "voting_box": {
        "states": ["closed", "open", "counted"],
        "default": "closed",
        "changed_by": ["chair", "clerk"],
    },
    "press_gallery_desk": {
        "states": ["empty", "occupied"],
        "default": "empty",
        "changed_by": ["journalist"],
    },
    "circulaire": {
        "states": ["none", "circulating", "spent"],
        "default": "none",
        "changed_by": ["mp"],
    },
}


@dataclass
class StatefulObject:
    id: str
    kind: str
    node_id: str
    state: str
    payload: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        extra = ""
        if self.kind == "speaker_list":
            extra = f" ({len(self.payload.get('speakers', []))} names)"
        elif self.kind == "kamerstuk":
            extra = f" ({self.payload.get('title', 'bill')})"
        elif self.kind == "stenograph" and self.state == "recording":
            extra = f" (page={self.payload.get('page', '?')})"
        elif self.kind == "circulaire":
            state_nl = {
                "none": "niet aanwezig",
                "circulating": "in omloop",
                "spent": "reeds rondgedeeld",
            }.get(self.state, self.state)
            return f"circulaire van de kamerclub is {state_nl}"
        return f"{self.kind} is {self.state}{extra}"

    def set_state(self, new_state: str, **payload: Any) -> None:
        machine = OBJECT_MACHINES[self.kind]
        if new_state not in machine["states"]:
            raise ValueError(f"{self.kind} cannot be {new_state}")
        self.state = new_state
        self.payload.update(payload)


@dataclass
class ObjectStore:
    objects: dict[str, StatefulObject] = field(default_factory=dict)

    def add(self, obj: StatefulObject) -> StatefulObject:
        self.objects[obj.id] = obj
        return obj

    def get(self, oid: str) -> StatefulObject:
        return self.objects[oid]

    def by_kind(self, kind: str) -> list[StatefulObject]:
        return [o for o in self.objects.values() if o.kind == kind]

    def at_node(self, node_id: str) -> list[StatefulObject]:
        return [o for o in self.objects.values() if o.node_id == node_id]
