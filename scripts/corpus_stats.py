"""Count DutchParl XML files in the local zip."""
from __future__ import annotations

import collections
import re
import zipfile

ZIP_PATH = "Dutch Parliamentary debates (XML).zip"


def main() -> None:
    z = zipfile.ZipFile(ZIP_PATH)
    names = [n for n in z.namelist() if n.endswith(".xml")]
    n_speech = 0
    n_meet = 0
    houses: collections.Counter[str] = collections.Counter()
    years: collections.Counter[str] = collections.Counter()
    roles: collections.Counter[str] = collections.Counter()
    speakers: set[str] = set()
    parties: collections.Counter[str] = collections.Counter()
    n_with_speech = 0
    n_member_ref = 0

    speaker_re = re.compile(rb'pm:speaker="([^"]*)"')
    role_re = re.compile(rb'pm:role="([^"]*)"')
    party_re = re.compile(rb'pm:party-ref="([^"]*)"')
    member_re = re.compile(rb'pm:member-ref="([^"]*)"')
    house_re = re.compile(rb'pm:house="([^"]*)"')

    for i, n in enumerate(names):
        data = z.read(n)
        n_meet += 1
        k = data.count(b"<speech ")
        n_speech += k
        if k:
            n_with_speech += 1
        ym = re.search(r"(\d{4})-", n.split("/")[-1])
        if ym:
            years[ym.group(1)] += 1
        hm = house_re.search(data)
        if hm:
            houses[hm.group(1).decode("utf-8", "replace")] += 1
        elif "Eerste Kamer" in n:
            houses["EK-fn"] += 1
        elif "Tweede Kamer" in n:
            houses["TK-fn"] += 1
        else:
            houses["other"] += 1
        if i % 500 == 0:
            for m in speaker_re.finditer(data):
                speakers.add(m.group(1).decode("utf-8", "replace"))
            for m in role_re.finditer(data):
                roles[m.group(1).decode("utf-8", "replace")] += 1
            for m in party_re.finditer(data):
                parties[m.group(1).decode("utf-8", "replace")] += 1
            n_member_ref += sum(1 for m in member_re.finditer(data) if m.group(1))
            print(i, "speeches_so_far", n_speech, flush=True)

    # second pass on a denser speaker sample: last 200 files of 1890s
    late = [n for n in names if "/189" in n or n.split("/")[-1].startswith("189")]
    late = late[-400:] if late else names[-400:]
    for n in late:
        data = z.read(n)
        for m in speaker_re.finditer(data):
            speakers.add(m.group(1).decode("utf-8", "replace"))
        for m in role_re.finditer(data):
            roles[m.group(1).decode("utf-8", "replace")] += 1
        for m in party_re.finditer(data):
            parties[m.group(1).decode("utf-8", "replace")] += 1

    print("meetings", n_meet)
    print("speech_tags", n_speech)
    print("files_with_speech", n_with_speech)
    print("houses", dict(houses))
    print("year_span", min(years), max(years), "n_years", len(years))
    dec: collections.Counter[str] = collections.Counter()
    for y, c in years.items():
        dec[y[:3] + "0"] += c
    print("decades", dict(sorted(dec.items())))
    print("unique_speakers_sampled", len(speakers))
    print("roles", dict(roles.most_common(20)))
    print("parties", dict(parties.most_common(15)))


if __name__ == "__main__":
    main()
