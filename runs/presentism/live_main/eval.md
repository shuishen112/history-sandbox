# Presentism audit — gpt-4o-mini, seeds 7/11/19

Holdout: 14731 TK speeches 1890–1899 (first 480 chars). Lexicon terms attested in the holdout and not counted: aanpakken, budget, collega, communicatie, duurzaam, efficient, en_issue, en_okay, geachte_voorzitter, meneer, minister_president, moderne_wereld, netwerk, samenleving, stabiliteit, uitdaging.

## record

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| Handelingen 1890–1899 | 14731 | 0.0 | 0.0 | 1.2 | 0.0 | 28.9 | 0.6 |
| ga · 14628 turns | 14010 | 10.5 [8–14] | 3.2 [3–4] | 93.4 | 18.0 | 1.4 [1–2] | 49.9 [48–51] |
| ga_periodprompt · 14628 turns | 13995 | 5.0 [2–9] | 0.8 [0–2] | 27.3 | 27.1 | 7.2 [6–8] | 34.2 [30–39] |
| kamer_noguard · 615 turns | 615 | 3.6 [2–6] | 0.2 [0–1] | 26.1 | 37.4 | 10.6 [7–14] | 26.2 [21–31] |
| kamer_full (pre-filter) · 615 turns | 615 | 2.3 [0–5] | 0.3 [0–1] | 27.3 | 0.0 | 8.9 [7–11] | 23.7 [17–30] |
| kamer_full (post-filter) | 615 | 0.3 [0–1] | 0.3 [0–1] | 27.4 | 0.0 | 8.8 [7–11] | 22.9 [17–29] |

## floor

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| Handelingen 1890–1899 | 14731 | 0.0 | 0.0 | 1.2 | 0.0 | 28.9 | 0.6 |
| ga · 16788 turns | 14975 | 10.2 [8–14] | 3.1 [2–4] | 94.2 | 18.2 | 1.3 [1–2] | 46.9 [46–48] |
| ga_periodprompt · 16788 turns | 14452 | 5.0 [2–9] | 0.8 [0–2] | 27.4 | 27.1 | 7.0 [6–8] | 33.4 [29–38] |
| kamer_noguard · 2775 turns | 1227 | 2.7 [2–4] | 0.1 [0–0] | 27.6 | 29.4 | 8.1 [5–11] | 25.7 [22–30] |
| kamer_full (pre-filter) · 2775 turns | 989 | 2.1 [1–4] | 0.2 [0–1] | 28.6 | 0.0 | 7.2 [5–9] | 25.0 [20–30] |
| kamer_full (post-filter) | 989 | 0.2 [0–1] | 0.2 [0–1] | 28.6 | 0.0 | 7.1 [5–9] | 24.2 [19–29] |

## dialogue

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| ga · 751 turns | 738 | 2.7 [1–4] | 0.1 [0–1] | 99.2 | – | 2.7 [1–4] | 7.6 [4–11] |
| ga_periodprompt · 751 turns | 738 | 1.6 [1–3] | 0.0 [0–0] | 29.2 | – | 2.3 [1–4] | 32.1 [27–37] |
| kamer_noguard · 756 turns | 743 | 1.7 [1–3] | 0.0 [0–0] | 39.7 | – | 3.1 [2–5] | 37.8 [33–43] |
| kamer_full (pre-filter) · 756 turns | 743 | 1.5 [0–3] | 0.0 [0–0] | 45.7 | – | 3.5 [2–6] | 33.5 [30–37] |
| kamer_full (post-filter) | 743 | 0.0 [0–0] | 0.0 [0–0] | 45.4 | – | 3.4 [2–5] | 33.4 [30–37] |

## interview

| condition | distinct completions | modern vocab % | audit-half % | modern spelling % | modern vocative % | adversarial % | consensus % |
|---|---|---|---|---|---|---|---|
| ga · 450 turns | 450 | 14.7 [11–18] | 0.9 [0–2] | 49.9 | – | 0.9 [0–2] | 18.4 [15–23] |
| ga_periodprompt · 450 turns | 450 | 13.3 [10–17] | 0.4 [0–1] | 48.1 | – | 0.4 [0–1] | 16.0 [13–20] |
| kamer_noguard · 450 turns | 450 | 16.7 [13–21] | 1.6 [0–3] | 49.0 | – | 3.1 [2–5] | 14.0 [10–18] |
| kamer_full (pre-filter) · 450 turns | 450 | 18.4 [15–23] | 0.4 [0–1] | 68.1 | – | 2.2 [1–4] | 19.3 [15–24] |
| kamer_full (post-filter) | 450 | 2.7 [1–4] | 0.4 [0–1] | 67.3 | – | 2.0 [1–4] | 15.3 [11–20] |

## self-description errors (interviews)

| condition | self-knowledge answers | error % | all answers | error % | S-G as chamber % | top codes |
|---|---|---|---|---|---|---|
| ga | 75 | 4.0 [1–11] | 450 | 0.9 | 0.0 | claims_minister×3, claims_voorzitter×1 |
| ga_periodprompt | 75 | 4.0 [1–11] | 450 | 0.7 | 0.0 | claims_minister×3 |
| kamer_noguard | 75 | 4.0 [1–11] | 450 | 1.1 | 0.0 | claims_minister×3, claims_voorzitter×2 |
| kamer_full | 75 | 4.0 [1–11] | 450 | 0.7 | 0.0 | claims_minister×3 |

## coverage (LLM vs heuristic lines in the simulated Handelingen)

| condition | seed | record lines | LLM | fallback | completions requested |
|---|---|---|---|---|---|
| ga | 7 | 4876 | 4876 | 0 | 6017 |
| ga | 11 | 4876 | 4876 | 0 | 5992 |
| ga | 19 | 4876 | 4876 | 0 | 5980 |
| ga_periodprompt | 7 | 4876 | 4876 | 0 | 6017 |
| ga_periodprompt | 11 | 4876 | 4876 | 0 | 5992 |
| ga_periodprompt | 19 | 4876 | 4876 | 0 | 5980 |
| kamer_full | 7 | 205 | 205 | 0 | 1355 |
| kamer_full | 11 | 205 | 205 | 0 | 1381 |
| kamer_full | 19 | 205 | 205 | 0 | 1363 |
| kamer_noguard | 7 | 205 | 205 | 0 | 1318 |
| kamer_noguard | 11 | 205 | 205 | 0 | 1335 |
| kamer_noguard | 19 | 205 | 205 | 0 | 1328 |
