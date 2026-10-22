"""Seed N agents from attested DutchParl speakers (public office-holders)."""

from __future__ import annotations

import json
from pathlib import Path

from maroon.agents.llm import CognitiveBackend

from kamer.agents.agent import Agent, AgentState
from kamer.config import SimConfig
from kamer.world.binnenhof import ChamberWorld

FALLBACK_ROSTER = [
    {"name": "van Naamen van Eemnes", "role": "chair", "function": "voorzitter", "party": "", "excerpts": []},
    {"name": "Cremer", "role": "government", "function": "minister van Koloniën", "party": "nl.p.lu", "excerpts": []},
    {"name": "Goeman Borgesius", "role": "government", "function": "minister van Binnenlandsche Zaken", "party": "nl.p.lu", "excerpts": []},
    {"name": "van Asch van Wijck", "role": "mp", "function": "De heer", "party": "nl.p.arp", "excerpts": []},
    {"name": "Pijnacker Hordijk", "role": "mp", "function": "De heer", "party": "", "excerpts": []},
    {"name": "Rahusen", "role": "mp", "function": "De heer", "party": "", "excerpts": []},
    {"name": "de Jong", "role": "mp", "function": "De heer", "party": "", "excerpts": []},
    {"name": "Cort van der Linden", "role": "government", "function": "minister", "party": "", "excerpts": []},
]

# S1 t0 is December 1899 (Pierson cabinet, 1897–1901). The 1896–99 speaker
# dump ranks Röell-cabinet ministers first; override from the historian review.
PIERSON_1899_MINISTERS = {
    "Cremer": {
        "role": "government",
        "function": "minister van Koloniën",
        "party": "nl.p.lu",
    },
    "Goeman Borgesius": {
        "role": "government",
        "function": "minister van Binnenlandsche Zaken",
        "party": "nl.p.lu",
    },
}
NOT_IN_OFFICE_DEC_1899 = {
    "van Houten",  # Interior until 1897
    "Sprenger van Eyk",  # Finance until 1897
    "Gerritsen",  # left the Kamer in 1897
}
PARTY_1899 = {
    "Goeman Borgesius": "nl.p.lu",
    "de Beaufort": "nl.p.liberaal",
    "Smeenge": "nl.p.liberaal",
    "Bahlmann": "nl.p.roomskatholieken",
    "van Vlijmen": "nl.p.roomskatholieken",
    "Beelaerts van Blokland": "nl.p.arp",
}


def _role_status(raw: str) -> str:
    raw = (raw or "mp").lower()
    if raw in {"chair", "voorzitter"}:
        return "Chair"
    if raw in {"government", "minister"}:
        return "Minister"
    return "MP"


HOME = {
    "Chair": "chair_dais",
    "MP": "left_benches",
    "Minister": "ministers_bench",
    "Clerk": "griffier_desk",
    "Journalist": "gallery_desk",
    "Gallery": "tribune",
}

HOUSE_NL = {"commons": "Tweede Kamer", "senate": "Eerste Kamer", "both": "beide Kamers"}
STATUS_NL = {
    "Chair": "Voorzitter",
    "MP": "Kamerlid",
    "Minister": "minister",
    "Clerk": "griffier",
    "Journalist": "verslaggever",
    "Gallery": "toehoorder",
}


def load_roster(path: Path | str = "data/speakers.json") -> list[dict]:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return FALLBACK_ROSTER


def _apply_period(rec: dict) -> dict | None:
    """Drop people not in office at S1 t0; promote Pierson-cabinet ministers."""
    name = rec.get("name") or ""
    if name in NOT_IN_OFFICE_DEC_1899:
        return None
    out = dict(rec)
    if name in PIERSON_1899_MINISTERS:
        out.update(PIERSON_1899_MINISTERS[name])
    if name in PARTY_1899:
        out["party"] = PARTY_1899[name]
    return out


def build_population(world: ChamberWorld, backend: CognitiveBackend, n: int = 25) -> list[Agent]:
    roster = [r for r in (_apply_period(x) for x in load_roster()) if r]
    agents: list[Agent] = []

    def make(i: int, rec: dict, status: str) -> Agent:
        house = rec.get("house") or (
            "both" if status == "Minister" else "none" if status == "Journalist" else world.cfg.house
        )
        if status == "Chair" and house == "senate":
            home = "ek_chair"
        elif status == "MP" and house == "senate":
            home = "ek_benches"
        else:
            home = HOME[status]
        name = rec.get("name") or f"Lid {i}"
        role_nl = STATUS_NL.get(status, status)
        kamer = HOUSE_NL.get(house, "Tweede Kamer")
        persona = (
            f"{rec.get('function', 'De heer')} {name} is {role_nl} der {kamer} "
            f"({world.cfg.period}). Partij: {rec.get('party') or 'zonder partij'}. "
            "Het publieke woord, zoo het op de vloer klinkt, is tot den Voorzitter gericht."
        )
        spec = AgentState(
            id=f"a{i:03d}",
            name=name,
            status=status,
            role=status.lower(),
            function=rec.get("function") or ("voorzitter" if status == "Chair" else "De heer"),
            party=rec.get("party") or "",
            home_area=home,
            location=home,
            persona=persona,
            member_ref=rec.get("member_ref") or "",
            house=house,
            excerpts=[
                (e.get("text") if isinstance(e, dict) else e) or ""
                for e in (rec.get("excerpts") or [])
            ],
        )
        return Agent(spec, backend)

    chairs = [r for r in roster if _role_status(r.get("role", "")) == "Chair"]
    ministers = [r for r in roster if _role_status(r.get("role", "")) == "Minister"]
    mps = [r for r in roster if _role_status(r.get("role", "")) == "MP"]
    # Prefer named Pierson ministers even if the dump still tagged them as mp.
    preferred = [r for r in roster if r.get("name") in PIERSON_1899_MINISTERS]
    if preferred:
        ministers = preferred + [m for m in ministers if m.get("name") not in PIERSON_1899_MINISTERS]
    if not chairs:
        chairs = [{"name": "van Naamen van Eemnes", "role": "chair", "function": "voorzitter", "party": ""}]
    if not ministers:
        ministers = FALLBACK_ROSTER[1:3]
    if not mps:
        mps = FALLBACK_ROSTER[3:]
    minister_names = {m.get("name") for m in ministers[:2]}
    mps = [r for r in mps if r.get("name") not in minister_names]

    agents.append(make(0, chairs[0], "Chair"))
    agents.append(make(1, {"name": "Arntzenius", "function": "griffier", "role": "clerk"}, "Clerk"))
    agents.append(make(2, {"name": "Verslaggever van de Courant", "function": "journalist", "role": "journalist"}, "Journalist"))
    i = 3
    for rec in ministers[:2]:
        agents.append(make(i, rec, "Minister"))
        i += 1
    for rec in mps:
        if len(agents) >= n:
            break
        agents.append(make(i, rec, "MP"))
        i += 1
    while len(agents) < n:
        agents.append(make(i, {"name": f"Lid {i}", "function": "De heer", "role": "mp"}, "MP"))
        i += 1
    return agents[:n]
