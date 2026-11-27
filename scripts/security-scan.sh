#!/usr/bin/env bash
# security-scan.sh repo            -> secrets, misconfigurations (Dockerfiles, Kubernetes, Ansible...) and
#                                     dependency vulnerabilities in the whole repo
# security-scan.sh image IMAGE     -> vulnerabilities in a container image
#
# What fails the pipeline (prints everything HIGH and above either way):
#   - any secret found
#   - a HIGH or CRITICAL misconfiguration
#   - a CRITICAL vulnerability that has a fix available
# Free tool: Trivy (Apache-2.0), pinned binary with checksum (scripts/lib/install-trivy.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/lib/install-trivy.sh
source scripts/lib/install-trivy.sh
install_trivy

ignore=()
[ -f .trivyignore ] && ignore=(--ignorefile .trivyignore)

case "${1:-}" in
  repo)
    echo "== Report: HIGH and CRITICAL (secrets, misconfigurations, vulnerabilities)"
    trivy fs --quiet --scanners secret,misconfig,vuln --severity HIGH,CRITICAL --exit-code 0 "${ignore[@]}" .
    echo "== Gate: secrets"
    trivy fs --quiet --scanners secret --exit-code 1 "${ignore[@]}" .
    echo "== Gate: HIGH/CRITICAL misconfigurations"
    trivy fs --quiet --scanners misconfig --severity HIGH,CRITICAL --exit-code 1 "${ignore[@]}" .
    echo "== Gate: CRITICAL vulnerabilities with a fix"
    trivy fs --quiet --scanners vuln --severity CRITICAL --ignore-unfixed --exit-code 1 "${ignore[@]}" .
    ;;
  image)
    image="${2:?usage: security-scan.sh image IMAGE}"
    echo "== Report: HIGH and CRITICAL vulnerabilities in ${image}"
    trivy image --quiet --severity HIGH,CRITICAL --exit-code 0 "${ignore[@]}" "${image}"
    echo "== Gate: CRITICAL vulnerabilities with a fix, and secrets in the image"
    trivy image --quiet --scanners vuln,secret --severity CRITICAL --ignore-unfixed --exit-code 1 "${ignore[@]}" "${image}"
    ;;
  *) echo "usage: security-scan.sh repo | image IMAGE" >&2; exit 1 ;;
esac
echo "Security scan passed."
