#!/usr/bin/env python3
"""把 ArkTS call_graph 查询结果写回 schema 的 calls 字段。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arkts_analysis import ARKTS_DATA_ROOT, PROJECTS_ROOT
from arkts_create_schema import _schema_name


# 解析调用图位置。
def _split_location(value: str) -> tuple[str, int, int, int, int]:
    """解析原版 file:///path:startLine:startCol:endLine:endCol。"""
    raw = value.removeprefix("file:///")
    path, start_line, start_column, end_line, end_column = raw.rsplit(":", 4)
    return "/" + path.lstrip("/"), int(start_line), int(start_column), int(end_line), int(end_column)


# 解析查询输出行。
def _parse_row(line: str) -> list[str]:
    """读取原版竖线分隔行，并去掉首尾空列。"""
    return [item.strip() for item in line.split("|")[1:-1]]


# 定位 Schema callable。
def _find_callable(
    schema: dict[str, Any], name: str, start_line: int
) -> tuple[str, str, dict[str, Any]] | None:
    """按名称和起始行定位 callable，并兼容 ArkTS 顶层函数。"""
    for class_name, class_data in schema["classes"].items():
        for key, method in class_data["methods"].items():
            if method["start"] == start_line and key.split(":", 1)[1].split(":", 1)[0] == name:
                return class_name, key, method
    for key, function in schema.get("functions", {}).items():
        if function["start"] == start_line and key.split(":", 1)[1].split(":", 1)[0] == name:
            return "<module>", key, function
    return None


# 映射源码到 Schema 路径。
def _schema_path(schema_dir: Path, project_dir: Path, source_path: str) -> Path:
    """把调用图中的源码绝对路径转换为对应 schema 文件路径。"""
    relative = str(Path(source_path).resolve().relative_to(project_dir.resolve())).replace("\\", "/")
    return schema_dir / f"{_schema_name(relative)}.json"


# 将调用图写回 Schema。
def attach_calls(project_name: str) -> tuple[int, int]:
    """对应原版 extract_call_graph.py，把七列调用图写回 calls。"""
    project_dir = PROJECTS_ROOT / project_name
    schema_dir = ARKTS_DATA_ROOT / "schemas" / project_name
    call_graph = ARKTS_DATA_ROOT / "query_outputs" / project_name / f"{project_name}_call_graph.txt"
    if not schema_dir.is_dir():
        raise FileNotFoundError(f"Schema directory not found: {schema_dir}")
    if not call_graph.is_file():
        raise FileNotFoundError(f"Call graph output not found: {call_graph}")

    cache: dict[Path, dict[str, Any]] = {}
    attached = 0
    skipped = 0
    # 查询输出只负责传递调用边；这里负责把边解析成 Schema 中的三元组。
    for line in call_graph.read_text(encoding="utf-8").splitlines():
        values = _parse_row(line)
        if len(values) != 7:
            skipped += 1
            continue
        _, caller_name, caller_location, _, callee_name, callee_location, callee_signature = values
        caller_source, caller_line, _, _, _ = _split_location(caller_location)
        caller_schema_path = _schema_path(schema_dir, project_dir, caller_source)
        caller_schema = cache.setdefault(
            caller_schema_path, json.loads(caller_schema_path.read_text(encoding="utf-8"))
        )
        # caller 必须先在本项目 Schema 中定位，才能把 calls 写回正确方法。
        caller = _find_callable(caller_schema, caller_name, caller_line)
        if caller is None:
            skipped += 1
            continue

        callee_source, callee_line, _, _, _ = _split_location(callee_location)
        # SDK、标准库和第三方目标没有项目内源码，沿用原版 library 三元组。
        if callee_line == 0 or not Path(callee_source).is_file():
            target = ["library", callee_source.lstrip("/"), callee_signature]
        else:
            try:
                callee_schema_path = _schema_path(schema_dir, project_dir, callee_source)
                callee_schema = cache.setdefault(
                    callee_schema_path, json.loads(callee_schema_path.read_text(encoding="utf-8"))
                )
                callee = _find_callable(callee_schema, callee_name, callee_line)
            except (ValueError, FileNotFoundError):
                callee = None
                callee_schema_path = None
            if callee is None or callee_schema_path is None:
                target = ["library", callee_source.lstrip("/"), callee_signature]
            else:
                # 项目内目标保持 [schema名, class/<module>, callable键]。
                target = [callee_schema_path.stem, callee[0], callee[1]]
        # 同一调用目标可能由多个 ArkIR CFG 路径重复发现，写回前去重。
        if target not in caller[2]["calls"]:
            caller[2]["calls"].append(target)
            attached += 1

    # 统一写回所有被触及的 Schema 文件，未被调用图访问的文件不重复写入。
    for path, schema in cache.items():
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return attached, skipped


# 处理命令行并启动脚本。
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()
    attached, skipped = attach_calls(args.project_name)
    print(f"CALLS_ATTACHED={attached}")
    print(f"CALLS_SKIPPED={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
