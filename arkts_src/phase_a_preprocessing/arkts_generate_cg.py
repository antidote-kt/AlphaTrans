#!/usr/bin/env python3
"""从 ArkAnalyzer ArkIR 生成与 AlphaTrans 格式兼容的 callgraph.txt。

逐方法体记录实际调用点，对应原版 JavaCG 的作用；第一阶段不执行 CHA/RTA。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
ARKTS_PROJECTS = REPO_ROOT / "arkts_projects" / "automated_reduced_projects"
DEFAULT_ARKANALYZER = REPO_ROOT / "arkts_tools" / "arkanalyzer" / "node_modules" / ".bin" / "arkanalyzer"
# ArkIR 中三类可能产生方法调用边的表达式。
CALL_EXPR_KINDS = {"InstanceCallExpr", "StaticCallExpr", "PtrCallExpr"}
INTERFACE_CATEGORY = 2


# 把文件路径转换为模块 owner。
def _module_owner(file_name: str) -> str:
    """将源码路径转换为调用图 owner；模块顶层函数以源文件模块为 owner。"""
    value = re.sub(r"\.(ets|ts|js|d\.ts)$", "", file_name.strip())
    value = value.replace("/src/main/ets/", "/")
    value = value.replace("/src/test/", "/test/")
    value = value.replace("/src/ohosTest/ets/", "/ohosTest/")
    value = re.sub(r"[^A-Za-z0-9_$./-]+", "_", value)
    return value.replace("/", ".").strip(".") or "module"


# 辅助函数：处理 _declaring_class。
def _declaring_class(method: dict[str, Any]) -> dict[str, Any]:
    value = method.get("declaringClass", {})
    return value if isinstance(value, dict) else {}


# 计算方法的调用图 owner。
def _method_owner(method: dict[str, Any]) -> str:
    declaring_class = _declaring_class(method)
    file_name = str(declaring_class.get("declaringFile", {}).get("fileName", "unknown"))
    module_owner = _module_owner(file_name)
    class_name = str(declaring_class.get("name", "%dflt"))
    if class_name in {"%dflt", "@dummyClass"}:
        return module_owner
    if class_name == module_owner.rsplit(".", 1)[-1]:
        return module_owner
    return f"{module_owner}${class_name}"


# 辅助函数：处理 _type_text。
def _type_text(value: Any) -> str:
    """将 ArkIR 类型转换为方法签名中的紧凑文本。"""
    if not isinstance(value, dict):
        return "unknown"
    kind = str(value.get("_", "UnknownType"))
    primitive = {
        "AnyType": "any", "BooleanType": "boolean", "NeverType": "never",
        "NullType": "null", "NumberType": "number", "StringType": "string",
        "UndefinedType": "undefined", "UnknownType": "unknown", "VoidType": "void",
    }
    if kind in primitive:
        return primitive[kind]
    if kind in {"ClassType", "GenericType"}:
        signature = value.get("signature", {})
        name = signature.get("name") if isinstance(signature, dict) else None
        name = name or value.get("name") or "unknown"
        parameters = value.get("realGenericTypes") or value.get("types") or []
        if parameters:
            return f"{name}<{','.join(_type_text(item) for item in parameters)}>"
        return str(name)
    if kind in {"UnclearReferenceType", "AliasType"}:
        return str(value.get("name", "unknown"))
    if kind == "ArrayType":
        element = value.get("elementType") or value.get("baseType") or value.get("type")
        dimensions = int(value.get("dimensions", 1) or 1)
        return _type_text(element) + "[]" * dimensions
    if kind == "UnionType":
        values = value.get("types") or value.get("currType") or []
        return "|".join(_type_text(item) for item in values) or "unknown"
    if kind == "FunctionType":
        return "Function"
    return kind[:-4] if kind.endswith("Type") else kind or "unknown"


# 生成方法调用签名。
def method_signature(method: dict[str, Any]) -> str:
    owner = _method_owner(method)
    name = str(method.get("name", "<unknown>"))
    if name == "constructor":
        name = "<init>"
    parameters = method.get("parameters", [])
    parameter_text = ",".join(
        _type_text(item.get("type", {})) for item in parameters if isinstance(item, dict)
    )
    return re.sub(r"\s+", "", f"{owner}:{name}({parameter_text})")


# 辅助函数：处理 _method_key。
def _method_key(method: dict[str, Any]) -> tuple[str, str]:
    declaring_class = _declaring_class(method)
    return (
        str(declaring_class.get("declaringFile", {}).get("fileName", "")),
        str(declaring_class.get("name", "")),
    )


# 辅助函数：处理 _interface_keys。
def _interface_keys(documents: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    interfaces: set[tuple[str, str]] = set()
    for document in documents:
        for ark_class in document.get("classes", []):
            if ark_class.get("category") != INTERFACE_CATEGORY:
                continue
            signature = ark_class.get("signature", {})
            interfaces.add((
                str(signature.get("declaringFile", {}).get("fileName", "")),
                str(signature.get("name", "")),
            ))
    return interfaces


# 递归查找 ArkIR 调用表达式。
def _find_call_exprs(value: Any) -> Iterable[dict[str, Any]]:
    """递归遍历 ArkIR 语句，找出其中所有调用表达式。"""
    if isinstance(value, dict):
        if value.get("_") in CALL_EXPR_KINDS:
            yield value
        for nested in value.values():
            yield from _find_call_exprs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _find_call_exprs(nested)


# 判断 ArkIR 调用类型标记。
def _call_type(expression: dict[str, Any], interfaces: set[tuple[str, str]]) -> str:
    """将 ArkIR 调用表达式映射为 M/I/O/S/D 调用类型。"""
    method = expression.get("method", {})
    if str(method.get("name", "")) in {"constructor", "%instInit"}:
        return "O"
    kind = expression.get("_")
    if kind == "StaticCallExpr":
        return "S"
    if kind == "PtrCallExpr":
        return "D"
    if _method_key(method) in interfaces:
        return "I"
    return "M"


# 把 ArkIR 文档转换为调用图行。
def convert_arkir_documents(documents: list[dict[str, Any]]) -> list[str]:
    """将 ArkIR 转换为 AlphaTrans/JavaCG 兼容的 M: 方法边和 C: owner 边。"""
    interfaces = _interface_keys(documents)
    method_lines: list[str] = []
    class_lines: set[str] = set()
    for document in documents:
        for ark_class in document.get("classes", []):
            for caller_method in ark_class.get("methods", []):
                body = caller_method.get("body")
                if not isinstance(body, dict):
                    continue
                caller = method_signature(caller_method.get("signature", {}))
                for block in body.get("cfg", {}).get("blocks", []):
                    for statement in block.get("stmts", []):
                        for expression in _find_call_exprs(statement):
                            callee_method = expression.get("method")
                            if not isinstance(callee_method, dict):
                                continue
                            callee = method_signature(callee_method)
                            method_lines.append(f"M:{caller} ({_call_type(expression, interfaces)}){callee}")
                            caller_owner = caller.split(":", 1)[0]
                            callee_owner = callee.split(":", 1)[0]
                            if caller_owner != callee_owner:
                                class_lines.add(f"C:{caller_owner} {callee_owner}")
    return sorted(class_lines) + sorted(method_lines)


# 执行 ArkAnalyzer ArkIR 导出。
def run_arkanalyzer_ir(project_dir: Path, output_dir: Path, executable: Path, sdk_home: str | None) -> None:
    """调用 ArkAnalyzer CLI，将 ArkTS 源码导出为临时 ArkIR JSON。"""
    if not executable.is_file():
        raise FileNotFoundError(
            f"ArkAnalyzer executable not found: {executable}. Install it under arkts_tools/arkanalyzer first."
        )
    command = [str(executable), "ir", str(project_dir), "-f", "json", "-o", str(output_dir)]
    if sdk_home:
        command.extend(["--ohos-sdk-home", sdk_home])
    subprocess.run(command, check=True)


# 生成第一阶段兼容格式调用图。
def generate_callgraph(
    project_name: str,
    arkanalyzer: Path = DEFAULT_ARKANALYZER,
    sdk_home: str | None = None,
) -> Path:
    # 只对第一阶段已经复制并准备裁剪的 reduced project 生成调用图。
    project_dir = ARKTS_PROJECTS / project_name
    if not project_dir.is_dir():
        raise FileNotFoundError(f"ArkTS project not found: {project_dir}")
    # 临时副本排除依赖、构建缓存和已有产物，避免 ArkAnalyzer 重复扫描。
    with tempfile.TemporaryDirectory(prefix="alphatrans-arkts-ir-") as temp_dir:
        temp_root = Path(temp_dir)
        analysis_dir = temp_root / project_name
        # 临时副本避免把依赖目录、构建缓存和旧产物送入 ArkAnalyzer。
        shutil.copytree(
            project_dir,
            analysis_dir,
            ignore=shutil.ignore_patterns(
                ".git", ".hvigor", "build", "node_modules", "oh_modules",
                "callgraph.txt", "trusted.txt", "untrusted.jsonl",
            ),
        )
        # ArkAnalyzer 输出的是按源码文件组织的 ArkIR JSON；这里只读，不修改源码。
        ir_dir = temp_root / "arkir"
        run_arkanalyzer_ir(analysis_dir, ir_dir, arkanalyzer, sdk_home)
        # 读取全部 ArkIR 文档后，统一转换成 M:/C: 兼容边。
        documents = []
        for json_file in sorted(ir_dir.rglob("*.json")):
            with json_file.open(encoding="utf-8") as handle:
                documents.append(json.load(handle))
        lines = convert_arkir_documents(documents)
    # 临时目录在离开 with 后删除，只有兼容格式的 callgraph.txt 被保留。
    output = project_dir / "callgraph.txt"
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    method_edges = sum(line.startswith("M:") for line in lines)
    print(f"Call graph saved to {output} ({len(documents)} ArkIR files, {method_edges} direct call sites).")
    return output


# 处理命令行并启动脚本。
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    parser.add_argument("--arkanalyzer", type=Path, default=DEFAULT_ARKANALYZER)
    parser.add_argument("--ohos-sdk-home", default=os.environ.get("OHOS_SDK_HOME"))
    args = parser.parse_args()
    try:
        generate_callgraph(args.project_name, args.arkanalyzer, args.ohos_sdk_home)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
