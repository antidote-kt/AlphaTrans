#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME=${1:?Usage: $0 <project_name>}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

bash "$SCRIPT_DIR/arkts_generate_query_outputs.sh" "$PROJECT_NAME"
bash "$SCRIPT_DIR/arkts_create_schema.sh" "$PROJECT_NAME"
bash "$SCRIPT_DIR/arkts_extract_call_graph.sh" "$PROJECT_NAME"
PYTHONPATH="$REPO_ROOT/arkts_src/phase_b_static_analysis" \
  python "$REPO_ROOT/arkts_src/phase_b_static_analysis/arkts_generate_phase_report.py" "$PROJECT_NAME"
