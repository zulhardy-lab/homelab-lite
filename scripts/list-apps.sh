#!/usr/bin/env bash
# list-apps.sh -> JSON list of the apps: every folder apps/<name>/ that has a Dockerfile.
set -euo pipefail
cd "$(dirname "$0")/.."
for d in apps/*/Dockerfile; do
  [ -f "${d}" ] && basename "$(dirname "${d}")"
done | python3 -I -c 'import json, sys; print(json.dumps(sorted(l.strip() for l in sys.stdin if l.strip())))'
