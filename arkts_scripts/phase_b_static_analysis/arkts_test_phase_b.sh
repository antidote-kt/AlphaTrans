#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME=${1:-RdbPlus}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

PYTHONPATH="$REPO_ROOT/arkts_src/phase_b_static_analysis" \
  python -m unittest discover -s "$REPO_ROOT/arkts_tests/phase_b_static_analysis" -p 'test_*.py'
bash "$SCRIPT_DIR/arkts_run_static_analysis.sh" "$PROJECT_NAME"
echo "PHASE_B_TEST=PASS"
