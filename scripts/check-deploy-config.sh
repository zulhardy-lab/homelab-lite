#!/usr/bin/env bash
# check-deploy-config.sh -> checks deploy/ before anything reaches app01 (GitHub-hosted runners only):
#   1. docker compose accepts compose.yml
#   2. Caddy accepts the Caddyfile (run inside the exact pinned Caddy image, which also proves the digest is right)
#   3. Trivy scans that Caddy image
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== compose.yml"
IMAGE_PREFIX=example.invalid/x- IMAGE_TAG=test APP01_IP=192.0.2.10 \
  docker compose -f deploy/compose.yml config --quiet
echo "compose.yml: ok"

caddy_image="$(grep -oE 'caddy:[^[:space:]]+@sha256:[0-9a-f]{64}' deploy/compose.yml | head -1)"
[ -n "${caddy_image}" ] || { echo "FAIL: no digest-pinned Caddy image in deploy/compose.yml" >&2; exit 1; }

echo "== Caddyfile (in ${caddy_image})"
docker pull -q "${caddy_image}"
docker run --rm "${caddy_image}" caddy version
docker run --rm -e APP01_IP=192.0.2.10 -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  "${caddy_image}" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
echo "Caddyfile: ok"

scripts/security-scan.sh image "${caddy_image}"
