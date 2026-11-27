#!/usr/bin/env bash
# build-image.sh APP [push] -> builds apps/APP, runs it the way app01 does (read-only, no capabilities),
# smoke-tests it, scans the image with Trivy, and only with "push" (after a merge) pushes it to GitHub's registry
# as ghcr.io/<owner>/<repo>-APP:<commit>.
# GitHub-hosted runners only: they have Docker; ci01 and app01 never build anything.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/lib/image.sh
source scripts/lib/image.sh
app="${1:?usage: build-image.sh APP [push]}"
mode="${2:-}"

image="$(image_name "${app}")"
docker build --pull=false \
  --label "org.opencontainers.image.source=https://github.com/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY not set}" \
  -t "${image}" "apps/${app}"

name="smoke-${app}-$$"
cleanup() { docker rm -f "${name}" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "${name}" -p 127.0.0.1::8080 --read-only --cap-drop ALL \
  --security-opt no-new-privileges "${image}" >/dev/null
port="$(docker port "${name}" 8080 | head -1 | sed 's/.*://')"
for _ in $(seq 1 30); do curl -fs -o /dev/null "http://127.0.0.1:${port}/health" && break; sleep 1; done
"apps/${app}/tests/smoke.sh" "http://127.0.0.1:${port}" || { docker logs "${name}" 2>&1 | tail -20; exit 1; }

scripts/security-scan.sh image "${image}"

if [ "${mode}" = "push" ]; then
  echo "${GITHUB_TOKEN:?GITHUB_TOKEN not set}" | docker login ghcr.io -u "${GITHUB_ACTOR:?GITHUB_ACTOR not set}" --password-stdin
  trap 'cleanup; docker logout ghcr.io >/dev/null' EXIT
  docker push "${image}"
  echo "Pushed ${image}"
fi
