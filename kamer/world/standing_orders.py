"""Standing-order affordance layer C(ρ, v, t) for the Binnenhof.

An agent may *want* to speak, interrupt, or vote; it can only *act* when
the Reglement van Orde, its role, and the sitting state permit. Rejected
actions become structured refusals written to memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kamer.world.binnenhof import ChamberWorld


@dataclass
class AffordanceResult:
    allowed: bool
    action: str
    node_id: str
    reason: str = ""

    def refusal_text(self) -> str:
        return self.reason or f"action {self.action} on {self.node_id} is not permitted"


FLOOR_SPEAK = frozenset({"speak", "reply", "interrupt", "move_amendment", "vote"})
CHAIR_ONLY = frozenset({"recognize", "open_sitting", "adjourn", "call_vote", "call_to_order"})
CLERK_ONLY = frozenset({"read_kamerstuk"})  # griffier: administration, not the stenograph
STENO_ONLY = frozenset({"record"})
JOURNALIST_OK = frozenset({"observe", "talk", "wait", "move", "take_notes"})

TK_FLOOR = frozenset({
    "tweede_kamer", "chair_dais", "stenographers", "griffier_desk",
    "ministers_bench", "left_benches", "right_benches", "centre_aisle",
})
EK_FLOOR = frozenset({"eerste_kamer", "ek_floor", "ek_chair", "ek_benches"})


def chamber_of(world: ChamberWorld, node_id: str) -> str | None:
    """Which house a node belongs to: commons (Tweede Kamer) or senate (Eerste Kamer)."""
    if node_id in EK_FLOOR:
        return "senate"
    if node_id in TK_FLOOR:
        return "commons"
    tags = _tags(world, node_id)
    if "senate" in tags:
        return "senate"
    if "commons" in tags:
        return "commons"
    return None


def sitting_house(world: ChamberWorld) -> str:
    return getattr(world, "sitting_house", None) or getattr(world.cfg, "house", "commons") or "commons"


def agent_house(agent: Any) -> str:
    return getattr(agent, "house", None) or "commons"


def house_permits(agent: Any, chamber: str | None) -> bool:
    """Ministers appear in both houses; a Kamerlid sits in only one; press in neither."""
    if chamber is None:
        return True
    h = agent_house(agent)
    if h in {"both", "all"}:
        return True
    if h in {"none", ""}:
        return False
    return h == chamber


def house_nl(house: str) -> str:
    if house == "senate":
        return "Eerste Kamer"
    if house == "both":
        return "beide Kamers"
    return "Tweede Kamer"


def _tags(world: ChamberWorld, node_id: str) -> set[str]:
    if node_id not in world.tree.nodes:
        return set()
    tags = set(world.tree.get(node_id).tags)
    for anc in world.tree.ancestors(node_id):
        tags.update(anc.tags)
    return tags


def affordance_set(agent: Any, node_id: str, world: ChamberWorld) -> list[str]:
    role = getattr(agent, "status", "MP")
    tags = _tags(world, node_id)
    sitting = world.sitting_open
    actions = ["wait", "observe", "talk", "move", "reflect"]
    chamber = chamber_of(world, node_id)
    on_this_floor = (
        sitting
        and chamber is not None
        and chamber == sitting_house(world)
        and ("on_record" in tags or node_id in TK_FLOOR or node_id in EK_FLOOR)
        and house_permits(agent, chamber)
    )
    in_afdeeling = "committee" in tags

    if role == "Chair":
        if house_permits(agent, sitting_house(world)):
            actions += ["open_sitting", "adjourn", "recognize", "call_to_order", "call_vote"]
            if sitting and on_this_floor:
                actions.append("speak")
    elif role == "Clerk":
        # Griffier: papers and announcements, not the stenograph.
        actions += ["read_kamerstuk"]
        if "corridor" in tags:
            actions.append("talk")
    elif role == "Stenographer":
        actions += ["record"]
    elif role == "Journalist":
        actions += ["take_notes"]
        if "press" in tags or "gallery" in tags or "corridor" in tags:
            pass
        else:
            actions = [a for a in actions if a not in FLOOR_SPEAK]
    elif role == "Gallery":
        actions = ["wait", "observe", "move"]
    elif role in {"MP", "Minister"}:
        if on_this_floor:
            actions += ["request_floor", "vote"]
            if world.recognized == agent.id:
                actions += ["speak", "reply"]
                # Recht van amendement: Tweede Kamer only.
                if chamber == "commons":
                    actions.append("move_amendment")
        if in_afdeeling and role in {"MP", "Minister"}:
            # Afdeelingen: members speak without plenary recognition; off the Handelingen.
            actions += ["speak", "talk", "caucus"]
        if "corridor" in tags or "ministry" in tags:
            actions += ["talk", "caucus"]

    if not world.cfg.enable_affordance:
        return sorted(set(actions + list(FLOOR_SPEAK) + list(CHAIR_ONLY)))
    return sorted(set(actions))


def check_action(agent: Any, action: str, node_id: str, world: ChamberWorld) -> AffordanceResult:
    if world.cfg.ga_baseline or not world.cfg.enable_affordance:
        return AffordanceResult(True, action, node_id)

    allowed = affordance_set(agent, node_id, world)
    role = getattr(agent, "status", "MP")
    tags = _tags(world, node_id)

    chamber = chamber_of(world, node_id)
    if action in CHAIR_ONLY and role != "Chair":
        return AffordanceResult(False, action, node_id, "Alleen de Voorzitter mag de orde handhaven.")
    if action in CHAIR_ONLY and role == "Chair" and not house_permits(agent, sitting_house(world)):
        return AffordanceResult(
            False,
            action,
            node_id,
            "De Voorzitter van de eene Kamer opent de zitting van de andere niet.",
        )
    if action in FLOOR_SPEAK and role == "Journalist":
        return AffordanceResult(
            False,
            action,
            node_id,
            "De perstribune heeft geen spreekrecht op de vloer.",
        )
    if action in FLOOR_SPEAK and role == "Gallery":
        return AffordanceResult(False, action, node_id, "De publieke tribune heeft geen spreekrecht.")
    if action in FLOOR_SPEAK and chamber and not house_permits(agent, chamber):
        other = house_nl("senate" if chamber == "commons" else "commons")
        here = house_nl(chamber)
        return AffordanceResult(
            False,
            action,
            node_id,
            f"Een lid der {other} voert op de vloer van de {here} het woord niet.",
        )
    if action == "move_amendment" and chamber == "senate":
        return AffordanceResult(
            False,
            action,
            node_id,
            "De Eerste Kamer heeft geen recht van amendement; zij neemt aan of verwerpt.",
        )
    in_afdeeling = "committee" in tags
    if (
        action == "speak"
        and world.recognized != agent.id
        and role != "Chair"
        and not in_afdeeling
    ):
        return AffordanceResult(
            False,
            action,
            node_id,
            "Mijnheer de Voorzitter heeft u het woord nog niet gegeven.",
        )
    if action in {"speak", "reply", "vote", "request_floor"} and not world.sitting_open and not in_afdeeling:
        return AffordanceResult(False, action, node_id, "De vergadering is niet geopend.")
    if action == "record" and role == "Clerk":
        return AffordanceResult(
            False,
            action,
            node_id,
            "De griffier is geen stenograaf; de stenograaf teekent de Handelingen aan.",
        )
    if action == "record" and "on_record" not in tags and node_id != "stenographers":
        return AffordanceResult(
            False,
            action,
            node_id,
            "De stenograaf neemt alleen hetgeen op de vloer wordt gesproken op.",
        )
    if action == "move" and role == "Journalist" and "on_record" in tags and "gallery" not in tags:
        return AffordanceResult(
            False,
            action,
            node_id,
            "Journalisten blijven op de perstribune of in de wandelgang.",
        )
    if action not in allowed and action not in {"wait", "observe", "reflect"}:
        return AffordanceResult(False, action, node_id, f"Rol {role} mag '{action}' hier niet.")
    return AffordanceResult(True, action, node_id)
