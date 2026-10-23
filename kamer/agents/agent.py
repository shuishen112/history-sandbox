"""Role-constrained parliamentary agent. One step follows Algorithm 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from maroon.agents.llm import CognitiveBackend
from maroon.agents.memory import MemoryStream
from maroon.agents.spatial import SpatialMemory

from kamer.agents.role import RoleAutomaton, stratum
from kamer.config import MAX_REPLAN, SITTING_CLOSE_HOUR, SITTING_OPEN_HOUR, stable_mod
from kamer.world.standing_orders import check_action

if TYPE_CHECKING:
    from kamer.world.binnenhof import ChamberWorld


EMOJI = {
    "speak": "🎙",
    "talk": "💬",
    "observe": "👁",
    "recognize": "🔔",
    "open_sitting": "⚖️",
    "adjourn": "⚖️",
    "record": "🖋",
    "vote": "🗳️",
    "take_notes": "📰",
    "caucus": "🤝",
    "wait": "•",
    "move": "🚶",
    "reflect": "💭",
    "request_floor": "✋",
}


HOME = {
    "Chair": "chair_dais",
    "MP": "left_benches",
    "Minister": "ministers_bench",
    "Clerk": "griffier_desk",
    "Journalist": "gallery_desk",
    "Gallery": "tribune",
}

STATUS_NL = {
    "Chair": "Voorzitter",
    "MP": "Kamerlid",
    "Minister": "minister",
    "Clerk": "griffier",
    "Journalist": "verslaggever",
    "Gallery": "toehoorder",
}


@dataclass
class AgentState:
    id: str
    name: str
    status: str
    role: str
    function: str
    party: str
    home_area: str
    location: str
    persona: str
    member_ref: str = ""
    house: str = "commons"  # commons | senate | both | none
    excerpts: list[str] = field(default_factory=list)


class Agent:
    def __init__(self, spec: AgentState, backend: CognitiveBackend) -> None:
        self.id = spec.id
        self.name = spec.name
        self.status = spec.status
        self.role = spec.role
        self.function = spec.function
        self.party = spec.party
        self.home_area = spec.home_area
        self.location = spec.location
        self.persona = spec.persona
        self.member_ref = spec.member_ref
        self.house = spec.house or "commons"
        self.excerpts = list(spec.excerpts)
        self.backend = backend
        self.memory = MemoryStream()
        self.spatial = SpatialMemory()
        self.current_action = "wait"
        self.current_emoji = "•"
        self.destination = spec.location
        self.inbox_text: list[str] = []
        self.retrieved: list[str] = []
        self.last_refusal: str = ""
        self.n_refusals: int = 0
        self.utterance: str = ""
        self.relations: dict[str, float] = {}
        self.automaton = RoleAutomaton()
        self.wants_floor: bool = spec.status in {"MP", "Minister"}

    def perceive(self, world: "ChamberWorld") -> list[str]:
        if not world.cfg.enable_observation:
            return []
        tree = world.tree
        here = tree.subarea_of(self.location).id
        notes = [f"I am at {tree.path_string(here)}."]
        if world.sitting_open:
            house = "Eerste Kamer" if getattr(world, "sitting_house", "commons") == "senate" else "Tweede Kamer"
            notes.append(f"The sitting of the {house} is open.")
            if world.recognized:
                rec = world._agents.get(world.recognized)
                if rec:
                    notes.append(f"The Chair has given the floor to {rec.name}.")
        else:
            notes.append("The sitting is not in session.")
        for obj in world.objects.at_node(here):
            notes.append(f"I see that the {obj.describe()}.")
        others = world.agents_at(here, exclude=self.id)
        if others:
            names = ", ".join(f"{a.name} ({a.status})" for a in others[:6])
            notes.append(f"Also here: {names}.")
        if world.rumours:
            for rumour, speaker in world.rumours.pop_inbox(self.id):
                notes.append(f"{speaker} told me: {rumour.content}")
                if world.cfg.enable_dialogue_map:
                    self.spatial.learn_from_text(rumour.content, tree, True)
        for extra in self.inbox_text:
            notes.append(extra)
        self.inbox_text.clear()
        return notes

    def preferred_location(self, world: "ChamberWorld") -> str:
        sitting = world.sitting_open
        if self.status == "Chair":
            return "chair_dais" if sitting or 9 <= world.clock.hour < 18 else "corridor"
        if self.status == "Clerk":
            return "griffier_desk" if sitting else "corridor"
        if self.status == "Stenographer":
            return "stenographers" if sitting else "corridor"
        if self.status == "Minister":
            if sitting:
                return "ministers_bench"
            if world.clock.hour >= SITTING_CLOSE_HOUR:
                return "kolonien"
            return "corridor"
        if self.status == "Journalist":
            ungated = world.cfg.ga_baseline or not world.cfg.enable_affordance
            if ungated and sitting:
                return "centre_aisle"
            if world.clock.hour in {9, 13, 17, 18}:
                return "corridor"
            return "gallery_desk" if sitting else "corridor"
        if self.status == "Gallery":
            return "tribune" if sitting else "corridor"
        # MPs: benches during sitting, wandelgang around it, committee some hours
        if sitting:
            return "left_benches" if stable_mod(self.id, 2) == 0 else "right_benches"
        if world.clock.hour == 9 or world.clock.hour >= 17:
            return "corridor"
        if world.clock.hour >= 14 and not sitting:
            return "committee_a"
        return "corridor"

    def choose_action(self, world: "ChamberWorld") -> str:
        loc = world.tree.subarea_of(self.location).id
        hour = world.clock.hour
        if self.status == "Chair":
            if not world.sitting_open and hour == SITTING_OPEN_HOUR and world.clock.minute == 0:
                return "open_sitting"
            if world.sitting_open and hour == SITTING_CLOSE_HOUR and world.clock.minute == 0:
                return "adjourn"
            if world.sitting_open and world.recognized is None:
                # chair_strictness > 1: skip some recognitions (stricter order).
                step_mod = max(1, int(round(getattr(world.cfg, "chair_strictness", 1.0))))
                if world.clock.step % step_mod == 0:
                    return "recognize"
                return "wait"
            return "wait"
        if self.status == "Clerk":
            return "read_kamerstuk" if world.sitting_open else "wait"
        if self.status == "Stenographer":
            return "record" if world.sitting_open else "wait"
        ungated = world.cfg.ga_baseline or not world.cfg.enable_affordance
        if self.status == "Journalist":
            if ungated and world.sitting_open:
                return "speak"
            return "take_notes" if loc == "gallery_desk" else "talk"
        if self.status in {"MP", "Minister"}:
            if world.sitting_open and (world.recognized == self.id or ungated):
                return "speak"
            if world.sitting_open and self.wants_floor and loc in {
                "left_benches",
                "right_benches",
                "ministers_bench",
                "centre_aisle",
            }:
                return "request_floor"
            if loc == "committee_a":
                return "speak"
            if loc == "corridor":
                return "talk"
            return "wait"
        return "wait"

    def _uses_llm(self) -> bool:
        return getattr(self.backend, "name", "") == "openai_compat" and bool(getattr(self.backend, "api_key", ""))

    def _llm_budget_left(self) -> bool:
        cap = int(getattr(self.backend, "utter_cap", 0) or 0)
        if cap <= 0:
            return True
        # n_calls counts cache misses only, so a warm cache can replay a full week.
        return int(getattr(self.backend, "n_calls", 0)) < cap

    def compose_speech(self, world: "ChamberWorld") -> str:
        base = self.heuristic_speech(world)
        if not self._uses_llm() or not self._llm_budget_left():
            return base
        retrieved = " ".join(m.text for m in self.memory.items[-6:])
        leak = (
            "You have heard a corridor rumour that the Minister of Colonies may resign "
            "over an East Indies deficit. Allude to it only if you would dare on the floor."
            if world.rumours and world.rumours.aware(self.id, "leak")
            else "Do not invent a resignation rumour."
        )
        text = self.backend.complete(
            f"{self.persona}\nRole: {self.status}. Location: {self.location}. "
            f"Sitting open: {world.sitting_open}. Recognised: {world.recognized == self.id}.\n"
            f"Memories: {retrieved[:400]}\n{leak}\n"
            "Write one floor utterance addressed to the Voorzitter, in period Dutch if you can. "
            "Do not claim a journalist is speaking on the record unless your role is Journalist "
            "and standing orders have been lifted."
        )
        return (text or base)[:480]

    def compose_talk(self, world: "ChamberWorld", other: "Agent | None" = None) -> str:
        fallback = "Wij spraken in de wandelgang over de begrooting."
        if not self._uses_llm() or not self._llm_budget_left():
            return fallback
        retrieved = " ".join(m.text for m in self.memory.items[-6:])
        rumour = ""
        if world.rumours and world.rumours.aware(self.id, "leak"):
            rumour = "the Minister of Colonies may resign over the East Indies budget"
        partner = other.name if other else "a colleague"
        text = self.backend.complete(
            f"{self.persona}\nQuiet wandelgang remark to {partner}.\n"
            f"Memories: {retrieved[:300]}\nRumour if any: {rumour}\n"
            "One spoken aside, not for the Handelingen."
        )[:360] or fallback
        return text

    def heuristic_speech(self, world: "ChamberWorld") -> str:
        # Corridor leaks almost never enter the official record: a rare veiled aside.
        leak = ""
        strict = max(0.25, float(getattr(world.cfg, "chair_strictness", 1.0)))
        # Higher strictness → rarer allusions to corridor talk on the floor.
        bucket = max(2, int(round(12 * strict)))
        if (
            world.rumours
            and world.rumours.aware(self.id, "leak")
            and self.status in {"MP", "Journalist"}
            and stable_mod(f"{self.id}:{world.clock.day_index()}", bucket) == 0
        ):
            leak = " Zonder de geruchten uit de wandelgang te willen bevestigen, vraag ik of de begrooting sluit."
        if self.excerpts:
            seed = self.excerpts[0][:220]
            return f"Mijnheer de Voorzitter! {seed}{leak}"
        if self.status == "Minister":
            return (
                "Mijnheer de Voorzitter! De Regeering handhaaft het ontwerp. "
                "Het belang van de kolonie gedoogt geen verder uitstel."
            )
        if self.status == "Chair":
            return "Ik geef het woord aan den volgenden spreker."
        return f"Mijnheer de Voorzitter! Ik wensch een opmerking te maken over het Kamerstuk.{leak}"

    def step(self, world: "ChamberWorld") -> dict[str, Any]:
        notes = self.perceive(world)
        for n in notes:
            self.memory.add(n, world.clock.step, importance=4, kind="observation")
        dest = self.preferred_location(world)
        if dest != world.tree.subarea_of(self.location).id:
            result = check_action(self, "move", dest, world)
            if result.allowed:
                self.location = dest
                self.spatial.know(dest, "visit")
                self.current_action = "move"
            else:
                self.last_refusal = result.refusal_text()
                self.n_refusals += 1
                self.memory.add(self.last_refusal, world.clock.step, importance=6, kind="refusal")
                self.current_action = "wait"
        action = self.choose_action(world)
        loc = world.tree.subarea_of(self.location).id
        for _ in range(MAX_REPLAN):
            result = check_action(self, action, loc, world)
            if result.allowed:
                break
            self.last_refusal = result.refusal_text()
            self.n_refusals += 1
            self.memory.add(self.last_refusal, world.clock.step, importance=7, kind="refusal")
            action = "wait"
        else:
            action = "wait"
        self.current_action = action
        self.current_emoji = EMOJI.get(action, "•")
        self.utterance = ""
        if action == "speak":
            self.utterance = self.compose_speech(world)
            self.memory.add(f"I said: {self.utterance[:180]}", world.clock.step, importance=8, kind="speech")
        elif action == "talk":
            self.utterance = self.compose_talk(world)
        elif action == "open_sitting":
            world.sitting_open = True
            world.objects.get("gavel").set_state("opening")
            world.record("open_sitting", chair=self.id)
        elif action == "adjourn":
            world.sitting_open = False
            world.recognized = None
            world.objects.get("gavel").set_state("adjourned")
            world.record("adjourn", chair=self.id)
        elif action == "recognize":
            candidates = [
                a
                for a in world._agents.values()
                if a.status in {"MP", "Minister"} and a.wants_floor and a.id != self.id
            ]
            if candidates:
                pick = candidates[world.clock.step % len(candidates)]
                world.recognized = pick.id
                world.record("recognize", chair=self.id, speaker=pick.id)
                self.utterance = f"Het woord is aan den heer {pick.name}."
        return {
            "id": self.id,
            "action": action,
            "loc": loc,
            "utterance": self.utterance,
        }

    def talk_with(self, other: "Agent", world: "ChamberWorld") -> None:
        self.relations[other.id] = self.relations.get(other.id, 0.0) + 0.05
        other.relations[self.id] = other.relations.get(self.id, 0.0) + 0.05
        line = self.compose_talk(world, other)
        self.utterance = line
        self.memory.add(f"I told {other.name}: {line[:160]}", world.clock.step, importance=5, kind="dialogue")
        other.memory.add(f"{self.name} said: {line[:160]}", world.clock.step, importance=5, kind="dialogue")

    def inspect(self, world: "ChamberWorld") -> dict[str, Any]:
        loc = world.tree.subarea_of(self.location).id
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "role": self.role,
            "function": self.function,
            "party": self.party,
            "location": world.tree.path_string(loc),
            "action": self.current_action,
            "emoji": self.current_emoji,
            "utterance": self.utterance,
            "last_refusal": self.last_refusal,
            "memories": [m.text for m in self.memory.items[-8:]],
            "stratum": stratum(self.status),
        }
