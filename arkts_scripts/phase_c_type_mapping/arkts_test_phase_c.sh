#!/usr/bin/env bash
set -euo pipefail
project=${1:?project name required}
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
PYTHONPATH="$repo_root" python3 -m unittest discover -s "$repo_root/arkts_tests/phase_c_type_mapping" -v
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_c_type_mapping.arkts_collect_types "$project"
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_c_type_mapping.arkts_crawl_type_desc "$project"
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_c_type_mapping.arkts_translate_types "$project"
