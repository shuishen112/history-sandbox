# Kamer historian lab

Same labelling pattern as the earlier historian lab: five static pages, a bottom bar, download-a-JSON.

Live (GitHub Pages): https://shuishen112.github.io/history-sandbox/

1. **Scheme** — speaker fields and sandbox roles  
2. **Names** — OCR / name / party review  
3. **People** — the 25 S1 agents  
4. **Conversations** — blinded TrueSkill pairs  
5. **Standing orders** — map, Reglement, floor clips  

Raters keep work in the browser, then **Download my work** and email the file.

```bash
PYTHONPATH=. python scripts/build_historian_site.py
python -m http.server 8766 --directory historian-site
# publish the site repo (does not touch the paper repo's main):
bash scripts/publish_historian_site.sh
PYTHONPATH=. python scripts/score_historian_labels.py exports/*.json
```
