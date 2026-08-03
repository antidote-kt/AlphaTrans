#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME=${1:?Usage: $0 <project_name>}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

PYTHONPATH="$REPO_ROOT/arkts_src/phase_b_static_analysis" \
  python "$REPO_ROOT/arkts_src/phase_b_static_analysis/arkts_run_static_analysis.py" "$PROJECT_NAME"
