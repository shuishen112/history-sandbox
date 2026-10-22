"""Parse PoliticalMashup DutchParl XML (Marx et al., DANS doi:10.17026/DANS-XK5-DW3S)."""
from __future__ import annotations

import collections
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator
from xml.etree import ElementTree as ET

NS = {
    "pm": "http://www.politicalmashup.nl",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}

DEFAULT_ZIP = Path("Dutch Parliamentary debates (XML).zip")
BEKENDMAKINGEN = "https://zoek.officielebekendmakingen.nl"
ID_IN_NAME = re.compile(r"id\s+(\d{6,})", re.I)


def bekendmakingen_id(path: str) -> str:
    """Officiele Bekendmakingen id from a DutchParl filename (… id 0000379998.xml)."""
    m = ID_IN_NAME.search(path.split("/")[-1])
    return m.group(1) if m else ""


def bekendmakingen_url(ident: str) -> str:
    return f"{BEKENDMAKINGEN}/{ident}" if ident else ""


@dataclass
class Speech:
    sitting_id: str
    date: str
    house: str
    speaker: str
    role: str
    function: str
    party: str
    member_ref: str
    text: str
    topic: str


@dataclass
class Sitting:
    path: str
    identifier: str
    date: str
    title: str
    house: str
    period: str
    n_speeches: int = 0
    speakers: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def iter_sittings(zip_path: Path | str = DEFAULT_ZIP) -> Iterator[tuple[str, bytes]]:
    z = zipfile.ZipFile(zip_path)
    for name in z.namelist():
        if name.endswith(".xml"):
            yield name, z.read(name)


def parse_sitting(xml_bytes: bytes, path: str = "") -> tuple[Sitting, list[Speech]]:
    root = ET.fromstring(xml_bytes)
    ident = _text(root.find(".//{http://purl.org/dc/elements/1.1/}identifier"))
    date = _text(root.find(".//{http://purl.org/dc/elements/1.1/}date"))
    title = _text(root.find(".//{http://purl.org/dc/elements/1.1/}title"))
    house_el = root.find(".//{http://www.politicalmashup.nl}house")
    house = (house_el.get("{http://www.politicalmashup.nl}house") if house_el is not None else "") or ""
    period_el = root.find(".//{http://www.politicalmashup.nl}legislative-period")
    period = _text(period_el)
    sitting = Sitting(
        path=path,
        identifier=ident,
        date=date,
        title=title,
        house=house,
        period=period,
    )
    speeches: list[Speech] = []
    for sp in root.iter():
        if _local(sp.tag) != "speech":
            continue
        speaker = sp.get("{http://www.politicalmashup.nl}speaker") or ""
        role = sp.get("{http://www.politicalmashup.nl}role") or ""
        function = sp.get("{http://www.politicalmashup.nl}function") or ""
        party = sp.get("{http://www.politicalmashup.nl}party-ref") or ""
        member = sp.get("{http://www.politicalmashup.nl}member-ref") or ""
        topic = ""
        paras = [
            " ".join("".join(p.itertext()).split())
            for p in sp
            if _local(p.tag) == "p"
        ]
        text = " ".join(t for t in paras if t)
        if not speaker:
            continue
        speeches.append(
            Speech(
                sitting_id=ident,
                date=date,
                house=house,
                speaker=speaker,
                role=role,
                function=function,
                party=party,
                member_ref=member,
                text=text,
                topic=topic,
            )
        )
        sitting.speakers.append(speaker)
    sitting.n_speeches = len(speeches)
    return sitting, speeches


def corpus_stats(zip_path: Path | str = DEFAULT_ZIP, year_min: int = 1814, year_max: int = 1899) -> dict:
    n_files = 0
    n_speech = 0
    n_with_speech = 0
    houses: collections.Counter[str] = collections.Counter()
    years: collections.Counter[str] = collections.Counter()
    roles: collections.Counter[str] = collections.Counter()
    parties: collections.Counter[str] = collections.Counter()
    speakers: set[str] = set()
    members: set[str] = set()
    year_re = re.compile(r"(\d{4})-")
    speaker_re = re.compile(rb'pm:speaker="([^"]+)"')
    role_re = re.compile(rb'pm:role="([^"]+)"')
    party_re = re.compile(rb'pm:party-ref="([^"]+)"')
    member_re = re.compile(rb'pm:member-ref="([^"]+)"')
    house_re = re.compile(rb'pm:house="([^"]+)"')

    for name, data in iter_sittings(zip_path):
        ym = year_re.search(name.split("/")[-1])
        year = int(ym.group(1)) if ym else 0
        if year and (year < year_min or year > year_max):
            continue
        n_files += 1
        k = data.count(b"<speech ")
        n_speech += k
        if k:
            n_with_speech += 1
        if year:
            years[str(year)] += 1
        hm = house_re.search(data)
        houses[hm.group(1).decode("utf-8", "replace") if hm else "other"] += 1
        for m in speaker_re.finditer(data):
            speakers.add(m.group(1).decode("utf-8", "replace"))
        for m in role_re.finditer(data):
            roles[m.group(1).decode("utf-8", "replace")] += 1
        for m in party_re.finditer(data):
            parties[m.group(1).decode("utf-8", "replace")] += 1
        for m in member_re.finditer(data):
            ref = m.group(1).decode("utf-8", "replace")
            if ref:
                members.add(ref)

    decades: collections.Counter[str] = collections.Counter()
    for y, c in years.items():
        decades[y[:3] + "0s"] += c
    return {
        "n_sittings": n_files,
        "n_speeches": n_speech,
        "n_sittings_with_speech": n_with_speech,
        "n_speakers": len(speakers),
        "n_member_refs": len(members),
        "houses": dict(houses),
        "roles": dict(roles.most_common()),
        "parties": dict(parties.most_common()),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "n_years": len(years),
        "decades": dict(sorted(decades.items())),
        "source": "Dutch Parliamentary Proceedings 1814–2012 (non-semanticized), doi:10.17026/DANS-XK5-DW3S",
        "slice": f"{year_min}–{year_max}",
        "license": "CC0-1.0",
    }


def sample_roster(
    zip_path: Path | str = DEFAULT_ZIP,
    year_min: int = 1896,
    year_max: int = 1899,
    house: str = "commons",
    max_sittings: int = 80,
    max_chars: int = 400,
) -> list[dict]:
    """Build persona seeds from attested speakers in a late-19th-century slice."""
    by_speaker: dict[str, dict] = {}
    n = 0
    for name, data in iter_sittings(zip_path):
        ym = re.search(r"(\d{4})-", name.split("/")[-1])
        if not ym:
            continue
        year = int(ym.group(1))
        if year < year_min or year > year_max:
            continue
        if house == "commons" and b'pm:house="commons"' not in data and "Tweede Kamer" not in name:
            continue
        if house == "senate" and b'pm:house="senate"' not in data:
            continue
        sitting, speeches = parse_sitting(data, name)
        n += 1
        for sp in speeches:
            rec = by_speaker.setdefault(
                sp.speaker,
                {
                    "name": sp.speaker,
                    "role": sp.role or "mp",
                    "function": sp.function,
                    "party": sp.party,
                    "member_ref": sp.member_ref,
                    "house": sp.house or house,
                    "n_speeches": 0,
                    "excerpts": [],
                    "excerpt_meta": [],
                },
            )
            rec["n_speeches"] += 1
            if len(rec["excerpts"]) < 3 and len(sp.text) > 80:
                ident = bekendmakingen_id(name)
                rec["excerpts"].append(sp.text[:max_chars])
                rec["excerpt_meta"].append(
                    {
                        "identifier": ident,
                        "url": bekendmakingen_url(ident),
                        "source": name.split("/")[-1],
                        "date": sitting.date,
                    }
                )
            if sp.party:
                rec["party"] = sp.party
            if sp.member_ref:
                rec["member_ref"] = sp.member_ref
        if n >= max_sittings:
            break
    roster = sorted(by_speaker.values(), key=lambda r: -r["n_speeches"])
    return roster


def dump_stats(out_dir: Path | str = "data") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stats = corpus_stats()
    (out / "corpus_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    roster = sample_roster()
    (out / "speakers.json").write_text(json.dumps(roster, indent=2, ensure_ascii=False), encoding="utf-8")
    print("stats", stats["n_sittings"], "speeches", stats["n_speeches"], "roster", len(roster))


if __name__ == "__main__":
    dump_stats()
