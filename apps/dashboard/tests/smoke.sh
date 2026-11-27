#!/usr/bin/env bash
# smoke.sh BASE_URL [HOST_HEADER] -> checks the dashboard answers: /health says ok, and the page has its title.
set -euo pipefail
base="${1:?usage: smoke.sh BASE_URL [HOST_HEADER]}"
host=()
[ -n "${2:-}" ] && host=(-H "Host: $2")

curl -fsS --max-time 10 "${host[@]}" "${base}/health" | grep -qx ok || { echo "FAIL: /health" >&2; exit 1; }
curl -fsS --max-time 10 "${host[@]}" "${base}/" | grep -q "homelab-lite status" || { echo "FAIL: page" >&2; exit 1; }
echo "dashboard: ok"
