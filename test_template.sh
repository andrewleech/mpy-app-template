#!/bin/bash
# Generate one variant of the template into a temporary directory and build it.
# Uses the same answer files as CI, so a local failure reproduces a CI failure.

set -e

VARIANTS=$(cd "$(dirname "$0")/test" && ls *.copier-answers.yml | sed 's/\.copier-answers\.yml$//')
TEMPLATE_DIR=$(cd "$(dirname "$0")" && pwd)

usage() {
  echo "Usage: $0 [variant|--all|--cleanup]"
  echo
  echo "Variants:"
  for v in $VARIANTS; do echo "  $v"; done
  exit 1
}

cleanup() {
  find "${TMPDIR:-/tmp}" -maxdepth 1 -type d -name "mpy_app_template_test_*" -print -exec rm -rf {} +
  exit 0
}

build_variant() {
  local variant="$1"
  local answers="$TEMPLATE_DIR/test/$variant.copier-answers.yml"
  [ -f "$answers" ] || { echo "No such variant: $variant"; usage; }

  local dest
  dest=$(mktemp -d "${TMPDIR:-/tmp}/mpy_app_template_test_${variant}_XXXXXX")
  echo "=== $variant -> $dest"

  # Through mpy-new-project, so the run takes the same path a user does.
  # --no-cache because uv reuses a wheel it built from a local path without
  # noticing the source changed, so edits appear to do nothing. Verified that
  # neither a new commit nor a dirty tree is enough to make it rebuild.
  uvx --no-cache --from "$TEMPLATE_DIR" mpy-new-project \
    --src "$TEMPLATE_DIR" --vcs-ref HEAD --data-file "$answers" "$dest"

  # The unix port has no board, so there is no firmware to build.
  if grep -q "^target_port: unix" "$answers"; then
    make -C "$dest" tests
  else
    make -C "$dest" system
    make -C "$dest" libs-only
    grep -q "^use_mboot: true" "$answers" && make -C "$dest" mboot
    make -C "$dest" tests
  fi
  make -C "$dest" checks
  echo "=== $variant OK ($dest)"
}

case "${1:-}" in
  --cleanup) cleanup ;;
  --all) for v in $VARIANTS; do build_variant "$v"; done ;;
  "") usage ;;
  -*) usage ;;
  *) build_variant "$1" ;;
esac
