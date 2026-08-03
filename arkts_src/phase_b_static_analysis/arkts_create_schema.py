#!/usr/bin/env python3
"""从 ArkTS 分析结果构建尽量兼容 AlphaTrans 的逐文件 schema。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arkts_analysis import ARKTS_DATA_ROOT, analyze_project


def _body(path: str, start: int, end: int) -> list[str]:
    """按 AST 的一基行号截取源码，保持原 schema 的 body=list[str]。"""
    lines = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    return lines[start - 1:end]


def _method_schema(path: str, item: dict[str, Any]) -> dict[str, Any]:
    """保留原 callable 字段，并追加 ArkTS 参数与方法种类信息。"""
    return {
        "start": item["startLine"],
        "end": item["endLine"],
        "body": _body(path, item["startLine"], item["endLine"]),
        "is_constructor": item["kind"] == "constructor",
        "annotations": item["decorators"],
        "modifiers": item["modifiers"],
        "return_types": [[item["returnType"], item["resolvedReturnType"]]],
        "signature": item["signature"],
        "parameters": [parameter["name"] for parameter in item["parameters"]],
        "calls": [],
        # ArkTS 增补：区分顶层函数、普通方法、getter、setter、constructor。
        "kind": item["kind"],
        "type_parameters": item["typeParameters"],
        "parameter_details": [
            {
                "name": parameter["name"],
                "type": parameter["type"],
                "resolved_type": parameter["resolvedType"],
                "optional": parameter["optional"],
                "rest": parameter["rest"],
                "default": parameter["default"],
            }
            for parameter in item["parameters"]
        ],
    }


def _method_map(path: str, methods: list[dict[str, Any]]) -> dict[str, Any]:
    """沿用原版“起始行-结束行:方法名”作为 callable 主键。"""
    result = {}
    for item in methods:
        key = f"{item['startLine']}-{item['endLine']}:{item['name']}"
        if key in result:
            # getter/setter 或重载位置键冲突时，用 kind 防止覆盖。
            key = f"{key}:{item['kind']}"
        result[key] = _method_schema(path, item)
    return result


def _field_schema(path: str, field: dict[str, Any]) -> dict[str, Any]:
    """保留原字段位置、正文、修饰符和类型，并记录 ArkTS 初始化语义。"""
    return {
        "start": field["startLine"],
        "end": field["endLine"],
        "body": _body(path, field["startLine"], field["endLine"]),
        "modifiers": field["modifiers"],
        "types": [[field["type"], field["type"]]],
        "kind": field["kind"],
        "optional": field["optional"],
        "definite": field["definite"],
        "initializer": field["initializer"],
        "annotations": field["decorators"],
    }


def _schema_name(relative_path: str) -> str:
    """沿用原版规则，把项目相对路径转换为点分 schema 文件名。"""
    value = relative_path.replace("\\", "/").replace("/", ".")
    if value.endswith(".ets"):
        value = value[:-4]
    elif value.endswith(".ts"):
        value = value[:-3]
    return value


def create_schemas(project_name: str) -> tuple[Path, dict[str, int]]:
    """对应原版 create_schema.py，按 ArkTS 源码文件生成 JSON。"""
    analysis = analyze_project(project_name)
    output_dir = ARKTS_DATA_ROOT / "schemas" / project_name
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {"files": 0, "classes": 0, "functions": 0, "methods": 0, "fields": 0}

    for file_data in analysis["files"]:
        path = file_data["path"]
        schema: dict[str, Any] = {
            "path": path,
            "imports": {},
            "classes": {},
            # ArkTS 允许类外声明，以下字段是相对 Java schema 的必要增补。
            "exports": file_data["exports"],
            "functions": _method_map(path, file_data["functions"]),
            "variables": {},
            "type_aliases": {},
        }
        for item in file_data["imports"]:
            key = f"{item['startLine']}-{item['endLine']}:{item['module']}"
            schema["imports"][key] = {
                "start": item["startLine"], "end": item["endLine"],
                "body": _body(path, item["startLine"], item["endLine"]),
                "module": item["module"], "side_effect_only": item["sideEffectOnly"],
            }
        for item in file_data["variables"]:
            schema["variables"][item["name"]] = {
                "start": item["startLine"], "end": item["endLine"],
                "body": _body(path, item["startLine"], item["endLine"]),
                "kind": item["kind"], "type": item["type"],
                "initializer": item["initializer"], "modifiers": item["modifiers"],
            }
        for item in file_data["typeAliases"]:
            schema["type_aliases"][item["name"]] = {
                "start": item["startLine"], "end": item["endLine"],
                "body": _body(path, item["startLine"], item["endLine"]),
                "type": item["type"], "modifiers": item["modifiers"],
                "type_parameters": item["typeParameters"],
            }
        for item in file_data["classes"]:
            # 原 class 字段全部保留；ArkTS 新字段集中追加在末尾。
            class_schema = {
                "start": item["startLine"], "end": item["endLine"],
                "is_abstract": item["isAbstract"],
                "is_interface": item["kind"] == "interface",
                "nested_inside": [item["nestedInside"]] if item["nestedInside"] else [],
                "nests": [], "implements": item["implements"], "extends": item["extends"],
                "methods": _method_map(path, item["methods"]),
                "fields": {field["name"]: _field_schema(path, field) for field in item["fields"]},
                "static_initializers": {
                    f"{value['startLine']}-{value['endLine']}": {
                        "start": value["startLine"], "end": value["endLine"],
                        "body": _body(path, value["startLine"], value["endLine"]),
                    }
                    for value in item["staticInitializers"]
                },
                # ArkTS 增补：class/interface/struct/enum 不能只由 is_interface 表达。
                "kind": item["kind"],
                "type_parameters": item["typeParameters"],
                "annotations": item["decorators"],
                "modifiers": item["modifiers"],
            }
            schema["classes"][item["name"]] = class_schema
            counts["methods"] += len(item["methods"])
            counts["fields"] += len(item["fields"])

        output = output_dir / f"{_schema_name(file_data['relativePath'])}.json"
        output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts["files"] += 1
        counts["classes"] += len(file_data["classes"])
        counts["functions"] += len(file_data["functions"])
    return output_dir, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()
    output, counts = create_schemas(args.project_name)
    print(f"SCHEMAS={output}")
    print(" ".join(f"{name}={value}" for name, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
