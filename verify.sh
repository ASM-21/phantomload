#!/usr/bin/env bash
# Full check from a clean virtualenv, exactly as a new user would run it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The venv goes in a temp dir that is removed on exit, however the script ends.
# Without the trap this leaks roughly 400 MB per run, which is easy to miss
# until a build starts failing with I/O errors on a full disk.
TMPROOT="$(mktemp -d)"
cleanup() { rm -rf "$TMPROOT"; }
trap cleanup EXIT INT TERM
VENV="$TMPROOT/venv"
echo "building venv in $VENV"
python3 -m venv --copies "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -e "$HERE[dev]"
cd "$HERE"
echo "--- tests"; "$VENV/bin/python" -m pytest -q
cp -r results "$TMPROOT/committed_results"
echo "--- tracks"; "$VENV/bin/python" run_all.py
# Informative, never failing: library versions can move a last digit, and a
# check that false-fails gets ignored (METHOD rule 3). The claims guard below is
# the binding check on every figure the prose quotes.
echo "--- reproducibility"
changed=$( { diff -rq "$TMPROOT/committed_results" results || true; } \
  | { grep -v claim_ledger.csv || true; } | wc -l )
if [ "$changed" -eq 0 ]; then
  echo "every committed file in results/ except the claim ledger reproduced byte for byte"
else
  echo "$changed result files differ from the committed copies at the byte level"
fi
echo "--- claims"; "$VENV/bin/python" tools/check_claims.py
echo "--- ledger"; "$VENV/bin/python" tools/claim_ledger.py
echo "--- cli"; "$VENV/bin/python" -m phantomload zero-mass <("$VENV/bin/python" -c "
import pandas as pd
d=pd.read_csv('data/eia861_dr_utility_2016_2018.csv',dtype={'utility_number':str})
d['key']=d.utility_number+'_'+d.state
print(d.rename(columns={'potential_peak_mw':'potential_mw','actual_peak_mw':'actual_mw'})[['key','year','potential_mw','actual_mw']].to_csv(index=False))") | tail -1
echo "--- source"; "$VENV/bin/python" tools/check_source.py
echo "ALL GREEN"
