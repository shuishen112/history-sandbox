"""Presentism audit for simulated parliamentary speech (kamer/PRESENTISM_EVAL.md).

Every measure is applied identically to simulated utterances and to the
Tweede Kamer 1890-1899 holdout, so each number has an archival reference:

  modern_vocab     21st-century policy, technology and address vocabulary.
                   The lexicon is split into a FILTER half (the only terms the
                   anachronism filter may see) and an AUDIT half (never seen by
                   the filter). Terms attested in the holdout are dropped.
  modern_spelling  post-1947 spellings where De Vries-Te Winkel (the 1890s
                   norm) had another form: zoo/zo, regeering/regering, ...
  vocative         opening address: "Mijnheer de Voorzitter!" vs modern forms
                   ("Geachte Voorzitter", "Meneer de Voorzitter", "Voorzitter,").
  register         adversarial register: turns that challenge or rebut another
                   participant, and consensus / sanitised-conflict cues.
  self_desc        self-description errors ("MP", "lid der Staten-Generaal",
                   wrong office or house, post-1899 parties, later years).

Pure stdlib; no network.
"""

from __future__ import annotations

import collections
import json
import math
import random
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable

from kamer.pipeline.proceedings import parse_sitting

ZIP_PATH = Path("Dutch Parliamentary debates (XML).zip")
WINDOW = 480  # compose_speech truncates floor utterances to 480 characters


def _rx(pattern: str) -> re.Pattern[str]:
    # 1890s print and OCR use both "ij" and "y" (zyne, wettelyke).
    return re.compile(pattern.replace("ij", "(?:ij|y)"))


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = re.sub(r"\xad\s*", "", t)  # soft hyphen at OCR line breaks: "ge\xad achten"
    t = t.replace("ÿ", "ij").replace("’", "'").replace("‘", "'")
    return " ".join(t.split()).lower()


def window(text: str, n: int = WINDOW) -> str:
    return normalize(text)[:n]


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# ---------------------------------------------------------------- lexicons
# (id, regex on normalized text, category). Split is deterministic: within a
# category, terms sorted by id alternate filter/audit.
MODERN_VOCAB_SPEC: list[tuple[str, str, str]] = [
    # 21st-century policy register
    ("aanpakken", r"\b(aan te pakken|aanpakken|aanpak)\b", "policy"),
    ("budget", r"\bbudget(ten)?\b", "policy"),
    ("cohesie", r"\b(sociale )?cohesie\b", "policy"),
    ("communicatie", r"\bcommunicatie\b", "policy"),
    ("constructief", r"\bconstructie(f|ve)\b", "policy"),
    ("diversiteit", r"\bdiversiteit\b", "policy"),
    ("draagvlak", r"\bdraagvlak\b", "policy"),
    ("duurzaam", r"\bduurza(am|me|amheid)\b", "policy"),
    ("economische_groei", r"\beconomische groei\b", "policy"),
    ("efficient", r"\beffici[eë]n(t|te|tie)\b", "policy"),
    ("faciliteren", r"\bfacilit(eer|eren|eert|eerd)\w*", "policy"),
    ("focus", r"\bfocus(sen)?\b", "policy"),
    ("generaties", r"\b(toekomstige|komende|jonge|jongere) generaties?\b", "policy"),
    ("gelijke_kansen", r"\bgelijke kansen\b", "policy"),
    ("impact", r"\bimpact\b", "policy"),
    ("inclusie", r"\binclusi(e|viteit)\b|\binclusieve\b", "policy"),
    ("infrastructuur", r"\binfrastructu?u?r\w*", "policy"),
    ("innovatie", r"\binnovatie(f|ve|s)?\b", "policy"),
    ("kwaliteit_onderwijs", r"\bkwaliteit van (het|ons) onderwijs\b", "policy"),
    ("mensenrechten", r"\bmensenrechten\b", "policy"),
    ("moderne_wereld", r"\bmoderne (wereld|tijd|samenleving|maatschappij)\b", "policy"),
    ("netwerk", r"\bnetwerk(en)?\b", "policy"),
    ("participatie", r"\bparticipatie\b", "policy"),
    ("polarisatie", r"\bpolari(satie|seren)\b", "policy"),
    ("proactief", r"\bpro-?actie(f|ve)\b", "policy"),
    ("samenleving", r"\bsamenleving\b", "policy"),
    ("stabiliteit", r"\bstabiliteit\b", "policy"),
    ("systeem_compound", r"\b(onderwijs|zorg|belasting|rechts|pensioen|bestuurs)systee?m\b", "policy"),
    ("transparant", r"\btransparan(t|te|tie)\b", "policy"),
    ("uitdaging", r"\buitdaging(en)?\b", "policy"),
    ("verantwoordelijkheid_nemen", r"\bverantwoordelijkheid (te )?nemen\b", "policy"),
    ("welzijn_burgers", r"\bwelzijn van (onze |de )?(burgers|bevolking|samenleving)\b", "policy"),
    # institutions and offices that post-date 1899
    ("minister_president", r"\bminister-?president\b|\bpremier\b", "institution"),
    ("eu_navo_vn", r"\b(europese unie|navo|verenigde naties)\b", "institution"),
    ("sessie", r"\bsessie\b", "institution"),
    ("fractievoorzitter", r"\bfractievoorzitter\w*", "institution"),
    ("partijlijn", r"\bpartijlijn\b|\bpartijdiscipline\b", "institution"),
    # modern address forms
    ("collega", r"\bcollega('s)?\b", "address"),
    ("meneer", r"\bmeneer\b", "address"),
    ("geachte_voorzitter", r"\bgeachte voorzitter\b", "address"),
    ("dames_en_heren", r"\bdames en heren\b", "address"),
    # technology and the modern world
    ("internet", r"\binternet\b|\bonline\b|\bdigita(al|le)\b", "technology"),
    ("email", r"\be-?mail\b", "technology"),
    ("smartphone", r"\bsmartphone|\bcomputer\w*", "technology"),
    ("social_media", r"\btwitter\b|\bsociale media\b|\blivestream\b", "technology"),
    ("televisie_radio", r"\btelevisie\b|\bradio\b", "technology"),
    ("vliegtuig", r"\bvliegtuig\w*", "technology"),
    ("klimaat", r"\bklimaat(verandering|crisis|beleid)\b", "technology"),
    ("covid", r"\bcovid\b|\bcorona\b|\blgbt\w*", "technology"),
    # English in Dutch floor speech
    ("en_okay", r"\b(okay|ok)\b", "english"),
    ("en_whip", r"\bwhip\b", "english"),
    ("en_parliament", r"\bparliament\b|\bdebate\b|\bspeaker\b", "english"),
    ("en_issue", r"\b(issue|issues|feedback|update|deal)\b", "english"),
    ("en_lobby", r"\blobby\w*", "english"),
]


def _split_lexicon(spec: list[tuple[str, str, str]]) -> dict[str, dict]:
    by_cat: dict[str, list[tuple[str, str, str]]] = collections.defaultdict(list)
    for row in spec:
        by_cat[row[2]].append(row)
    out: dict[str, dict] = {}
    for cat, rows in by_cat.items():
        for i, (tid, pat, _) in enumerate(sorted(rows)):
            out[tid] = {"rx": _rx(pat), "category": cat, "split": "filter" if i % 2 == 0 else "audit"}
    return out


LEXICON = _split_lexicon(MODERN_VOCAB_SPEC)


# (id, old De Vries-Te Winkel form, post-1947 form)
SPELLING_PAIRS: list[tuple[str, str, str]] = [
    ("zoo", r"\bzoo\b", r"\bzo\b"),
    ("zoodat", r"\bzoodat\b", r"\bzodat\b"),
    ("zooals", r"\bzooals\b", r"\bzoals\b"),
    ("zoodra", r"\bzoodra\b", r"\bzodra\b"),
    ("zoowel", r"\bzoowel\b", r"\bzowel\b"),
    ("zooveel", r"\bzoo(veel|lang|ver|even)\b", r"\bzo(veel|lang|ver|even)\b"),
    ("regeering", r"\bregeering\w*", r"\bregering\w*"),
    ("meening", r"\bmeening(en)?\b", r"\bmening(en)?\b"),
    ("beteekenis", r"\bbeteeken\w*", r"\bbeteken\w*"),
    ("vereeniging", r"\bvereenig\w*", r"\bverenig\w*"),
    ("afdeeling", r"\bafdeeling\w*", r"\bafdeling\w*"),
    ("begrooting", r"\bbegrooting\w*", r"\bbegroting\w*"),
    ("eenige", r"\beenig(e|en|szins)?\b", r"\benig(e|en|szins)?\b"),
    ("heeren", r"\bheeren\b", r"\bheren\b"),
    ("groote", r"\bgroote(n|r|re)?\b", r"\bgrote(n|r|re)?\b"),
    ("hooge", r"\bhooge(n|r|re)?\b", r"\bhoge(n|r|re)?\b"),
    ("noodig", r"\bnoodig\w*", r"\bnodig\w*"),
    ("mensch", r"\bmensch(en|elijk\w*|heid)?\b", r"\bmens(en|elijk\w*|heid)?\b"),
    ("nederlandsch", r"\bnederlandsche?\b", r"\bnederlandse?\b"),
    ("wensch", r"\bwensch\w*", r"\bwens(en|t|elijk\w*)?\b"),
    ("engelsch", r"\b(engel|fran|duit)sche?\b", r"\b(engel|fran|duit)se?\b"),
    ("practisch", r"\bpracti(sch|jk)\w*", r"\bprakti(sch|jk)\w*"),
    ("quaestie", r"\bquaestie\w*", r"\bkwestie\w*"),
]
SPELLING = [(pid, _rx(old), _rx(new)) for pid, old, new in SPELLING_PAIRS]

# Case morphology diagnostics (share of the period form; holdout is the reference).
DECLENSION = {
    "der_vs_van_de": (_rx(r"\bder\b"), _rx(r"\bvan de\b")),
    "eene_vs_een": (_rx(r"\beene\b"), _rx(r"\been\b")),
}

VOC_PERIOD = _rx(r"^\W*mijnheer de voorzitter")
VOC_MODERN = _rx(
    r"^\W*((geachte|waarde|beste|hooggeachte|edelachtbare) (heer )?(de )?voorzitter"
    r"|meneer de voorzitter|de heer voorzitter|voorzitter\s*[,!.:]|geachte (leden|aanwezigen|collega)"
    r"|dames en heren|mijn waarde|waarde collega|beste)"
)


# ---------------------------------------------------------------- register
REF_OTHER = [
    _rx(r"\b(de|den|het) geachten? (spreker|afgevaardigde|voorganger|voorsteller|lid|heer|minister|rapporteur|vriend)"),
    _rx(r"\b(de|den) (vorige|laatste|eerste|tweede|eerste) spreker\b"),
    _rx(r"\bmijn(en)? geachten? (vriend|ambtgenoot|medelid|tegenstander|collega)"),
    _rx(r"\b(de|den) heer (?!voorzitter)[a-z]"),
    _rx(r"\b(de|den|zijne excellentie de|z\. ?exc\. de) ministers?\b"),
    _rx(r"\bde regee?ring\b"),
    # "collega" only when it names a third party ("mijn collega Van Houten"), not as a vocative
    _rx(r"\b(de|den|mijn|onze) (geachte |waarde )?collega('s)? (de |van |den )?[a-z]{3,}"),
    _rx(r"\bmijn(en)? (ambtgenoot|tegenstander|tegenstanders)\b"),
]
CHALLENGE = [
    _rx(r"\bniet (kan |kunnen )?toegeven|\bniet toe(geven|stemmen)"),
    _rx(r"\b(het|er)\b[^.!?]{0,20}\bniet (mede |mee )?eens\b|\boneens\b"),
    _rx(r"\bbestrijd\w*|\bbestreden\b"),
    _rx(r"(?<!niet )(?<!niet te )\b(betwist|ontken)\w*"),
    _rx(r"\btegen ?te ?spreken\b|\btegenspraak\b|\bspreek (ik )?.{0,15}tegen\b"),
    _rx(r"\bweerleg\w*|\bwederleg\w*"),
    _rx(r"\bvergist zich\b|\bvergissing\b|\bdwaalt\b|\bdwaling\b"),
    _rx(r"\bonjuist\w*|\bongegrond\w*|\bonwaar(heid|e|achtig)?\b|\bis niet juist\b|\bis niet waar\b(?!\s*\?)"),
    _rx(r"\bprotest\w*"),
    _rx(r"\bintegendeel\b|\bgeenszins\b|\ballerminst\b|\bvolstrekt niet\b|\bin geen(en)? deele\b"),
    _rx(r"\bten onrechte\b|\bmiskent\b|\bmiskenning\b"),
    _rx(r"\bverwijt\w*|\bbeschuldig\w*"),
    _rx(r"\bafkeur\w*|\bafgekeurd\b|\bverwerp\w*|\bverworpen\b"),
    _rx(r"\bniet vere?enigen\b"),
    _rx(r"\bop ?(te )?komen tegen\b|\btegen .{0,30}op te komen\b"),
    _rx(r"\btegen (het|dit|dat|deze|die|zulk) (wetsontwerp|ontwerp|amendement|voorstel|artikel|motie)"),
    _rx(r"\btegen ?(te )?stemmen\b"),
    _rx(r"(?<!geen )\bbezwa(a)?r\w*"),
    _rx(r"\bheeft beweerd\b|\bbeweert\b|\bbewering\b"),
    _rx(r"\bik betreur\w*"),
]
CONTRAST = _rx(r"\b(maar|doch|evenwel|echter|daarentegen|integendeel)\b")
ATTRIB = _rx(
    r"\b(heeft|hebben|had)\b[^.!?]{0,60}\b(gezegd|beweerd|opgemerkt|betoogd|aangevoerd|verklaard"
    r"|geantwoord|gevraagd|voorgesteld|gesproken)\b|\b(zegt|meent|beweert|betoogt|stelt voor)\b"
)
CONSENSUS = [
    _rx(r"\bsamenwerk\w*|\bsamen te werken\b|\bsamen (kunnen|moeten|zullen)\b"),
    _rx(r"\bgezamenlijk\w*|\bgemeenschappelijk\w* (doel|belang|standpunt)"),
    _rx(r"\bconstructie(f|ve)\b"),
    _rx(r"\beensgezind\w*|\bharmonie\w*"),
    _rx(r"\bdraagvlak\b|\bconsensus\b|\bcompromis\w*"),
    _rx(r"\bdialoog\b|\bopen gesprek\b|\bwederzijds\w* (begrip|respect)"),
    _rx(r"\blaten wij (ons |hopen|samen|er )|\blaten we\b"),
    _rx(r"\bin het belang van (ons )?allen\b|\bwij allen\b|\bons allen\b"),
    _rx(r"\bbruggen? (te )?slaan\b"),
]


def register_features(text: str) -> dict[str, bool]:
    t = window(text)
    challenge = any(rx.search(t) for rx in CHALLENGE)
    ref = any(rx.search(t) for rx in REF_OTHER)
    rebut = responsive = False
    for s in sentences(t):
        if any(rx.search(s) for rx in REF_OTHER):
            rebut = rebut or bool(CONTRAST.search(s))
            responsive = responsive or bool(ATTRIB.search(s))
    return {
        "challenge": challenge,
        "ref_other": ref,
        "responsive": responsive,
        "rebuttal": rebut,
        "adversarial": challenge or rebut,
        "consensus": any(rx.search(t) for rx in CONSENSUS),
    }


# ---------------------------------------------------------------- self-description
# First-person clause ("ik ben ...", "als ... ik", sentence-initial "Als ...") followed by a title.
_SELF = (
    r"(\b(ik ben|ben ik|ik bekleed|bekleed ik|mijne? (functie|ambt|positie|hoedanigheid))\b[^.!?]{0,60}"
    r"|\bik\b[^.!?]{0,30}\bals (een |de |den )?|(^|[.!?]\s+)als (een |de |den )?)"
)
SELF_TITLE = {
    "mp_english": r"\b(mp|m\.p\.|member of parliament|parliamentarian)\b",
    "parlementslid": r"\b(parlementslid|parlementari[eë]r)\b",
    "lid_staten_generaal": r"\blid (der|van de|van) staten-? ?generaal\b",
    "voorzitter_staten_generaal": r"\bvoorzitter (der|van de|van) staten-? ?generaal\b",
}
SELF_DESC: dict[str, re.Pattern[str]] = {code: _rx(_SELF + pat) for code, pat in SELF_TITLE.items()}
SELF_DESC.update({
    # anywhere in an answer about oneself
    "modern_party": _rx(
        r"\b(cda|pvda|vvd|d66|groenlinks|pvv|christenunie|sgp|kvp|chu|vdb|partij van de arbeid"
        r"|volkspartij voor vrijheid|vrijzinnig-democratische bond)\b"
    ),
    "later_year": _rx(r"\b(19[0-9][1-9]|19[1-9]0|20[0-9]{2})\b"),
    "ai_self": _rx(r"\btaalmodel\b|\blanguage model\b|\bals (een )?ai\b|\bkunstmatige intelligentie\b"),
})
# Not a self-claim, but the same confusion: the Staten-Generaal treated as the chamber one sits in.
SG_AS_CHAMBER = _rx(
    r"\b(leden|lid) (der|van de|van) staten-? ?generaal\b|\b(in|uit) de staten-? ?generaal\b"
    r"|\bmp'?s\b|\bparlementsleden\b"
)
OFFICE_CLAIM = {
    "minister": _rx(_SELF + r"\bminister\b"),
    "kamerlid": _rx(_SELF + r"\b(kamerlid|lid (der|van de) (tweede )?kamer|volksvertegenwoordiger)\b"),
    "voorzitter": _rx(_SELF + r"\bvoorzitter\b"),
    "griffier": _rx(_SELF + r"\bgriffier\b"),
    "journalist": _rx(_SELF + r"\b(journalist|verslaggever|correspondent)\b"),
    "eerste_kamer": _rx(_SELF + r"\beerste kamer\b"),
    "tweede_kamer": _rx(_SELF + r"\btweede kamer\b"),
}
ALLOWED_OFFICE = {
    "Chair": {"voorzitter", "kamerlid", "tweede_kamer"},
    "MP": {"kamerlid", "tweede_kamer"},
    "Minister": {"minister", "tweede_kamer", "eerste_kamer"},  # ministers address both houses
    "Clerk": {"griffier", "tweede_kamer"},
    "Journalist": {"journalist", "tweede_kamer"},
    "Gallery": set(),
}


def self_description_errors(text: str, status: str, house: str = "commons") -> list[str]:
    t = normalize(text)
    errs = [code for code, rx in SELF_DESC.items() if rx.search(t)]
    allowed = set(ALLOWED_OFFICE.get(status, set()))
    if house == "senate" and status != "Minister":
        allowed = (allowed - {"tweede_kamer"}) | {"eerste_kamer"}
    for office, rx in OFFICE_CLAIM.items():
        if rx.search(t) and office not in allowed:
            errs.append(f"claims_{office}")
    return sorted(set(errs))


def sg_as_chamber(text: str) -> bool:
    return bool(SG_AS_CHAMBER.search(normalize(text)))


# ---------------------------------------------------------------- per-text features
def vocab_hits(text: str, attested: set[str] | None = None) -> list[str]:
    t = normalize(text)
    skip = attested or set()
    return [tid for tid, row in LEXICON.items() if tid not in skip and row["rx"].search(t)]


def filter_hits(text: str, attested: set[str] | None = None) -> list[str]:
    """Terms the anachronism filter may act on (FILTER half only)."""
    return [tid for tid in vocab_hits(text, attested) if LEXICON[tid]["split"] == "filter"]


def spelling_counts(text: str) -> dict[str, tuple[int, int]]:
    t = normalize(text)
    return {pid: (len(old.findall(t)), len(new.findall(t))) for pid, old, new in SPELLING}


def vocative(text: str) -> str:
    t = normalize(text)[:80]
    if VOC_PERIOD.search(t):
        return "period"
    if VOC_MODERN.search(t):
        return "modern"
    return "none"


def text_features(text: str, attested: set[str] | None = None) -> dict:
    hits = vocab_hits(text, attested)
    sp = spelling_counts(text)
    t = normalize(text)
    return {
        "vocab_hits": hits,
        "vocab_filter": [h for h in hits if LEXICON[h]["split"] == "filter"],
        "vocab_audit": [h for h in hits if LEXICON[h]["split"] == "audit"],
        "spelling_old": sum(o for o, _ in sp.values()),
        "spelling_new": sum(n for _, n in sp.values()),
        "spelling_by_pair": {k: v for k, v in sp.items() if v != (0, 0)},
        "declension": {k: (len(a.findall(t)), len(b.findall(t))) for k, (a, b) in DECLENSION.items()},
        "vocative": vocative(text),
        "register": register_features(text),
        "n_chars": len(t),
    }


# ---------------------------------------------------------------- aggregation
def _share(xs: list[bool]) -> float | None:
    return sum(1 for x in xs if x) / len(xs) if xs else None


def aggregate(feats: list[dict]) -> dict:
    """Turn-level rates for one group of texts."""
    n = len(feats)
    if not n:
        return {"n": 0}
    old = sum(f["spelling_old"] for f in feats)
    new = sum(f["spelling_new"] for f in feats)
    voc = collections.Counter(f["vocative"] for f in feats)
    decl = {}
    for k in DECLENSION:
        a = sum(f["declension"][k][0] for f in feats)
        b = sum(f["declension"][k][1] for f in feats)
        decl[k] = a / (a + b) if a + b else None
    reg = {k: _share([f["register"][k] for f in feats]) for k in feats[0]["register"]}
    term_counts = collections.Counter(h for f in feats for h in f["vocab_hits"])
    return {
        "n": n,
        "modern_vocab": _share([bool(f["vocab_hits"]) for f in feats]),
        "modern_vocab_filter_half": _share([bool(f["vocab_filter"]) for f in feats]),
        "modern_vocab_audit_half": _share([bool(f["vocab_audit"]) for f in feats]),
        "modern_spelling_share": new / (old + new) if old + new else None,
        "spelling_tokens": old + new,
        "modern_vocative_share": voc["modern"] / (voc["modern"] + voc["period"]) if voc["modern"] + voc["period"] else None,
        "vocative_counts": dict(voc),
        "declension_period_share": decl,
        **{f"register_{k}": v for k, v in reg.items()},
        "top_terms": term_counts.most_common(12),
    }


def bootstrap_ci(
    groups: list[list[float]], stat=lambda xs: sum(xs) / len(xs), b: int = 2000, seed: int = 0
) -> tuple[float, float] | None:
    """Cluster bootstrap over runs (seeds), then over turns within each run."""
    groups = [g for g in groups if g]
    if not groups:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(b):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        xs = [g[rng.randrange(len(g))] for g in pick for _ in g]
        vals.append(stat(xs))
    vals.sort()
    return vals[int(0.025 * b)], vals[int(0.975 * b) - 1]


# ---------------------------------------------------------------- archive
def _year(name: str) -> int | None:
    m = re.match(r"(\d{4})-", name.split("/")[-1])
    return int(m.group(1)) if m else None


def excerpt_sittings(speakers_path: Path | str = "data/speakers.json") -> set[str]:
    """Bekendmakingen ids of sittings that donated persona excerpts (exclude from holdout)."""
    p = Path(speakers_path)
    if not p.exists():
        return set()
    ids = set()
    for rec in json.loads(p.read_text(encoding="utf-8")):
        for meta in rec.get("excerpt_meta") or []:
            if meta.get("identifier"):
                ids.add(meta["identifier"])
    return ids


def load_speeches(
    year_min: int,
    year_max: int,
    zip_path: Path | str = ZIP_PATH,
    roles: Iterable[str] = ("mp", "government"),
    min_chars: int = 80,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """Tweede Kamer speeches from the DutchParl XML slice (chair rulings excluded)."""
    roles = set(roles)
    exclude_ids = exclude_ids or set()
    out: list[dict] = []
    z = zipfile.ZipFile(zip_path)
    for name in z.namelist():
        if not name.endswith(".xml"):
            continue
        y = _year(name)
        if y is None or y < year_min or y > year_max:
            continue
        m = re.search(r"id\s+(\d{6,})", name.split("/")[-1])
        if m and m.group(1) in exclude_ids:
            continue
        data = z.read(name)
        if b'pm:house="commons"' not in data and "Tweede Kamer" not in name:
            continue
        _, speeches = parse_sitting(data, name)
        for sp in speeches:
            if sp.role not in roles or len(sp.text) < min_chars:
                continue
            out.append({"text": sp.text, "role": sp.role, "speaker": sp.speaker, "date": sp.date, "year": y})
    return out


def holdout_texts(
    zip_path: Path | str = ZIP_PATH,
    speakers_path: Path | str = "data/speakers.json",
    year_min: int = 1890,
    year_max: int = 1899,
) -> list[dict]:
    return load_speeches(year_min, year_max, zip_path, exclude_ids=excerpt_sittings(speakers_path))


def attested_terms(texts: Iterable[str], min_docs: int = 3) -> tuple[set[str], dict[str, int]]:
    """Lexicon terms found in >= min_docs period speeches (full text): not anachronisms."""
    df: collections.Counter[str] = collections.Counter()
    for t in texts:
        nt = normalize(t)
        for tid, row in LEXICON.items():
            if row["rx"].search(nt):
                df[tid] += 1
    return {k for k, v in df.items() if v >= min_docs}, dict(df)


def lexicon_table() -> list[dict]:
    spec = {tid: pat for tid, pat, _ in MODERN_VOCAB_SPEC}
    return [
        {"id": tid, "category": row["category"], "split": row["split"], "pattern": spec[tid]}
        for tid, row in sorted(LEXICON.items(), key=lambda kv: (kv[1]["category"], kv[0]))
    ]


def copies_passage(text: str, passages: Iterable[str], n: int = 8) -> bool:
    """True if the utterance shares a word n-gram with a retrieved archival passage."""
    def grams(t: str) -> set[tuple[str, ...]]:
        w = re.findall(r"[a-zà-ÿ]+", normalize(t))
        return {tuple(w[i : i + n]) for i in range(len(w) - n + 1)}

    g = grams(text)
    return bool(g) and any(g & grams(p) for p in passages)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - r) / d, (c + r) / d
