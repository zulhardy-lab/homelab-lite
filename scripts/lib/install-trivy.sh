# shellcheck shell=bash
# Sourced. install_trivy -> puts a verified Trivy binary on PATH (in $RUNNER_TEMP or /tmp).
#
# Why not the Trivy GitHub Actions: on 2026-03-19 attackers force-pushed most trivy-action and setup-trivy tags
# to credential-stealing code, and published a malicious Trivy v0.69.4 (CVE-2026-33634). This downloads one
# specific release straight from GitHub and checks it against a SHA-256 recorded here.
TRIVY_VERSION="0.76.2" # released 2026-11-05
TRIVY_SHA256="bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf" # trivy_0.76.2_Linux-64bit.tar.gz

install_trivy() {
  if command -v trivy >/dev/null && trivy --version 2>/dev/null | grep -q "Version: ${TRIVY_VERSION}$"; then
    return 0
  fi
  local dir="${RUNNER_TEMP:-/tmp}/trivy-${TRIVY_VERSION}"
  if [ ! -x "${dir}/trivy" ]; then
    mkdir -p "${dir}"
    local tgz="${dir}/trivy.tar.gz"
    curl -sSfL --max-time 300 -o "${tgz}" \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
    echo "${TRIVY_SHA256}  ${tgz}" | sha256sum -c - >/dev/null || { echo "Trivy checksum mismatch, refusing to run it." >&2; return 1; }
    tar -xzf "${tgz}" -C "${dir}" trivy
    rm -f "${tgz}"
  fi
  export PATH="${dir}:${PATH}"
  trivy --version | head -1
}
