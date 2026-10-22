"""Archive vs simulated Handelingen: role mix, journalist leak, speech length."""

from __future__ import annotations

import collections
import re
import zipfile
from pathlib import Path
from typing import Iterable

from maroon.eval.fidelity import jsd, wasserstein_1d

ZIP_PATH = Path("Dutch Parliamentary debates (XML).zip")
ROLE_RE = re.compile(rb'<speech[^>]*pm:role="([^"]+)"')
YEAR_RE = re.compile(r"(\d{4})-")


def _norm(counter: collections.Counter[str], keys: Iterable[str] | None = None) -> dict[str, float]:
    keys = list(keys) if keys is not None else list(counter)
    tot = sum(counter[k] for k in keys) or 1.0
    return {k: counter[k] / tot for k in keys}


def archive_role_mix(
    zip_path: Path | str = ZIP_PATH,
    year_min: int = 1890,
    year_max: int = 1899,
    house: str = "commons",
) -> dict:
    z = zipfile.ZipFile(zip_path)
    roles: collections.Counter[str] = collections.Counter()
    n_files = 0
    lengths: list[float] = []
    sample = 0
    for name in z.namelist():
        if not name.endswith(".xml"):
            continue
        ym = YEAR_RE.search(name.split("/")[-1])
        if not ym:
            continue
        year = int(ym.group(1))
        if year < year_min or year > year_max:
            continue
        data = z.read(name)
        if house == "commons" and b'pm:house="commons"' not in data and "Tweede Kamer" not in name:
            continue
        if house == "senate" and b'pm:house="senate"' not in data:
            continue
        n_files += 1
        for m in ROLE_RE.finditer(data):
            roles[m.group(1).decode("utf-8", "replace")] += 1
        if sample < 80:
            sample += 1
            # crude: characters between <speech and </speech>
            for chunk in data.split(b"<speech ")[1:6]:
                end = chunk.find(b"</speech>")
                if end > 0:
                    lengths.append(float(end))
    mapped = collections.Counter()
    for k, v in roles.items():
        if k in {"mp", "chair", "government"}:
            mapped[k] += v
        else:
            mapped["other"] += v
    mapped["journalist"] = 0  # never in the Handelingen
    return {
        "n_sittings": n_files,
        "n_speeches": sum(roles.values()),
        "roles": dict(roles),
        "role_mix": _norm(mapped, ["mp", "government", "chair", "journalist", "other"]),
        "lengths": lengths,
        "year_min": year_min,
        "year_max": year_max,
    }


def sim_role_mix(lines: list[dict], naive_extra: list[dict] | None = None) -> dict:
    use = list(lines)
    if naive_extra:
        use = use + naive_extra
    mapped = collections.Counter()
    lengths: list[float] = []
    for line in use:
        role = (line.get("role") or "").lower()
        if role in {"mp", "member"}:
            mapped["mp"] += 1
        elif role in {"minister", "government"}:
            mapped["government"] += 1
        elif role in {"chair"}:
            mapped["chair"] += 1
        elif role in {"journalist"}:
            mapped["journalist"] += 1
        else:
            mapped["other"] += 1
        lengths.append(float(len(line.get("text") or "")))
    keys = ["mp", "government", "chair", "journalist", "other"]
    return {
        "n_speeches": sum(mapped.values()),
        "role_mix": _norm(mapped, keys),
        "lengths": lengths,
        "journalist_share": mapped["journalist"] / (sum(mapped.values()) or 1),
    }


def compare(sim: dict, arch: dict) -> dict:
    keys = ["mp", "government", "chair", "journalist", "other"]
    role_jsd = jsd(
        {k: sim["role_mix"].get(k, 0.0) for k in keys},
        {k: arch["role_mix"].get(k, 0.0) for k in keys},
    )
    length_w1 = wasserstein_1d(sim.get("lengths") or [0], arch.get("lengths") or [0])
    # scale W1 to thousands of characters to keep table compact
    return {
        "role_jsd": role_jsd,
        "length_w1": length_w1 / 1000.0,
        "journalist_share": sim.get("journalist_share", 0.0),
        "n_speeches": sim.get("n_speeches", 0),
    }


def anachronism_rate(texts: Iterable[str]) -> float:
    hits = 0
    n = 0
    modern = (
        "internet",
        "email",
        "smartphone",
        "climate change",
        "human rights",
        "twitter",
        "democracy promotion",
        "lgbt",
        "covid",
    )
    for t in texts:
        n += 1
        low = t.lower()
        if any(w in low for w in modern):
            hits += 1
    return hits / n if n else 0.0
