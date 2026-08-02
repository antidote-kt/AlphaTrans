#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <project_name>" >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PROJECT_DIR="$REPO_ROOT/arkts_projects/automated_reduced_projects/$1"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Error: ArkTS project not found: $PROJECT_DIR" >&2
  exit 1
fi

if [ -x "$PROJECT_DIR/hvigorw" ]; then
  (cd "$PROJECT_DIR" && ./hvigorw assembleHap)
  echo "BUILD_STATUS=PASS"
elif command -v hvigorw >/dev/null 2>&1; then
  (cd "$PROJECT_DIR" && hvigorw assembleHap)
  echo "BUILD_STATUS=PASS"
elif [ -x "$REPO_ROOT/../command-line-tools/bin/hvigorw" ]; then
  (cd "$PROJECT_DIR" && "$REPO_ROOT/../command-line-tools/bin/hvigorw" assembleHap)
  echo "BUILD_STATUS=PASS"
elif command -v hvigor >/dev/null 2>&1; then
  (cd "$PROJECT_DIR" && hvigor assembleHap)
  echo "BUILD_STATUS=PASS"
else
  echo "BUILD_STATUS=SKIP (Hvigor executable not available)"
fi

