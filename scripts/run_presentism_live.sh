#!/usr/bin/env bash
# Paid gpt-4o-mini run of the presentism audit (kamer/PRESENTISM_EVAL.md, section 5),
# one process per condition and seed, then scoring against the 1890-1899 holdout.
#
#   OPENAI_API_KEY=... bash scripts/run_presentism_live.sh
#
# Each process has its own --out-cache and a hard --max-completions stop.
# Logs: runs/presentism/$TAG/<condition>_s<seed>.jsonl; stdout in runs/presentism/$TAG/stdout/.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${OPENAI_API_KEY:-}${MAROON_API_KEY:-}" ]]; then
  echo "set OPENAI_API_KEY (or MAROON_API_KEY) first" >&2
  exit 1
fi

TAG=${TAG:-live_main}
CONDITIONS=${CONDITIONS:-"ga kamer_noguard kamer_full ga_periodprompt"}
SEEDS=${SEEDS:-"7 11 19"}
OUT=runs/presentism/$TAG
mkdir -p "$OUT/caches" "$OUT/stdout"

pids=()
for c in $CONDITIONS; do
  # About 6,000 completions per GA-world run and 1,500 per Kamer run (count backend).
  case $c in
    ga | ga_periodprompt) budget=8000 ;;
    *) budget=2500 ;;
  esac
  for s in $SEEDS; do
    PYTHONPATH=. python3 scripts/run_presentism.py --backend live --live \
      --max-completions "$budget" --conditions "$c" --seeds "$s" --tag "$TAG" \
      --out-cache "$OUT/caches/${c}_s${s}.jsonl" \
      >"$OUT/stdout/${c}_s${s}.log" 2>&1 &
    pids+=("$!")
    echo "started $c seed $s (budget $budget, pid $!)"
  done
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=$((failed + 1))
done
if ((failed)); then
  echo "$failed run(s) failed; see $OUT/stdout/" >&2
  exit 1
fi

PYTHONPATH=. python3 scripts/eval_presentism.py --logs "$OUT" \
  --label "gpt-4o-mini, seeds ${SEEDS// //}" --out "$OUT/eval.json"
echo "done: $OUT/eval.json and $OUT/eval.md"
