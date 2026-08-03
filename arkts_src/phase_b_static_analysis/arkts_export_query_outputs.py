#!/usr/bin/env python3
"""用 ArkAnalyzer 生成 AlphaTrans 原版命名的 15 类查询输出。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

from arkts_analysis import ARKTS_DATA_ROOT, analyze_project, location, pipe_row

# 文件名严格保持原版 create_schema.py 所依赖的 15 类名称。
OUTPUT_NAMES = (
    "imports", "fields", "class_callables", "interfaces", "superclasses",
    "nested_classes", "parameters", "call_graph", "types",
    "constructor_call_graph", "all_constructors", "method_call_graph",
    "all_methods", "overridden_methods", "static_initializers",
)


def _rows() -> dict[str, list[str]]:
    return {name: [] for name in OUTPUT_NAMES}


def _class_location(path: str, class_data: dict[str, Any]) -> str:
    return location(path, class_data)


def _callable_rows(
    rows: dict[str, list[str]], path: str, class_data: dict[str, Any], method: dict[str, Any]
) -> None:
    """生成 callable、parameters、all_methods/constructors 对应查询行。"""
    target = "interfaces" if class_data["kind"] == "interface" else "class_callables"
    modifiers = method["modifiers"] or [None]
    annotations = method["decorators"] or [None]
    start = location(path, method)
    for modifier in modifiers:
        if target == "class_callables":
            rows[target].append(pipe_row([
                class_data["name"], _class_location(path, class_data), method["name"], modifier,
                method["returnType"], method["resolvedReturnType"], method["signature"],
                location(path, method) if annotations[0] else None, start, start,
            ]))
        else:
            rows[target].append(pipe_row([
                class_data["name"], _class_location(path, class_data), method["name"], modifier,
                method["returnType"], method["resolvedReturnType"], method["signature"], start, start,
            ]))

    for parameter in method["parameters"]:
        rows["parameters"].append(pipe_row([
            class_data["name"], method["name"], parameter["name"], location(path, parameter), start,
        ]))

    common = [
        class_data["name"], _class_location(path, class_data), method["name"],
        method["signature"], start, start,
    ]
    if method["kind"] == "constructor":
        rows["all_constructors"].append(pipe_row([
            class_data["name"], start, start, method["signature"], len(method["parameters"]),
            location(path, method), None, None,
        ]))
    else:
        rows["all_methods"].append(pipe_row(common))


def _declaration_index(analysis: dict[str, Any]) -> dict[tuple[str, str, str, str, int], tuple[str, dict[str, Any]]]:
    """为 ArkIR 方法建立源码索引，以便语义调用目标映射回源码位置。"""
    result = {}
    for file_data in analysis["files"]:
        relative = file_data["relativePath"]
        path = file_data["path"]
        for function in file_data["functions"]:
            result[(relative, "<module>", function["name"], "method", len(function["parameters"]))] = (path, function)
        for class_data in file_data["classes"]:
            for method in class_data["methods"]:
                result[(relative, class_data["name"], method["name"], method["kind"], len(method["parameters"]))] = (path, method)
    return result


def _lookup(
    index: dict[tuple[str, str, str, str, int], tuple[str, dict[str, Any]]], method: dict[str, Any]
) -> tuple[str | None, dict[str, Any] | None]:
    key = (method["file"], method["class"], method["name"], method["kind"], len(method["parameter_types"]))
    found = index.get(key)
    if found:
        return found
    # ArkIR 的接口/动态分派可能缺少精确参数类型，按名称和参数数量回退。
    for candidate, value in index.items():
        if candidate[:3] == key[:3] and candidate[4] == key[4]:
            return value
    return None, None


def build_rows(analysis: dict[str, Any]) -> dict[str, list[str]]:
    """对应原版 queries/*.ql，从统一分析结果构造 15 类表格。"""
    rows = _rows()
    type_pairs: set[tuple[str, str]] = set()
    class_by_name: dict[str, dict[str, Any]] = {}

    for file_data in analysis["files"]:
        path = file_data["path"]
        # 对应 get_imports.ql。
        for item in file_data["imports"]:
            rows["imports"].append(pipe_row([item["module"], location(path, item)]))
        for class_data in file_data["classes"]:
            class_by_name[class_data["name"]] = class_data
            # 无方法接口也要输出占位行，否则 schema 阶段无法发现它。
            if class_data["kind"] == "interface" and not class_data["methods"]:
                rows["interfaces"].append(pipe_row([
                    class_data["name"], _class_location(path, class_data), None, None,
                    None, None, None, None, None,
                ]))
            for parent in class_data["extends"]:
                rows["superclasses"].append(pipe_row([
                    class_data["name"], "true", parent, _class_location(path, class_data),
                ]))
            if class_data["nestedInside"]:
                rows["nested_classes"].append(pipe_row([
                    class_data["name"], _class_location(path, class_data), class_data["nestedInside"],
                ]))
            for field in class_data["fields"]:
                # 对应 get_fields_*.ql；多个 modifier 分别保留一行。
                for modifier in field["modifiers"] or [None]:
                    rows["fields"].append(pipe_row([
                        class_data["name"], field["name"], modifier, field["type"],
                        field["type"], location(path, field),
                    ]))
                type_pairs.add((field["type"], field["type"]))
            for method in class_data["methods"]:
                _callable_rows(rows, path, class_data, method)
                type_pairs.add((method["returnType"], method["resolvedReturnType"]))
                for parameter in method["parameters"]:
                    type_pairs.add((parameter["type"], parameter["resolvedType"]))
            for initializer in class_data["staticInitializers"]:
                rows["static_initializers"].append(pipe_row([
                    class_data["name"], location(path, initializer),
                ]))
        # 顶层函数没有 Java class，对应 schema 的 functions；兼容查询中用 <module> 占位。
        module_class = {
            "name": "<module>", "kind": "class", "startLine": 1, "startColumn": 1,
            "endLine": 1, "endColumn": 1,
        }
        for function in file_data["functions"]:
            _callable_rows(rows, path, module_class, function)
            type_pairs.add((function["returnType"], function["resolvedReturnType"]))

    declaration_index = _declaration_index(analysis)
    # 三类调用查询共享 ArkIR 中的同一批调用边，仅输出列结构不同。
    for call in analysis["calls"]:
        caller_path, caller_node = _lookup(declaration_index, call["caller"])
        if not caller_path or not caller_node:
            continue
        callee_path, callee_node = _lookup(declaration_index, call["callee"])
        caller_location = location(caller_path, caller_node)
        callee_location = location(callee_path, callee_node) if callee_path and callee_node else location(call["callee"]["class"])
        # ArkIR 暂不提供调用表达式行列，兼容字段使用所属 callable 的范围。
        call_location = caller_location
        rows["call_graph"].append(pipe_row([
            call_location, call["caller"]["name"], caller_location, call["caller"]["signature"],
            call["callee"]["name"], callee_location, call["callee"]["signature"],
        ]))
        if call["kind"] == "C":
            rows["constructor_call_graph"].append(pipe_row([
                f"new {call['callee']['class']}(...)", call["callee"]["signature"],
                call_location, len(call["callee"]["parameter_types"]), call["kind"],
            ]))
        else:
            rows["method_call_graph"].append(pipe_row([
                call_location, call["callee"]["name"], len(call["callee"]["parameter_types"]),
                call_location, call["callee"]["signature"], call["caller"]["name"],
                caller_location, call["caller"]["class"], call["callee"]["name"],
                callee_location, call["callee"]["class"],
            ]))

    # ArkTS override 修饰符只说明意图；按继承类中的同名同参数方法建立对应关系。
    for file_data in analysis["files"]:
        path = file_data["path"]
        for class_data in file_data["classes"]:
            for method in class_data["methods"]:
                if "override" not in method["modifiers"]:
                    continue
                for parent_name in class_data["extends"] + class_data["implements"]:
                    parent = class_by_name.get(parent_name.split("<", 1)[0])
                    if not parent:
                        continue
                    for parent_method in parent["methods"]:
                        if parent_method["name"] == method["name"] and len(parent_method["parameters"]) == len(method["parameters"]):
                            parent_file = next(
                                f["path"] for f in analysis["files"] if parent in f["classes"]
                            )
                            rows["overridden_methods"].append(pipe_row([
                                method["name"], location(path, method), parent_method["name"],
                                location(parent_file, parent_method), parent["name"],
                            ]))

    rows["types"] = [pipe_row(pair) for pair in sorted(type_pairs)]
    return {name: sorted(set(values)) for name, values in rows.items()}


def export_query_outputs_from_analysis(analysis: dict[str, Any]) -> tuple[Path, dict[str, int]]:
    """使用已经完成的统一分析结果写出全部查询文件。"""
    rows = build_rows(analysis)
    project_name = analysis["project"]
    output_dir = ARKTS_DATA_ROOT / "query_outputs" / project_name
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_NAMES:
        content = "\n".join(rows[name])
        (output_dir / f"{project_name}_{name}.txt").write_text(
            content + ("\n" if content else ""), encoding="utf-8"
        )
    return output_dir, {name: len(rows[name]) for name in OUTPUT_NAMES}


def export_query_outputs(project_name: str) -> tuple[Path, dict[str, int]]:
    """独立调用时分析一次；统一入口直接调用 *_from_analysis。"""
    return export_query_outputs_from_analysis(analyze_project(project_name))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()
    output, counts = export_query_outputs(args.project_name)
    print(f"QUERY_OUTPUTS={output}")
    print(" ".join(f"{name}={count}" for name, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
