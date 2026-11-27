#!/usr/bin/env bash
# ci01-heartbeat: tells app01 that ci01 is up and what the GitHub runner is doing. Runs on ci01 every 30 seconds
# (systemd timer from heartbeat.yml), as the "heartbeat" user. On app01, its key can only save this message.
#
#   busy     the runner service is active and a job is running (Runner.Worker process)
#   idle     the runner service is active, no job
#   stopped  the runner service isn't active
set -euo pipefail

app01="${APP01_IP:?APP01_IP not set}"
deploy_user="${DEPLOY_USER:-deploy}"
key="${HOME}/.ssh/id_heartbeat"

if systemctl list-units --type=service --state=active --no-legend 'actions.runner.*' | grep -q .; then
  if pgrep -f 'Runner.Worker' >/dev/null; then runner=busy; else runner=idle; fi
else
  runner=stopped
fi

printf '{"runner":"%s"}\n' "${runner}" |
  ssh -i "${key}" -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes "${deploy_user}@${app01}"
