#!/usr/bin/env bash
# Lint checks for every PR: yamllint, Ansible syntax-check + ansible-lint, shellcheck, Python syntax.
# Pipeline YAML only calls scripts like this one, so the logic can move to another CI system later.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== yamllint =="
yamllint -d relaxed .

echo "== ansible syntax-check =="
for pb in ansible/playbooks/*.yml; do
  ( cd ansible && ansible-playbook --syntax-check "playbooks/$(basename "${pb}")" )
done

echo "== ansible-lint =="
( cd ansible && ansible-lint playbooks/ )

echo "== shellcheck =="
command -v shellcheck >/dev/null || { echo "shellcheck not installed" >&2; exit 1; }
shellcheck scripts/*.sh scripts/lib/*.sh apps/*/tests/*.sh ansible/playbooks/files/*.sh

echo "== python syntax =="
python3 -m py_compile apps/*/main.py apps/*/tests/*.py ansible/playbooks/files/*.py
find . -name __pycache__ -type d -prune -exec rm -rf {} +

echo "All checks passed."
