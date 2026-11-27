# AI rules — homelab-lite

Rules for any AI coding agent working in this repo. AI tools don't read this file on their own: tell your tool to
read `AI-RULES.md` and follow it before it changes anything.

Adapted from zulhardy/infrastructure-agents-guide (credential management, change control, guardrails, risk), the same
rules as zulhardy-lab/homelab, shortened for a learning lab. Where possible each rule is also enforced by a setting
("Enforced by"), because rules in a prompt are the weakest layer.

## What this repo is

- A two-VM DevOps lab for laptops: **ci01** (GitHub runner, Ansible) and **app01** (Docker, Caddy, the apps).
- The apps under `apps/` are built and scanned on GitHub's machines and deployed to app01 after a merge.
- PUBLIC repo: everything in it is visible to anyone.

## Autonomy level

- **Propose only.** The agent writes code and opens pull requests. The repo owner reviews and merges.
- The agent never merges, deploys, or runs commands on the VMs.

## Hard rules — never break these

1. Never push directly to `main`. One branch per change: `feat/…`, `fix/…`, `chore/…`.
   - Enforced by: the `protect-main` ruleset (PR + passing checks required).
2. Never run commands on the VMs or on the laptop that hosts them. Changes reach the VMs only through merged PRs, or
   through steps the repo owner runs.
3. Never merge or approve a pull request, and never change repository settings or rulesets.
4. Never store, request, print or commit credentials: SSH private keys, passwords, runner tokens, access tokens,
   `.env` files with secrets. The repo owner enters every secret.
   - Enforced by: `.gitignore`; secret scanning and push protection; Trivy's secret scan on every PR.
5. The self-hosted runner (ci01) may only be used by workflows triggered by a push to `main` or a manual run. Never
   target it from `pull_request` or `pull_request_target` workflows; PR checks run on GitHub-hosted runners.
   - Enforced by: fork PR workflows need the owner's approval.
6. Never commit anything that shouldn't be public: secrets, real passwords, personal data, copyrighted content
   that isn't licensed for it.
7. Never give a container the Docker socket, extra capabilities or a writable filesystem without the owner's
   explicit request.
8. Pin versions: actions by commit SHA, base images by digest, downloads by checksum, Python packages by hash.
   Never `latest`.
9. Don't open a ready-for-review PR until the lint checks have run. If they still fail after 10 attempts, open a
   DRAFT PR titled `[not converged]` and never describe it as a fix.
10. Anything irreversible (deleting data, volumes, VMs, users, keys, packages) is done by the repo owner.
11. When something is unclear, stop and ask. Fail safe, not fail open.

Changes outside `ansible/`, `apps/`, `deploy/`, `scripts/` and `docs/` are allowed only when they aren't
destructive, and only after telling the repo owner first. Changes to `.github/workflows/` need an explicit request.

## Every pull request includes

- **Summary**: what changed and why
- **Changes**: the files
- **Validation**: lint, test and scan results
- **Impact**: what changes on ci01 or app01
- Anything destructive, called out at the top

## Lab conventions

- Pipeline logic lives in `scripts/`; workflow YAML stays thin.
- Image builds, tests and scans run on GitHub-hosted runners. ci01 has no Docker.
- An app = `apps/<name>/` with `Dockerfile`, `main.py`, `tests/test_*.py` (unit tests, required), `tests/smoke.sh`
  (smoke test, required), a `/health` endpoint; plus its service in `deploy/compose.yml` and its block in
  `deploy/Caddyfile`.

## Emergency stop

The repo owner disables GitHub Actions for the repo, and/or stops the runner on ci01:
`sudo systemctl stop 'actions.runner.*'`.
