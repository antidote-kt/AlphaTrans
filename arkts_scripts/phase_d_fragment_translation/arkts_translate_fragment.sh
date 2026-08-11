#!/usr/bin/env bash
set -euo pipefail
project=${1:?project name required}
temperature=${2:?temperature required}
model=${3:?model name required}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_d_fragment_translation.arkts_translate_fragment \
  "$project" "$temperature" "$model"
