"""Parliamentary role automaton A = (Σ, Δ, Φ)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kamer.agents.agent import Agent
    from kamer.world.binnenhof import ChamberWorld


class Role(str, Enum):
    CHAIR = "Chair"
    MP = "MP"
    MINISTER = "Minister"
    CLERK = "Clerk"
    JOURNALIST = "Journalist"
    GALLERY = "Gallery"


DELTA: dict[Role, set[Role]] = {
    Role.MP: {Role.MINISTER, Role.CHAIR},
    Role.MINISTER: {Role.MP},
    Role.CHAIR: {Role.MP},
    Role.CLERK: set(),
    Role.JOURNALIST: set(),
    Role.GALLERY: set(),
}

FLOOR_ROLES = frozenset({Role.CHAIR.value, Role.MP.value, Role.MINISTER.value})
OFF_RECORD_TALKERS = frozenset({Role.MP.value, Role.MINISTER.value, Role.JOURNALIST.value, Role.CHAIR.value})


def stratum(status: str) -> str:
    if status in {Role.CHAIR.value, Role.CLERK.value}:
        return "institutional"
    if status == Role.MINISTER.value:
        return "government"
    if status == Role.MP.value:
        return "member"
    if status == Role.JOURNALIST.value:
        return "press"
    return "gallery"


def is_on_record_role(status: str) -> bool:
    return status in FLOOR_ROLES


@dataclass
class Transition:
    src: Role
    dst: Role
    reason: str


class RoleAutomaton:
    """Agent i moves ρ → ρ' only if (ρ, ρ') ∈ Δ and φ holds (appointment, election)."""

    def try_transition(self, agent: "Agent", dst: Role, world: "ChamberWorld", reason: str) -> bool:
        if not world.cfg.enable_automaton:
            agent.status = dst.value
            return True
        src = Role(agent.status)
        if dst not in DELTA.get(src, set()):
            return False
        agent.status = dst.value
        world.record("role_transition", agent=agent.id, src=src.value, dst=dst.value, reason=reason)
        return True
