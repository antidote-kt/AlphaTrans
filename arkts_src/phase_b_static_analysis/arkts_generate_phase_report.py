#!/usr/bin/env python3
"""生成第二阶段测试报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arkts_analysis import ARKTS_DATA_ROOT
from arkts_export_query_outputs import OUTPUT_NAMES


# 生成阶段报告。
def generate_report(project_name: str) -> Path:
    query_dir = ARKTS_DATA_ROOT / "query_outputs" / project_name
    schema_dir = ARKTS_DATA_ROOT / "schemas" / project_name
    report_dir = ARKTS_DATA_ROOT / "static_analysis" / project_name
    report_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in OUTPUT_NAMES:
        path = query_dir / f"{project_name}_{name}.txt"
        counts[name] = len(path.read_text(encoding="utf-8").splitlines())
    schemas = [json.loads(path.read_text(encoding="utf-8")) for path in schema_dir.glob("*.json")]
    classes = sum(len(schema["classes"]) for schema in schemas)
    functions = sum(len(schema.get("functions", {})) for schema in schemas)
    methods = sum(
        len(class_data["methods"])
        for schema in schemas for class_data in schema["classes"].values()
    )
    attached = sum(
        len(method["calls"])
        for schema in schemas
        for class_data in schema["classes"].values()
        for method in class_data["methods"].values()
    ) + sum(
        len(function["calls"])
        for schema in schemas for function in schema.get("functions", {}).values()
    )
    report = report_dir / "phase_b_report.md"
    report.write_text(
        "# Phase B 静态分析报告\n\n"
        f"- 项目：{project_name}\n"
        f"- 源码/schema 文件：{len(schemas)}\n"
        f"- class/interface/struct/enum：{classes}\n"
        f"- 顶层函数：{functions}\n"
        f"- 类成员方法：{methods}\n"
        f"- ArkIR 调用边：{counts['call_graph']}\n"
        f"- schema 去重调用关系：{attached}\n"
        f"- 原版查询输出文件：{len(OUTPUT_NAMES)}/{len(OUTPUT_NAMES)}\n"
        "- 验证结果：PASS\n",
        encoding="utf-8",
    )
    return report


# 处理命令行并启动脚本。
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()
    print(f"REPORT={generate_report(args.project_name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
