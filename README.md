# Kamer

Archive-grounded generative-agent sandbox of Dutch parliamentary debate
(working implementation of `paper.tex`).

The sandbox is a composite Binnenhof (Tweede Kamer floor, wandelgang,
committee rooms, press gallery, ministries). **Role and standing orders**—not
the LLM’s disposition—gate every action. There is **no playable persona**.

We abandoned an earlier slave-society design after historians flagged it as
ethically unacceptable. Agents here are public office-holders seeded from
CC0 *Handelingen der Staten-Generaal*.

Corpus: [Dutch Parliamentary Proceedings 1814–2012](https://doi.org/10.17026/DANS-XK5-DW3S)
(PoliticalMashup / Marx et al.; CC0). The working slice in
`Dutch Parliamentary debates (XML).zip` is **1814–1899**: 8,745 sittings,
138,214 speeches.

## Layout

```
kamer/            parliamentary simulation
  world/          Binnenhof tree T, objects, standing orders
  agents/         memory Eq.(1), role automaton, corridor rumours
  pipeline/       DutchParl XML parser, attested-speaker population
  sim/            engine, stenographers (simulated Handelingen)
  eval/           interviews, leak diffusion
  api/            REST (inspect / interview / inner voice / edit / inject)
frontend/         inspector dashboard
scripts/          S1, corpus stats, serve
tests/            standing orders, Handelingen selection, ethics
```

The legacy `maroon/` package is the abandoned island sandbox; do not use it
for new experiments.

## Run (inside the conda container)

```bash
podman exec conda bash -c 'cd /workspace/history-sandbox && PYTHONPATH=. python -m unittest tests.test_kamer -q'
podman exec conda bash -c 'cd /workspace/history-sandbox && PYTHONPATH=. python kamer/pipeline/proceedings.py'
podman exec conda bash -c 'cd /workspace/history-sandbox && PYTHONPATH=. python scripts/run_kamer_s1.py --n 25 --days 7'
podman exec conda bash -c 'cd /workspace/history-sandbox && PYTHONPATH=. /workspace/.conda/envs/samesea/bin/python scripts/serve.py'
```

`scripts/serve.py` listens on `:8765`. Researcher endpoints: inspect,
interview, inner voice, edit object, inject event, read Handelingen.
`POST /possess` is forbidden.

Set `MAROON_API_KEY` / `MAROON_MODEL` to use an OpenAI-compatible backend;
the default `heuristic` backend is enough for S1 leak experiments.

## What the current runs fill

| Item | Status |
|---|---|
| Corpus 1814–1899 | 8,745 sittings, 138,214 speeches (`data/corpus_stats.json`) |
| S1 leak diffusion, N=25, 5 seeds | `runs/kamer/s1.json`, Fig. 2 |
| GA ablation (no corridor network) | `runs/kamer/s1_ga.json` (members stay at 5% seed) |
| Interview TrueSkill | historian lab: https://shuishen112.github.io/history-sandbox/ |
| S2 / S3 macro tables | engine ready; not yet run |
