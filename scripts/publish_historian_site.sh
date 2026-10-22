#!/usr/bin/env bash
# Publish historian-site/ as the gh-pages branch of a GitHub repo.
#
#   bash scripts/publish_historian_site.sh
#   bash scripts/publish_historian_site.sh https://github.com/<user>/<repo>.git
#
# Then: Settings → Pages → Deploy from branch → gh-pages / (root).
# Never force-pushes main — only the gh-pages branch.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="$ROOT/historian-site"
REMOTE="${1:-}"
if [ -z "$REMOTE" ]; then
  REMOTE="$(git -C "$ROOT" remote get-url origin)"
fi
[ -f "$SITE/data/interviews.json" ] || {
  echo "No interviews.json; run: PYTHONPATH=. python scripts/build_historian_site.py"
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$SITE"/. "$TMP"/
cd "$TMP"
git init -q -b gh-pages
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-$(git -C "$ROOT" config --get user.name || echo site)}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-$(git -C "$ROOT" config --get user.email || echo site@localhost)}" \
    commit -q -m "Kamer historian lab ($(date +%Y-%m-%d))"
git remote add origin "$REMOTE"
git push -f origin gh-pages
echo "Pushed gh-pages to $REMOTE"
echo "Enable GitHub Pages: Settings → Pages → branch gh-pages, / (root)."
echo "URL will be https://<user>.github.io/<repo>/"
