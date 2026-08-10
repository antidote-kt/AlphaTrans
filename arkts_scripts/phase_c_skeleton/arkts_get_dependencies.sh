#!/usr/bin/env bash
set -euo pipefail
project=${1:?project name required}
# 从脚本目录定位仓库根目录，保证在任意工作目录下均可执行。
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
# 使用独立的 arkts_src Python 包，不修改原版 src。
PYTHONPATH="$repo_root" python3 -m arkts_src.phase_c_skeleton.arkts_get_dependencies "$project"
