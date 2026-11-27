#!/usr/bin/env bash
# deploy.sh -> deploys the merged commit to app01, then smoke-tests every app through Caddy, like a browser would.
# Runs ONLY on ci01's runner, from deploy.yml, after a merge to main (or a manual run on main).
#
#   1. copy deploy/ (compose.yml, Caddyfile) to app01 and write its .env (images, tag, address)
#   2. docker compose pull + up on app01, as the deploy user (SSH key ~/.ssh/id_deploy from deploy-access.yml)
#   3. record the deploy for the dashboard, and remove images unused for 3 days (keeps app01's small disk free)
#   4. smoke tests: the dashboard on the plain address, every other app on <app>.<app01-ip>.nip.io
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/lib/image.sh
source scripts/lib/image.sh

# app01's address comes from the inventory: one place to change it.
app01="$(cd ansible && ansible-inventory --host app01 |
  python3 -I -c 'import json, sys; print(json.load(sys.stdin)["ansible_host"])')"
deploy_user="${DEPLOY_USER:-deploy}"
lab=/srv/homelab-lite
ssh_opts=(-i "${HOME}/.ssh/id_deploy" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10)
target="${deploy_user}@${app01}"
tag="$(image_tag)"
# shellcheck disable=SC2029 # the commands are built here on purpose (fixed paths, no user input)
on_app01() { ssh "${ssh_opts[@]}" "${target}" "$@"; }

echo "== 1. Copy deploy/ to app01 (${app01})"
scp "${ssh_opts[@]}" deploy/compose.yml deploy/Caddyfile "${target}:${lab}/deploy/"
printf 'IMAGE_PREFIX=%s\nIMAGE_TAG=%s\nAPP01_IP=%s\n' "$(image_prefix)" "${tag}" "${app01}" |
  on_app01 "cat > ${lab}/deploy/.env"

echo "== 2. Pull and start (commit ${tag})"
on_app01 "cd ${lab}/deploy && docker compose pull --quiet && docker compose up -d"

echo "== 3. Record the deploy; tidy old images"
printf '{"commit":"%s","time":"%s"}\n' "${tag}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" |
  on_app01 "cat > ${lab}/status/last-deploy.json"
on_app01 "docker image prune -af --filter until=72h" >/dev/null

echo "== 4. Smoke tests"
for _ in $(seq 1 30); do curl -fs -o /dev/null "http://${app01}/health" && break; sleep 2; done
python3 -I -c 'import json, sys; print("\n".join(json.load(sys.stdin)))' <<<"$(scripts/list-apps.sh)" |
  while read -r app; do
    if [ "${app}" = "dashboard" ]; then
      "apps/${app}/tests/smoke.sh" "http://${app01}"
    else
      "apps/${app}/tests/smoke.sh" "http://${app01}" "${app}.${app01}.nip.io"
    fi
  done
echo "Deployed ${tag}. Dashboard: http://${app01}/"
