#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME=${1:?Usage: $0 <project_name>}
REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PYTHONPATH="$REPO_ROOT/arkts_src/phase_b_static_analysis" \
  python "$REPO_ROOT/arkts_src/phase_b_static_analysis/arkts_extract_call_graph.py" "$PROJECT_NAME"
