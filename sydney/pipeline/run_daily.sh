#!/usr/bin/env bash
# Daily refresh. Usage: bash run_daily.sh BASE_DIR INBOX_DIR [--backtest]
set -euo pipefail
BASE="$1"; INBOX="$2"; shift 2
# New monthly NSW history (syd_events_YYYYMM.csv from fetch.py) -> store/events, then rebuild the daily history
mkdir -p "$BASE/store/events"; NEW=0
shopt -s nullglob
for f in "$INBOX"/syd_events_[0-9][0-9][0-9][0-9][0-9][0-9].csv; do
  b=$(basename "$f")
  if [ ! -f "$BASE/store/events/$b" ] || [ "$f" -nt "$BASE/store/events/$b" ]; then cp "$f" "$BASE/store/events/$b"; NEW=1; echo "new history file: $b"; fi
done
if [ "$NEW" = 1 ]; then python3 "$BASE/pipeline/build_history.py" "$BASE/store/events" "$BASE/store" | tail -1; fi
if [ "$NEW" = 1 ] || [ ! -f "$BASE/store/station_profile.json" ]; then python3 "$BASE/pipeline/station_profile.py" "$BASE" | tail -1; fi
python3 "$BASE/pipeline/update.py" "$BASE" "$INBOX"
python3 "$BASE/pipeline/model.py" "$BASE" "$@" | tail -1 | cut -c1-200
