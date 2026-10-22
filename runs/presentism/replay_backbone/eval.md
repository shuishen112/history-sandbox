# Presentism audit — existing gpt-4o-mini outputs (backbone-check cache replay + s1_llm.json seed-7 interviews)

Holdout: 14731 TK speeches 1890–1899 (first 480 chars). Lexicon terms attested in the holdout and not counted: aanpakken, budget, collega, communicatie, duurzaam, efficient, en_issue, en_okay, geachte_voorzitter, meneer, minister_president, moderne_wereld, netwerk, samenleving, stabiliteit, uitdaging.

## record

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| Handelingen 1890–1899 | 14731 | 0.0 | 0.0 | 1.2 | 0.0 | 28.9 | 0.6 |
| ga · 626 turns | 269 | 6.3 [3–10] | 2.2 [1–4] | 69.5 | 45.4 | 0.0 [0–0] | 10.8 [6–15] |
| kamer_noguard · 60 turns | 7 | 0.0 [0–0] | 0.0 [0–0] | 77.8 | 57.1 | 0.0 [0–0] | 0.0 [0–0] |

## floor

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| Handelingen 1890–1899 | 14731 | 0.0 | 0.0 | 1.2 | 0.0 | 28.9 | 0.6 |
| ga · 626 turns | 269 | 6.3 [3–10] | 2.2 [1–4] | 69.5 | 45.4 | 0.0 [0–0] | 10.8 [6–15] |
| kamer_noguard · 60 turns | 7 | 0.0 [0–0] | 0.0 [0–0] | 77.8 | 57.1 | 0.0 [0–0] | 0.0 [0–0] |

## dialogue

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| ga · 5035 turns | 225 | 3.6 [2–6] | 0.4 [0–2] | 100.0 | – | 1.3 [0–3] | 3.6 [1–6] |
| kamer_noguard · 39398 turns | 734 | 9.8 [7–13] | 0.0 [0–0] | 44.5 | – | 2.0 [1–3] | 37.9 [34–42] |

## interview

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| ga · 150 turns | 150 | 29.3 [22–37] | 4.7 [2–8] | 100.0 | – | 1.3 [0–3] | 18.0 [13–25] |
| kamer_noguard · 150 turns | 150 | 36.0 [29–44] | 6.7 [3–11] | 100.0 | – | 1.3 [0–3] | 17.3 [11–24] |

## self-description errors (interviews)

| condition | self-knowledge answers | error % | all answers | error % | S-G as chamber % | top codes |
|---|---|---|---|---|---|---|
| ga | 25 | 64.0 [45–80] | 150 | 34.0 | 46.0 | lid_staten_generaal×48, mp_english×3, claims_journalist×1 |
| kamer_noguard | 25 | 16.0 [6–35] | 150 | 5.3 | 11.3 | lid_staten_generaal×6, voorzitter_staten_generaal×2 |

## coverage (LLM vs heuristic lines in the simulated Handelingen)

| condition | seed | record lines | LLM | fallback | completions requested |
|---|---|---|---|---|---|
| ga | 7 | 4876 | 186 | 4690 | 23012 |
| ga | 11 | 4876 | 202 | 4674 | 22996 |
| ga | 19 | 4876 | 238 | 4638 | 22984 |
| kamer_noguard | 7 | 205 | 20 | 185 | 18366 |
| kamer_noguard | 11 | 205 | 20 | 185 | 18337 |
| kamer_noguard | 19 | 205 | 20 | 185 | 18351 |
