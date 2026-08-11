#!/usr/bin/env bash
set -euo pipefail
project=${1:?project name required}
model=${2:-deepseek-v4-flash}
prompt_type=${3:-body}
temperature=${4:-0.0}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_d_fragment_translation.arkts_create_test_method_map \
  "$project" "$model" "$prompt_type" "$temperature"
