#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <project_name>" >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PROJECT_NAME=$1
ORIGINAL_DIR="$REPO_ROOT/arkts_projects/original_projects/$PROJECT_NAME"
REDUCED_DIR="$REPO_ROOT/arkts_projects/automated_reduced_projects/$PROJECT_NAME"

if [ ! -d "$ORIGINAL_DIR" ]; then
  echo "Error: ArkTS project not found: $ORIGINAL_DIR" >&2
  exit 1
fi

mkdir -p "$REDUCED_DIR"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude=.git --exclude=build --exclude=node_modules --exclude=oh_modules \
    "$ORIGINAL_DIR/" "$REDUCED_DIR/"
else
  (cd "$ORIGINAL_DIR" && tar --exclude=.git --exclude=build \
    --exclude=node_modules --exclude=oh_modules -cf - .) | (cd "$REDUCED_DIR" && tar -xf -)
fi

echo "ArkTS project copied to $REDUCED_DIR"

