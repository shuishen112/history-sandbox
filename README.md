# MAROON historian lab

A static website for historian collaborators who do not need a programming
environment. They open the site, label notices and conversations in the
browser, then download a file and email it to the project.

The interaction copies the companion newspaper search site in
`historical_nlp/www_experiments/site`: GitHub Pages, no login, answers in
`localStorage`, CSV/JSON download. Newspaper **PDFs are not hosted** (they
are several gigabytes). Each notice links to the Royal Library page through
its permanent handle; the computer-read snippet is from
`historical_nlp/data/www_search.sqlite`, itself built from
`historical_nlp/mediastream_pdfs`.

## Pages

| Page | Task |
|---|---|
| `index.html` | Plain-language briefing |
| `schema.html` | Keep / change / drop the six notice types |
| `annotate.html` | Label ~300 OCR passages (Table 2) |
| `personas.html` | Review synthetic people (no documented individual) |
| `interviews.html` | Pairwise believability + historical plausibility |
| `rules.html` | Map, pass/curfew rules, advertising prior π |

## Rebuild the notice sample

```bash
podman exec conda bash -c 'cd /workspace/history-sandbox && PYTHONPATH=. python scripts/build_historian_site.py'
```

Needs the companion index at `/workspace/historical_nlp/data/www_search.sqlite`.

## Preview locally

```bash
cd historian-site && python3 -m http.server 8766
```

Then open http://localhost:8766 — do not open the HTML file directly from
disk; the browser will block `fetch` of `data/records.json`.

## Publish to GitHub Pages

```bash
bash scripts/publish_historian_site.sh https://github.com/<user>/<repo>.git
```

On GitHub: Settings → Pages → Deploy from branch `main`, folder `/`.
