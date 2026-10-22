"""In-world stenographers: the observation model for simulated Handelingen.

Only recognised floor speech is written. Corridor talk, committee asides,
and press-gallery notes never enter Y^t unless a journalist later prints
them as a leak — which is a different channel, not the official record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kamer.world.binnenhof import ChamberWorld


@dataclass
class ProceedingsPage:
    date: str
    house: str
    lines: list[dict[str, Any]] = field(default_factory=list)

    def as_text(self) -> str:
        bits = [f"HANDELINGEN — {self.house} — {self.date}"]
        for line in self.lines:
            bits.append(f"{line.get('speaker', '?')} ({line.get('function', '')}): {line.get('text', '')}")
        return "\n".join(bits)


class Stenographers:
    def __init__(self) -> None:
        self.pages: list[ProceedingsPage] = []
        self.current: ProceedingsPage | None = None

    def open_sitting(self, world: ChamberWorld) -> None:
        house = "Eerste Kamer" if getattr(world, "sitting_house", "commons") == "senate" else "Tweede Kamer"
        self.current = ProceedingsPage(date=world.clock.iso(), house=house)
        world.objects.get("stenograph").set_state("recording", page=len(self.pages) + 1)

    def close_sitting(self, world: ChamberWorld) -> None:
        if self.current and self.current.lines:
            self.pages.append(self.current)
        self.current = None
        world.objects.get("stenograph").set_state("idle")

    def record_speech(self, world: ChamberWorld, agent: Any, text: str) -> bool:
        """π: record iff sitting is open, speaker is recognised (or is Chair), location on record."""
        if self.current is None or not world.sitting_open:
            return False
        ungated = world.cfg.ga_baseline or not world.cfg.enable_affordance
        if not ungated:
            # Stenographer π: recognised floor speech and the Chair's rulings.
            # Asides / unrecognised interruptions are omitted unless the recognised
            # speaker responds (they then count as part of that speech).
            if agent.status not in {"Chair", "MP", "Minister"}:
                return False
            if agent.status != "Chair" and world.recognized != agent.id:
                return False
        loc = world.tree.subarea_of(agent.location).id
        if not ungated and not world.is_on_record(loc):
            return False
        self.current.lines.append(
            {
                "speaker": agent.name,
                "role": agent.status,
                "function": getattr(agent, "function", ""),
                "party": getattr(agent, "party", ""),
                "text": text,
                "step": world.clock.step,
            }
        )
        world.record("handelingen", speaker=agent.id, text=text[:240])
        return True

    def latest_text(self) -> str:
        if self.current and self.current.lines:
            return self.current.as_text()
        if self.pages:
            return self.pages[-1].as_text()
        return ""
