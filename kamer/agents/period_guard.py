"""Period-faithfulness guards as described in the paper (archival RAG + anachronism filter).

Not wired into Agent by default: scripts/run_presentism.py installs them for
the `kamer_full` condition so that pre- and post-filter text can be logged.

* ArchivalRAG retrieves attested Tweede Kamer passages from the 1860-1889
  calibration slice only, so nothing leaks into the 1890-1899 holdout used for
  evaluation.
* The filter only sees the FILTER half of the presentism lexicon
  (kamer.eval.presentism.LEXICON); the AUDIT half, spelling, vocative and
  register measures stay filter-blind.
"""

from __future__ import annotations

import collections
import math
import re
from pathlib import Path

from kamer.eval import presentism as P

STOP = set(
    """
    aan alle allen als ben bij daar dan dat de deze die dit door een eene eenige en er geen haar heb
    hebben heeft hem het hier hij hoe hun iets ik in is je kan kunnen maar men met mij mijn mijne na
    naar niet nog nu of om omdat ons onze ook op over reeds te tegen ten ter tot toe uit van veel voor
    want was wat wel werd wezen wij wordt worden zal zich zij zijn zijne zoo zou zullen den der des
    the and you your role location sitting open recognised memories write one floor utterance addressed
    voorzitter mijnheer kamer heer minister lid
    """.split()
)
# Lower-case content words only: Dutch capitalises names, not nouns, so this keeps
# member names in the prompt ("Also here: de Beaufort, ...") from retrieving roll calls.
TOKEN = re.compile(r"(?<![A-Za-zÀ-ÿ])[a-zà-ÿ]{4,}(?![A-Za-zÀ-ÿ])")
CAPWORD = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ]+")
WORD = re.compile(r"\b[A-Za-zÀ-ÿ]+")


def _tokens(text: str) -> list[str]:
    return [w for w in TOKEN.findall(_clean(text).replace("ÿ", "ij")) if w not in STOP]


def _name_list(text: str) -> bool:
    words = WORD.findall(text)
    return not words or len(CAPWORD.findall(text)) / len(words) > 0.25


def _clean(text: str) -> str:
    return " ".join(re.sub(r"\xad\s*", "", text).split())


class ArchivalRAG:
    def __init__(self, year_min: int = 1860, year_max: int = 1889, zip_path=P.ZIP_PATH, chars: int = 360) -> None:
        self.passages: list[dict] = []
        for sp in P.load_speeches(year_min, year_max, zip_path, min_chars=200):
            text = _clean(sp["text"])[:chars]
            if _name_list(text) or len(sp["speaker"]) < 3:  # roll calls, OCR debris
                continue
            self.passages.append({"year": sp["year"], "speaker": sp["speaker"], "text": text})
        self.index: dict[str, list[int]] = collections.defaultdict(list)
        for i, p in enumerate(self.passages):
            for w in set(_tokens(p["text"])):
                self.index[w].append(i)
        n = len(self.passages) or 1
        self.idf = {w: math.log(n / (1 + len(ids))) for w, ids in self.index.items()}
        self.length = [max(1, len(set(_tokens(p["text"])))) for p in self.passages]

    def query(self, text: str, k: int = 2) -> list[dict]:
        scores: dict[int, float] = collections.defaultdict(float)
        for w in set(_tokens(text)):
            ids = self.index.get(w)
            if not ids or len(ids) > 5000:  # skip near-stopwords
                continue
            for i in ids:
                scores[i] += self.idf[w]
        ranked = sorted(scores, key=lambda i: (-scores[i] / math.sqrt(self.length[i]), i))
        return [dict(self.passages[i], idx=i) for i in ranked[:k]]

    def block(self, hits: list[dict]) -> str:
        if not hits:
            return ""
        rows = [f'- ({h["year"]}, {h["speaker"]}) "{h["text"]}"' for h in hits]
        return (
            "Period reference from the Handelingen der Tweede Kamer (for register and spelling; "
            "do not quote it):\n" + "\n".join(rows)
        )


def surface_hits(text: str, attested: set[str] | None = None) -> list[str]:
    t = P.normalize(text)
    out = []
    for tid in P.filter_hits(text, attested):
        m = P.LEXICON[tid]["rx"].search(t)
        if m:
            out.append(m.group(0))
    return out


def regeneration_note(words: list[str]) -> str:
    return (
        "\n\nYour previous draft used wording foreign to Dutch parliamentary speech of 1899 ("
        + ", ".join(sorted(set(words)))
        + "). Write the utterance again without these words or concepts, as it could have been "
        "said in the Tweede Kamer in December 1899."
    )


def load_attested(path: Path | str) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    import json

    return set(json.loads(p.read_text(encoding="utf-8")).get("attested", []))
