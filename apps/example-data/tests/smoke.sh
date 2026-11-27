#!/usr/bin/env bash
# smoke.sh BASE_URL [HOST_HEADER] -> checks example-data answers: /health says ok, and the page shows its table.
set -euo pipefail
base="${1:?usage: smoke.sh BASE_URL [HOST_HEADER]}"
host=()
[ -n "${2:-}" ] && host=(-H "Host: $2")

curl -fsS --max-time 10 "${host[@]}" "${base}/health" | grep -qx ok || { echo "FAIL: /health" >&2; exit 1; }
curl -fsS --max-time 10 "${host[@]}" "${base}/" | grep -q "<table>" || { echo "FAIL: page" >&2; exit 1; }
echo "example-data: ok"
