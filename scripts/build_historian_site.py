#!/usr/bin/env python3
"""Build the static Kamer historian-labelling site (GitHub Pages).

Writes historian-site/data/*.json:
  interviews.json  — blinded pairwise TrueSkill pack
  speakers.json    — OCR / persona review items
  procedure.json   — floor-rights / stenographer items
  codebook.json    — on-page instructions

Interview answers come from a short S1 pause-and-interview (2 days) across
full / ga / no_affordance / no_rumour. Cached under
historian-site/data/interviews_raw.json so the pack can be rebuilt quickly.
"""

from __future__ import annotations

import json
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "historian-site"
DATA = OUT / "data"

PRESETS = ["full", "ga", "no_affordance", "no_rumour"]
DAYS = 2
SEED = 7
N_AGENTS = 25
N_PAIRS = 40
N_SPEAKERS = 40
N_PROCEDURE = 18

QUESTIONS = {
    "self-knowledge": "Wie bent u, en welke functie bekleedt u in de Kamer?",
    "memory": "Wat hebt u deze week in de wandelgang of op de vloer vernomen?",
    "plans": "Wat zult u morgen tijdens de vergadering doen?",
    "reactions": "U wilt het woord, maar de Voorzitter herkent u niet. Wat doet u?",
    "reflections": "Waarover hebt u de laatste dagen nagedacht?",
    "institutional_awareness": (
        "Mag een journalist het woord voeren op de vloer? "
        "En een lid, zonder erkenning van de Voorzitter?"
    ),
}

CATEGORIES = list(QUESTIONS)


def excerpt_text(e) -> str:
    if isinstance(e, dict):
        return e.get("text") or ""
    return str(e or "")


def _ocr_noise(text: str) -> int:
    if not text:
        return 0
    return len(
        re.findall(
            r"[\\|!•>]|[A-Z]{4,}|[a-z][A-Z]|[A-Za-z]\s[A-Za-z]\s|[0-9]{2}\s[A-Z]{3}",
            text,
        )
    ) + text.count("  ")


def collect_interviews(cache: Path) -> dict[str, dict]:
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        if all(p in raw for p in PRESETS):
            print("using cached interviews", cache)
            return raw

    from kamer.config import SimConfig
    from kamer.eval.interview import run_interviews
    from kamer.sim.engine import Simulation

    raw: dict[str, dict] = {}
    for preset in PRESETS:
        print(f"interview run {preset}…", flush=True)
        cfg = SimConfig(seed=SEED, n_agents=N_AGENTS, n_days=DAYS).apply_preset(preset)
        sim = Simulation(cfg)
        sim.seed_leak()
        sim.run_days(DAYS)
        pack = run_interviews(sim, N_AGENTS)
        lines = []
        for page in sim.press.pages:
            lines.extend(page.lines)
        raw[preset] = {
            "rows": pack["rows"],
            "mean_procedural": pack["mean_procedural"],
            "n_lines": len(lines),
            "sample_lines": lines[:40],
        }
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw


LLM_PACK = ROOT / "runs/kamer/s1_llm.json"
LLM_PERIOD_PACK = ROOT / "runs/kamer/s1_llm_period.json"


def _norm_answer(s: str) -> str:
    return " ".join((s or "").split()).casefold()


_VOCATIVE = re.compile(
    r"^\s*(mijnheer|mynheer|meneer|waarde|geachte|edelachtbare)\s+"
    r"(de\s+)?voorzitter\s*[,!.]?\s*",
    re.I,
)


def strip_floor_vocative(text: str) -> str:
    """Interview answers are off-record; drop floor-speech openings."""
    t = (text or "").strip()
    t = _VOCATIVE.sub("", t).lstrip()
    if t:
        t = t[0].upper() + t[1:]
    return t


def load_llm_interviews() -> dict[str, dict]:
    """{condition: {agent_id: interview row}} from the LLM S1 run, if present."""
    pack = LLM_PERIOD_PACK if LLM_PERIOD_PACK.exists() else LLM_PACK
    if not pack.exists():
        return {}
    print("interview source", pack)
    blob = json.loads(pack.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for r in blob.get("runs") or []:
        rows = (r.get("interviews") or {}).get("rows") or []
        if not rows:
            continue
        key = f"{r.get('preset', 'full')}_llm"
        out[key] = {row["id"]: row for row in rows}
    return out


def interview_pairs(raw: dict[str, dict], rng: random.Random, llm_rows: dict[str, dict] | None = None) -> list[dict]:
    if llm_rows:
        by_cond = llm_rows
        contrasts = [("full_llm", "ga_llm")] if "full_llm" in by_cond and "ga_llm" in by_cond else [
            (a, b) for a in by_cond for b in by_cond if a < b
        ]
    else:
        by_cond = {p: {r["id"]: r for r in raw[p]["rows"]} for p in PRESETS}
        # Heuristic ga and no_affordance share the same ungated template — do not pair them.
        contrasts = [("full", "ga"), ("full", "no_rumour")]
    ids = sorted(set.intersection(*[set(v) for v in by_cond.values()])) if by_cond else []
    # Prefer a mix of roles: Chair/Journalist/Clerk are scarce but procedurally informative.
    home = next(iter(by_cond))
    def role_of(aid: str) -> str:
        return (by_cond[home].get(aid) or {}).get("status") or "MP"
    ids.sort(key=lambda i: ({"Chair": 0, "Journalist": 1, "Clerk": 2, "Minister": 3}.get(role_of(i), 4), i))
    pairs: list[dict] = []
    n = 0
    per_cat = {c: 0 for c in CATEGORIES}
    cap_per_cat = max(4, N_PAIRS // max(1, len(CATEGORIES)))
    for aid in ids:
        for cat in CATEGORIES:
            if n >= N_PAIRS:
                break
            if per_cat[cat] >= cap_per_cat:
                continue
            a, b = contrasts[n % len(contrasts)]
            if aid not in by_cond[a] or aid not in by_cond[b]:
                continue
            ra, rb = by_cond[a][aid], by_cond[b][aid]
            qa = strip_floor_vocative((ra["answers"].get(cat) or [""])[0])
            qb = strip_floor_vocative((rb["answers"].get(cat) or [""])[0])
            if not qa.strip() or not qb.strip():
                continue
            if _norm_answer(qa) == _norm_answer(qb):
                continue
            left, right = (qa, a, ra), (qb, b, rb)
            if rng.random() < 0.5:
                left, right = right, left
            pairs.append(
                {
                    "id": f"pair-{n:03d}",
                    "agent_id": aid,
                    "role": ra["status"],
                    "category": cat,
                    "question": QUESTIONS[cat],
                    "left": {"text": left[0], "hidden": left[1]},
                    "right": {"text": right[0], "hidden": right[1]},
                    "catch": False,
                }
            )
            n += 1
            per_cat[cat] += 1
        if n >= N_PAIRS:
            break

    # Two attention checks: one side is an obvious anachronism.
    if ids:
        aid = ids[0]
        home = "full_llm" if "full_llm" in by_cond else "full"
        row = by_cond[home][aid]
        pairs.append(
            {
                "id": "pair-catch-modern",
                "agent_id": aid,
                "role": row["status"],
                "category": "institutional_awareness",
                "question": QUESTIONS["institutional_awareness"],
                "left": {
                    "text": (
                        "Sure, anyone can grab the mic — I'll just tweet the leak "
                        "and livestream the sitting from my phone."
                    ),
                    "hidden": "catch_anachronism",
                },
                "right": {
                    "text": (row["answers"]["institutional_awareness"] or [""])[0],
                    "hidden": home,
                },
                "catch": True,
            }
        )
        pairs.append(
            {
                "id": "pair-catch-empty",
                "agent_id": ids[-1],
                "role": by_cond[home][ids[-1]]["status"],
                "category": "self-knowledge",
                "question": QUESTIONS["self-knowledge"],
                "left": {
                    "text": (by_cond[home][ids[-1]]["answers"]["self-knowledge"] or [""])[0],
                    "hidden": home,
                },
                "right": {
                    "text": "I am a large language model trained by a 21st-century lab.",
                    "hidden": "catch_anachronism",
                },
                "catch": True,
            }
        )
    rng.shuffle(pairs)
    return pairs


def speaker_items(rng: random.Random) -> list[dict]:
    roster = json.loads((ROOT / "data" / "speakers.json").read_text(encoding="utf-8"))
    by_role: dict[str, list] = defaultdict(list)
    for rec in roster:
        by_role[rec.get("role") or "mp"].append(rec)
    for recs in by_role.values():
        recs.sort(key=lambda r: -_ocr_noise(" ".join(excerpt_text(e) for e in (r.get("excerpts") or []))))

    picked: list[dict] = []
    quotas = {"chair": 3, "government": 10, "mp": 25}
    for role, k in quotas.items():
        pool = by_role.get(role) or []
        take = pool[:k] if len(pool) >= k else pool
        # mix a few cleaner controls
        if len(pool) > k + 4:
            take = pool[: max(1, k - 3)] + rng.sample(pool[k:], min(3, len(pool) - k))
        for rec in take:
            picked.append(_speaker_card(rec, synthetic=False))

    picked.append(
        _speaker_card(
            {
                "name": "Verslaggever van de Courant",
                "role": "journalist",
                "function": "journalist",
                "party": "",
                "member_ref": "",
                "house": "commons",
                "n_speeches": 0,
                "excerpts": [
                    "Synthetic press-gallery persona. Not attested in the Handelingen."
                ],
            },
            synthetic=True,
        )
    )
    picked.append(
        _speaker_card(
            {
                "name": "Griffier",
                "role": "clerk",
                "function": "griffier",
                "party": "",
                "member_ref": "",
                "house": "commons",
                "n_speeches": 0,
                "excerpts": ["Synthetic clerk. The XML names a griffier; this card is a role seed."],
            },
            synthetic=True,
        )
    )
    picked.append(
        _speaker_card(
            {
                "name": "Alex Rivera (2024 intern)",
                "role": "mp",
                "function": "De heer",
                "party": "nl.p.fake",
                "member_ref": "",
                "house": "commons",
                "n_speeches": 0,
                "excerpts": [
                    "Attention check: this person is not a nineteenth-century Kamerlid."
                ],
            },
            synthetic=True,
            catch=True,
        )
    )
    rng.shuffle(picked)
    return picked[: N_SPEAKERS + 3]


def _speaker_card(rec: dict, synthetic: bool, catch: bool = False) -> dict:
    party = rec.get("party") or ""
    party_short = party.split(".")[-1] if party else ""
    meta = list(rec.get("excerpt_meta") or [])
    excerpts = []
    for i, raw in enumerate(list(rec.get("excerpts") or [])[:3]):
        if isinstance(raw, dict):
            excerpts.append(raw)
            continue
        info = meta[i] if i < len(meta) else {}
        ident = info.get("identifier") or ""
        excerpts.append(
            {
                "text": excerpt_text(raw),
                "identifier": ident,
                "url": info.get("url") or (f"https://zoek.officielebekendmakingen.nl/{ident}" if ident else ""),
                "source": info.get("source") or "",
                "date": info.get("date") or "",
            }
        )
    return {
        "id": f"spk-{rec.get('member_ref') or rec.get('name', 'x')}".replace(" ", "_"),
        "name": rec.get("name") or "",
        "suggested_role": rec.get("role") or "mp",
        "suggested_function": rec.get("function") or "",
        "suggested_party": party,
        "party_label": party_short,
        "member_ref": rec.get("member_ref") or "",
        "house": rec.get("house") or "commons",
        "n_speeches": rec.get("n_speeches") or 0,
        "excerpts": excerpts,
        "synthetic": synthetic,
        "catch": catch,
        "ocr_noise": max((_ocr_noise(excerpt_text(e)) for e in excerpts or [""]), default=0),
    }


def procedure_items(raw: dict[str, dict], speakers: list[dict], rng: random.Random) -> list[dict]:
    items: list[dict] = []
    n = 0

    def add(**kw) -> None:
        nonlocal n
        items.append({"id": f"proc-{n:03d}", **kw})
        n += 1

    # Archive excerpts: should be in order and on the record.
    archival = [s for s in speakers if not s.get("synthetic") and s.get("excerpts")]
    rng.shuffle(archival)
    for rec in archival[:6]:
        add(
            source="archive",
            hidden="archive",
            setting="Tweede Kamer, sitting open, 1896–1899 (archival Handelingen excerpt)",
            actor_role=rec["suggested_role"],
            actor_name=rec["name"],
            action="speaks after recognition (source claims this was recorded)",
            text=excerpt_text(rec["excerpts"][0])[:420],
            catch=False,
        )

    # Simulated official lines from full vs ga.
    for preset, label in (("full", "simulated Handelingen, standing orders on"), ("ga", "simulated record, Smallville-style (no standing orders)")):
        lines = raw.get(preset, {}).get("sample_lines") or []
        rng.shuffle(lines)
        for ln in lines[:4]:
            add(
                source="simulation",
                hidden=preset,
                setting=f"Simulated Tweede Kamer floor, December 1899 — {label}",
                actor_role=ln.get("role") or "MP",
                actor_name=ln.get("speaker") or "?",
                action="line written into the simulated Handelingen",
                text=(ln.get("text") or "")[:420],
                catch=False,
            )

    add(
        source="vignette",
        hidden="vignette_journalist",
        setting="Tweede Kamer floor, sitting open, 1899",
        actor_role="Journalist",
        actor_name="(press gallery)",
        action="rises from the perstribune and addresses the Chair about a colonial deficit",
        text="Mijnheer de Voorzitter! De Courant heeft uit de wandelgang vernomen dat de Minister van Koloniën aftreedt.",
        catch=False,
    )
    add(
        source="vignette",
        hidden="vignette_unrecognised",
        setting="Tweede Kamer floor, sitting open, 1899",
        actor_role="MP",
        actor_name="(unrecognised member)",
        action="speaks without having been given the floor",
        text="Mijnheer de Voorzitter! Ik onderbreek den minister — de begrooting sluit niet.",
        catch=False,
    )
    add(
        source="vignette",
        hidden="vignette_corridor",
        setting="Wandelgang, sitting in progress, 1899",
        actor_role="MP",
        actor_name="(member in the corridor)",
        action="tells a colleague the Minister of Colonies may resign",
        text="Zacht: de Minister van Koloniën zou over het Indisch tekort aftreden.",
        catch=False,
    )
    add(
        source="vignette",
        hidden="catch_anachronism",
        setting="Tweede Kamer floor, sitting open, 1899",
        actor_role="MP",
        actor_name="(attention check)",
        action="reads a tweet about the sitting into the record",
        text="Mijnheer de Voorzitter! I just saw on Twitter that the minister is trending.",
        catch=True,
    )
    rng.shuffle(items)
    return items[:N_PROCEDURE]


def codebook() -> dict:
    return {
        "title": "Kamer historian lab",
        "corpus": (
            "Dutch Parliamentary Proceedings 1814–2012 (PoliticalMashup / Marx et al.), "
            "doi:10.17026/DANS-XK5-DW3S, CC0. Working slice 1814–1899."
        ),
        "period": "Tweede Kamer, late 1890s (seed week December 1899).",
        "tasks": {
            "rank": (
                "Blind pairwise ranking of pause-and-interview answers given off the floor "
                "(wandelgang / side room), not as Tweede Kamer speeches. "
                "They should not open by addressing the Chair. "
                "Rate believability (could this public person have said this, in late-1890s Dutch?) and "
                "historical-procedural plausibility (does it respect the Reglement van Orde?). "
                "Conditions are hidden. Two items are attention checks."
            ),
            "speakers": (
                "Check names, roles, and parties parsed from OCR'd Handelingen XML. "
                "Mark garbled readings. Flag synthetic or invented cards. "
                "We do not ask you to reconstruct private lives."
            ),
            "procedure": (
                "For each clip or vignette: would the Chair have allowed it, "
                "and would the stenographer have written it into the Handelingen?"
            ),
        },
        "ethics": (
            "Agents are public office-holders. There is no playable persona. "
            "Do not invent inner lives. Annotations are research data; "
            "download your JSON and send it back to the investigators."
        ),
    }


def main() -> None:
    rng = random.Random(20261012)
    DATA.mkdir(parents=True, exist_ok=True)
    raw = collect_interviews(DATA / "interviews_raw.json")
    llm_rows = load_llm_interviews()
    if llm_rows:
        print("using LLM interviews", list(llm_rows))
    pairs = interview_pairs(raw, rng, llm_rows or None)
    speakers = speaker_items(rng)
    procedure = procedure_items(raw, speakers, rng)

    interviews_path = DATA / "interviews.json"
    if interviews_path.exists() and (json.loads(interviews_path.read_text(encoding="utf-8")).get("frozen")):
        print("keeping frozen", interviews_path)
    else:
        interviews_path.write_text(
            json.dumps({"n": len(pairs), "frozen": False, "items": pairs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (DATA / "speakers.json").write_text(
        json.dumps({"n": len(speakers), "items": speakers}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DATA / "procedure.json").write_text(
        json.dumps({"n": len(procedure), "items": procedure}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DATA / "codebook.json").write_text(
        json.dumps(codebook(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 25-agent cast for the People page (attested speakers + two synthetic roles)
    cast = []
    for row in (raw.get("full") or {}).get("rows") or []:
        rec = next((s for s in speakers if s.get("name") == row.get("name")), None)
        cast.append(
            {
                "id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "persona": (row.get("answers") or {}).get("self-knowledge", [""])[0],
                "member_ref": (rec or {}).get("member_ref") or "",
                "party": (rec or {}).get("suggested_party") or "",
                "synthetic": row["status"] in {"Journalist", "Clerk"} or row["name"].startswith("Lid "),
                "excerpts": (rec or {}).get("excerpts") or [],
            }
        )
    (DATA / "personas.json").write_text(
        json.dumps(cast, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    figs = OUT / "figs"
    figs.mkdir(exist_ok=True)
    for name in ("kamer.svg", "sandbox.png"):
        src = ROOT / "figs" / name
        if src.exists():
            shutil.copy2(src, figs / name)
    (OUT / ".nojekyll").write_text("")
    print(
        "wrote",
        f"{len(pairs)} pairs,",
        f"{len(speakers)} speakers,",
        f"{len(procedure)} procedure →",
        DATA,
    )


if __name__ == "__main__":
    main()
