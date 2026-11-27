#!/usr/bin/env bash
# smoke.sh BASE_URL [HOST_HEADER] -> the real-feed check.
#   Fails if the news app doesn't answer. Only WARNS if no headlines came back (e.g. the feed is down),
#   so a publisher's outage doesn't block your deploys.
set -euo pipefail
base="${1:?usage: smoke.sh BASE_URL [HOST_HEADER]}"
host=()
[ -n "${2:-}" ] && host=(-H "Host: $2")

curl -fsS --max-time 10 "${host[@]}" "${base}/health" | grep -qx ok || { echo "FAIL: /health" >&2; exit 1; }
page="$(curl -fsS --max-time 30 "${host[@]}" "${base}/")" || { echo "FAIL: page" >&2; exit 1; }
count="$(grep -o "class='headline'" <<<"${page}" | wc -l)"
if [ "${count}" -eq 0 ]; then
  echo "::warning title=news: no headlines::The news page loads, but no headlines came back. Is the feed (NEWS_FEED_URL) up?"
else
  echo "news: ok, ${count} headlines from the live feed"
fi
