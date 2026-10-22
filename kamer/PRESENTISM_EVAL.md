# Measuring presentist distortion in Kamer

Plan, scripts and cost estimate for a direct test of the paper's presentism
framing: LLM backbones speak 21st-century policy language and avoid the
adversarial register of 1890s debate, and Kamer moves the period constraints
into the world. Prepared 2026-10-19. **No paid runs have been launched.**

Files (all new; nothing existing was modified):

| file | role |
|---|---|
| `kamer/eval/presentism.py` | metrics, lexicons, holdout loader (stdlib only) |
| `kamer/agents/period_guard.py` | archival RAG + anachronism filter, as the paper describes them |
| `scripts/run_presentism.py` | runs the conditions; logs every completion before and after the filter; `count` / `replay` / `live` backends |
| `scripts/eval_presentism.py` | scores logs against the Tweede Kamer 1890–1899 holdout → `eval.json`, `eval.md` |
| `runs/presentism/` | `attested.json`, `holdout_features.json`, `count/` (completion counts), `replay_backbone/` (existing gpt-4o-mini outputs, scored) |

## 0. Why the current evidence cannot carry the framing

Found while reading the code and replaying `runs/kamer/llm_cache.jsonl`:

1. **The guards do not exist in Kamer.** `SimConfig.enable_archival_rag` and
   `enable_anachronism_filter` are never read under `kamer/`; only the
   abandoned `maroon/` agent reads them, and its filter masks words with
   `[period]` instead of regenerating. In the gpt-4o-mini backbone check,
   `full` meant world rules plus the `KAMER_SYSTEM` prompt, with no RAG and
   no filter. The abstract ("conditioned on period debate, and filtered for
   anachronism"), §Period-faithfulness guards and Alg. 1 (`ArchRAG`) describe
   code that those runs did not execute.
2. **The 0% audit mostly scores archival text, not LLM text.** The audit
   lexicon is nine English strings (`internet`, `covid`, …) matched against
   Dutch. It is also applied to Handelingen lines, most of which were not
   written by the LLM. The 400-completion cap is used up by cosmetic corridor
   bubbles: `Agent.step` → `compose_talk()` with no partner, about 17,000
   requests per Kamer week, each of which only sets the UI bubble. After that,
   `compose_speech` returns `"Mijnheer de Voorzitter! " + <verbatim persona
   excerpt from the Handelingen>`. The replay shows:
   - Kamer `full`: at most 20 of 205 record lines per seed are gpt-4o-mini
     text. These are 2–3 distinct utterances per seed, 7 across all seeds.
   - GA: 186–238 of 4,876 lines per seed are gpt-4o-mini text.

   With a regenerating filter, a post-filter 0% would also hold partly by
   construction.
3. **Agents never hear the previous speech.** `perceive()` logs who was given
   the floor, not what they said. In every condition a rebuttal is
   impossible, so comparing register with the Handelingen would measure this
   gap, not the backbone.
4. **GA and Kamer differ in the LLM prompt.** `GA_SYSTEM` says "Prefer period
   Dutch"; `KAMER_SYSTEM` lists 1890s spellings. Part of any spelling
   difference therefore comes from the prompt, which is the side the paper
   says the constraints are moved out of. A prompt-matched control is
   included below.
5. **The world can add presentism too.** The corridor object `whip_note`
   (a Westminster whip) is described to agents and appears in 68 distinct
   Kamer corridor completions ("de afwezigheid van den whip").
6. **The historian pack was probably rewritten by an LLM.** None of the 76
   rated texts in `historian-site/data/interviews.json` (frozen) appear
   verbatim in `runs/kamer/s1_llm.json`. The pack's register is "off-record
   1899 Dutch". `build_historian_site.py` prefers `s1_llm_period.json`, the
   output of `rewrite_kamer_interviews.py`, but that file no longer exists.
   Both conditions appear to have been rewritten, so the 17–8–11 ranking
   speaks to the rewritten text, not to raw agent output. Please verify.
7. **Runs were not replayable.** `hash(id) % 2` decides bench seating, and
   Python hashing varies between processes. `run_presentism.py` pins
   `PYTHONHASHSEED=0`.

## 1. Conditions

Shared: N=25 agents, 7 days, gpt-4o-mini, temperature 0.7, `max_tokens` 220
(the backbone settings), seeds {7, 11, 19}.

| condition | world | LLM system prompt | archival RAG | anachronism filter |
|---|---|---|---|---|
| `ga` | Smallville-style (`ga` preset) | `GA_SYSTEM` | – | – |
| `kamer_noguard` | role automaton + standing orders (= backbone `full`) | `KAMER_SYSTEM` | – | – |
| `kamer_full` | same | `KAMER_SYSTEM` | ✓ | ✓ |
| `ga_periodprompt` (recommended control) | Smallville-style | `KAMER_SYSTEM` | – | – |

Held constant across conditions, so that every scored turn is LLM text and
rebuttal is possible:

- No utterance cap: every floor, afdeeling (committee) and dialogue turn uses
  the LLM.
- Debate context on. Each floor prompt quotes the last recorded speech
  neutrally: `The previous speaker on the floor, X (MP), said: "…"`. There is
  no instruction to oppose. `--debate-context off` reproduces the backbone
  prompts.
- The solo corridor bubble is not sent to the LLM. It has no effect on
  memory, the record or rumours.
- 25 × 6 interviews at the end of the week.

Guards (`period_guard.py`):

- **RAG.** TF-IDF over 56,630 opening passages (360 characters) of Tweede
  Kamer MP and minister speeches from **1860–1889**, the calibration slice,
  with roll calls removed. The top 2 passages go into every prompt, marked
  "for register and spelling; do not quote it". Nothing from the 1890–1899
  holdout is ever retrieved.
- **Filter.** If a draft contains a term from the FILTER half of the lexicon,
  it is regenerated once, naming the offending words. The raw draft, the
  final text and any terms left after regeneration are all logged.

## 2. Metrics (`kamer/eval/presentism.py`)

**Unit.** Distinct LLM completions; a cached repeat of the same prompt counts
once. Every condition is scored on the **pre-filter** text; `kamer_full` is
also scored post-filter.

**Reference.** The Tweede Kamer 1890–1899 holdout: 14,731 MP and minister
speeches of at least 80 characters. Sittings that supplied persona excerpts
are excluded. Each speech is cut to its first 480 characters, the length cap
on simulated utterances.

| measure | definition | holdout |
|---|---|---|
| (a) modern vocabulary | share of turns with ≥1 lexicon term. 54 candidates (policy register, post-1899 offices, modern address forms, technology, English); the **16 attested in ≥3 holdout speeches are dropped automatically** (e.g. *duurzaam, samenleving, stabiliteit, collega, budget*), leaving 38. Split deterministically into a FILTER half (20 terms, the only ones the filter sees) and an AUDIT half (18, never seen by the filter). | 0.0% |
| (a) modern spelling | share of post-1947 forms across 23 pairs (*zoo/zo, regeering/regering, mensch/mens, wensch/wens, quaestie/kwestie, afdeeling/afdeling …*) | 1.2% (OCR) |
| (a) modern vocative | opening *Geachte/Waarde/Meneer de Voorzitter* or bare *Voorzitter,* versus *Mijnheer de Voorzitter!* | 1 / 5,608 |
| (b) adversarial register | challenge cue (*bestrijden, betwisten, niet toegeven, ten onrechte, tegen het amendement …*), **or** a reference to another participant (*de geachte spreker/afgevaardigde, de heer X, de Minister, de Regeering*) plus *maar/doch/evenwel/echter* in the same sentence | 28.9% |
| (b) consensus cues | *samenwerken, gezamenlijk, constructief, laten wij hopen, ons allen, draagvlak …* | 0.6% |
| (c) self-description errors | in interviews, mainly *Wie bent u…?*: first-person "MP" / *parlementslid* / *lid* or *voorzitter der Staten-Generaal*; claiming another office or house; post-1899 parties; years after 1900; AI self-reference. The rate of treating the Staten-Generaal as one's chamber is reported separately. | n/a |
| (d) copying check (`kamer_full`) | share of turns sharing a word 8-gram with their retrieved passages | n/a |

**Contrasts.**

1. `ga` vs `kamer_noguard`: the effect of the world rules.
2. `kamer_noguard` vs `kamer_full` (pre-filter): the effect of RAG on the
   draft.
3. `kamer_full` pre- vs post-filter on the **AUDIT half**: whether the filter
   helps beyond its own word list.
4. `ga` vs `ga_periodprompt`: the effect of the period prompt.
5. Every row against the holdout.

**Statistics.** Per-seed values; a cluster bootstrap 95% CI (seeds, then
turns); Wilson CIs for the interview rates.

**Validation still to do (free).** A historian labels 120 blinded turns (60
holdout, 60 simulated) as adversarial yes/no and modern yes/no, giving the
cues' precision and recall. I spot-checked the cues on both sides and
tightened them: corridor false positives fell from 37 to 7 of 221. Use the
historian rather than an LLM judge, which would bring in the same
present-day prior being measured.

## 3. What the existing gpt-4o-mini outputs show

Source: `runs/presentism/replay_backbone/eval.md` (backbone check replayed
offline from its cache; seed-7 interviews from `s1_llm.json`). There is no
debate context and there are no guards, so this is the system as published.

| | n distinct | modern vocab | modern spelling | modern vocative | adversarial | consensus |
|---|---|---|---|---|---|---|
| Handelingen 1890–1899 | 14,731 | 0.0% | 1.2% | 0.0% | 28.9% | 0.6% |
| GA, record lines | 269 | 6.3% [3–10] | 69.5% | 45.4% | 0.0% | 10.8% [6–15] |
| Kamer, record lines | **7** | 0.0% | 77.8% | 57.1% | 0.0% | 0.0% |
| Kamer, corridor talk | 734 | 9.8% [7–13] | 44.5% | – | 2.0% | 37.9% [34–42] |
| GA, interviews | 150 | 29.3% [22–37] | 100% | – | 1.3% | 18.0% |
| Kamer, interviews | 150 | 36.0% [29–44] | 100% | – | 1.3% | 17.3% |

- **Self-description errors**, in answers to *Wie bent u…*: GA 64%
  [45–80] vs Kamer 16% [6–35] (n=25 each). The dominant error is *lid van de
  Staten-Generaal*.
- **Typical modern terms**: *sessie* (a calque of the prompt's "not in
  session"), *constructief*, *onderwijssysteem*, *kwaliteit van het
  onderwijs*, *transparant*, *welzijn van onze burgers*, *toekomstige
  generaties*.

What this shows:

- The measure separates the conditions from the archive.
- Presentism is real in gpt-4o-mini output.
- Without guards, Kamer does not remove it from interviews or corridor talk.
- There is too little LLM floor text to say anything about the record.

The new runs are needed for the record-level claim.

**Predictions to check.**

- **H1.** Modern vocabulary falls as GA > kamer_noguard > kamer_full
  pre-filter > kamer_full post-filter, and the post-filter AUDIT half stays
  above 0.
- **H2.** Adversarial share: the holdout is highest; kamer_full is above
  kamer_noguard ≈ GA.
- **H3.** Self-description errors: GA > kamer_noguard ≥ kamer_full.

If H2 fails, the paper can keep the observation (LLMs avoid the register)
but should not claim that Kamer fixes it.

## 4. Cost estimate (gpt-4o-mini)

Completion counts come from `--backend count`, which runs exactly the same
control flow offline. Results are in `runs/presentism/count/*.summary.json`.

| condition | per run: floor + committee + dialogue + interview | 3 seeds |
|---|---|---|
| `ga` | 4,876 + 720 + ~251 + 150 ≈ 5,997 | **17,992** |
| `kamer_noguard` | 205 + 720 + ~246 + 150 ≈ 1,321 | **3,964** |
| `kamer_full` | 1,321 + ~170 filter regenerations | **≈ 4,470** |
| **main design** | | **≈ 26,400 completions** |
| `ga_periodprompt` (control) | as GA | +17,992 → **≈ 44,400** |

- **Regeneration estimate.** On existing pre-filter outputs the FILTER half
  fires on 0–4% of floor turns, 3–10% of corridor turns and 26–32% of
  interview answers. I assumed 10% / 10% / 35%.
- **Tokens.** Measured prompt lengths, plus the system prompt, at about 3.5
  characters per token:

  | condition | floor | committee | dialogue | interview |
  |---|---|---|---|---|
  | GA | ~390 | ~305 | ~215 | ~500 |
  | Kamer, no guards | ~480 | ~415 | ~310 | ~535 |
  | Kamer, full (RAG adds ~250) | ~725 | ~655 | ~555 | ~780 |

  Output averages ~100 tokens (cached answers average 314 characters).
- **Money.** The main design is ≈ 11.4M input and 2.6M output tokens, ≈
  **$3.3**. In the worst case, where every reply hits 220 tokens, it is ≈
  **$5.2**. The control adds $2.3–3.6. This uses the $0.15 / $0.60 per 1M
  tokens list price I know of; check current pricing.
- **Time.** Calls are sequential at about 1.2 s each: ≈ 9 h for the main
  design in one process, or ≈ 2 h with one process per (condition, seed).

## 5. Running it

```bash
cd /home/zhan/workspaces/history-sandbox
# offline, free: completion counts / replay of the backbone cache / scoring
PYTHONPATH=. python3 scripts/run_presentism.py --backend count --conditions ga,kamer_noguard,kamer_full,ga_periodprompt
PYTHONPATH=. python3 scripts/run_presentism.py --backend replay --conditions ga,kamer_noguard --debate-context off --kinds all --tag replay_backbone
PYTHONPATH=. python3 scripts/eval_presentism.py --logs runs/presentism/replay_backbone --s1-llm runs/kamer/s1_llm.json

# PAID, only after approval. --max-completions is a hard stop for the process.
PYTHONPATH=. python3 scripts/run_presentism.py --backend live --live --max-completions 30000 --tag live_main
PYTHONPATH=. python3 scripts/run_presentism.py --backend live --live --max-completions 20000 \
    --conditions ga_periodprompt --tag live_main --out-cache runs/presentism/llm_cache_gapp.jsonl
PYTHONPATH=. python3 scripts/eval_presentism.py --logs runs/presentism/live_main --label "gpt-4o-mini, seeds 7/11/19"
```

- The live mode reads `runs/kamer/llm_cache.jsonl` but never writes to it.
  New completions go to `--out-cache`; give each parallel process its own.
- Logs go to `runs/presentism/<tag>/<condition>_s<seed>.jsonl`, one line per
  completion with `raw`, `text`, `filter_raw`, `filter_final`, `n_regen`,
  `rag`, `prev_speaker`, `on_record` and `source`.

## 6. Decisions for the authors

1. **Where the guards live.** Should they be wired into `kamer/agents/agent.py`
   (and the backbone check rerun), or should the paper describe them as an
   evaluation-time layer? Today the paper describes code the reported runs
   did not use.
2. **Debate context.** Keep it on in all conditions (recommended). It changes
   what agents perceive, so it should be stated in §Setup.
3. **Statements to revisit** in `www.tex` once new numbers exist (not edited
   here):
   - the abstract's "No modern vocabulary entered the simulated record";
   - the Audit paragraph;
   - the "400 completions per run" setup note;
   - the historian review, which needs a sentence on the rewrite pass if
     item 0.6 is confirmed.
4. **`whip_note`.** Rename it to a period object, e.g. a *kamerclub*
   circular, or keep it as a documented example of the world introducing
   presentism.
