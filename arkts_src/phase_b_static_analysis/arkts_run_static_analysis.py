#!/usr/bin/env python3
"""第二阶段统一入口：一次分析，同时生成 query outputs、schema 和报告。"""

from __future__ import annotations

import argparse

from arkts_analysis import analyze_project
from arkts_create_schema import create_schemas_from_analysis
from arkts_export_query_outputs import export_query_outputs_from_analysis
from arkts_extract_call_graph import attach_calls
from arkts_generate_phase_report import generate_report


# 执行统一第二阶段流程。
def run(project_name: str) -> None:
    # AST 和 ArkIR 只在这里执行一次，后续消费者共享同一份合并结果。
    analysis = analyze_project(project_name)
    output_dir, counts = export_query_outputs_from_analysis(analysis)
    print(f"QUERY_OUTPUTS={output_dir}")
    print(" ".join(f"{name}={count}" for name, count in counts.items()))

    schema_dir, schema_counts = create_schemas_from_analysis(analysis)
    print(f"SCHEMAS={schema_dir}")
    print(" ".join(f"{name}={value}" for name, value in schema_counts.items()))

    attached, skipped = attach_calls(project_name)
    print(f"CALLS_ATTACHED={attached}")
    print(f"CALLS_SKIPPED={skipped}")
    print(f"REPORT={generate_report(project_name)}")


# 处理命令行并启动脚本。
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()
    run(args.project_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
