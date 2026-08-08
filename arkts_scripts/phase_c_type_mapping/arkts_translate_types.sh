#!/usr/bin/env bash
set -euo pipefail
project=${1:?project name required}
model=${2:-}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_c_type_mapping.arkts_translate_types "$project" "$model"
