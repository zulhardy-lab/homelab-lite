# shellcheck shell=bash
# Sourced. Image names on GitHub's container registry, the same in the build and the deploy:
#   image_prefix      -> ghcr.io/<owner>/<repo>-        (lowercase, as GHCR requires)
#   image_name APP    -> ghcr.io/<owner>/<repo>-APP:<commit>
# GITHUB_REPOSITORY and GITHUB_SHA are set by GitHub Actions.

image_prefix() {
  local repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY not set}"
  echo "ghcr.io/${repo,,}-"
}

image_tag() { echo "${IMAGE_TAG:-${GITHUB_SHA:?GITHUB_SHA not set}}"; }

image_name() { echo "$(image_prefix)${1:?image_name APP}:$(image_tag)"; }
