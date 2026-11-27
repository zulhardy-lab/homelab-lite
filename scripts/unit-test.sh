#!/usr/bin/env bash
# unit-test.sh APP -> runs the app's unit tests (apps/APP/tests/test_*.py, Python unittest).
# An app without unit tests fails: every app needs some. Installs the app's pinned requirements first, if any.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/.."
app="${1:?usage: unit-test.sh APP}"

compgen -G "apps/${app}/tests/test_*.py" >/dev/null || { echo "FAIL: ${app} has no unit tests (apps/${app}/tests/test_*.py)" >&2; exit 1; }
if [ -f "apps/${app}/requirements.txt" ]; then
  python3 -m pip install --quiet --require-hashes -r "apps/${app}/requirements.txt"
fi
python3 -m unittest discover -s "apps/${app}/tests" -v
