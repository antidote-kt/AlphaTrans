#!/usr/bin/env python3
"""第二阶段共享分析层：合并 ArkTS AST 与 ArkAnalyzer ArkIR。"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_ROOT = REPO_ROOT / "arkts_projects" / "automated_reduced_projects"
ARKTS_DATA_ROOT = REPO_ROOT / "arkts_data"
ARKANALYZER = REPO_ROOT / "arkts_tools" / "arkanalyzer" / "node_modules" / ".bin" / "arkanalyzer"
OHOS_TYPESCRIPT = REPO_ROOT / "arkts_tools" / "arkanalyzer" / "node_modules" / "arkanalyzer" / "lib" / "node_modules" / "ohos-typescript"
AST_HELPER = Path(__file__).with_name("arkts_analyze_project.js")
SOURCE_SUFFIXES = {".ets", ".ts"}
IGNORED_PARTS = {".git", ".hvigor", "build", "node_modules", "oh_modules"}
CALL_EXPR_KINDS = {"InstanceCallExpr", "StaticCallExpr", "PtrCallExpr"}


# 收集当前阶段需要分析的源码文件。
def source_files(project_dir: Path) -> list[Path]:
    """仅分析项目源码，排除 SDK、依赖、构建目录和声明文件。"""
    result = []
    for path in project_dir.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if path.name.endswith(".d.ts") or any(part in IGNORED_PARTS for part in path.parts):
            continue
        result.append(path.resolve())
    return sorted(result)


# 辅助函数：处理 _run_ast。
def _run_ast(files: list[Path]) -> list[dict[str, Any]]:
    """用 AST 补充 ArkIR 不提供的装饰器、源码文本和精确位置。"""
    if not OHOS_TYPESCRIPT.is_dir():
        raise FileNotFoundError(f"ohos-typescript not found: {OHOS_TYPESCRIPT}")
    completed = subprocess.run(
        ["node", str(AST_HELPER), str(OHOS_TYPESCRIPT)],
        input=json.dumps({"files": [str(path) for path in files]}),
        text=True, capture_output=True, check=True,
    )
    return json.loads(completed.stdout)["files"]


# 把 ArkIR 类型转换为文本。
def type_text(value: Any) -> str:
    """把 ArkIR 类型节点转换成 ArkTS 类型文本。"""
    if not isinstance(value, dict):
        return "unknown"
    kind = str(value.get("_", "UnknownType"))
    primitive = {
        "AnyType": "any", "BigIntType": "bigint", "BooleanType": "boolean",
        "NeverType": "never", "NullType": "null", "NumberType": "number",
        "StringType": "string", "UndefinedType": "undefined",
        "UnknownType": "unknown", "VoidType": "void",
    }
    if kind in primitive:
        return primitive[kind]
    if kind in {"ClassType", "GenericType"}:
        signature = value.get("signature", {})
        name = signature.get("name") if isinstance(signature, dict) else None
        name = name or value.get("name") or "unknown"
        parameters = value.get("realGenericTypes") or value.get("types") or []
        return f"{name}<{','.join(type_text(item) for item in parameters)}>" if parameters else str(name)
    if kind in {"UnclearReferenceType", "AliasType"}:
        return str(value.get("name", "unknown"))
    if kind == "ArrayType":
        element = value.get("elementType") or value.get("baseType") or value.get("type")
        return type_text(element) + "[]" * int(value.get("dimensions", 1) or 1)
    if kind == "UnionType":
        return "|".join(type_text(item) for item in value.get("types", [])) or "unknown"
    if kind == "TupleType":
        return "[" + ",".join(type_text(item) for item in value.get("types", [])) + "]"
    if kind == "FunctionType":
        return "Function"
    return kind[:-4] if kind.endswith("Type") else kind


# 还原 ArkIR 项目相对路径。
def _relative_file(file_name: str, project_name: str) -> str:
    """ArkIR 来自临时副本，这里还原为项目内相对路径。"""
    normalized = file_name.replace("\\", "/")
    marker = f"/{project_name}/"
    return normalized.split(marker, 1)[1] if marker in normalized else normalized.lstrip("./")


# 规范化 ArkAnalyzer 方法名。
def _normalize_method_name(name: str) -> tuple[str, str]:
    """把 ArkAnalyzer 内部 getter/setter 名称恢复成 ArkTS 源码语义。"""
    if name == "constructor": return "constructor", "constructor"
    if name.startswith("Get-"): return name[4:], "getter"
    if name.startswith("Set-"): return name[4:], "setter"
    return name, "method"


# 递归查找 ArkIR 调用表达式。
def _find_call_exprs(value: Any) -> Iterable[dict[str, Any]]:
    """递归搜索 CFG 语句中内嵌的实例、静态和动态调用表达式。"""
    if isinstance(value, dict):
        if value.get("_") in CALL_EXPR_KINDS:
            yield value
        for nested in value.values():
            yield from _find_call_exprs(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _find_call_exprs(nested)


# 归一化 ArkIR 方法签名记录。
def _method_record(signature: dict[str, Any], project_name: str) -> dict[str, Any]:
    """把 ArkIR MethodSignature 归一化成查询层使用的方法记录。"""
    declaring = signature.get("declaringClass", {})
    file_name = declaring.get("declaringFile", {}).get("fileName", "")
    class_name = str(declaring.get("name", "%dflt"))
    name, kind = _normalize_method_name(str(signature.get("name", "<unknown>")))
    parameters = signature.get("parameters", [])
    parameter_types = [type_text(item.get("type", {})) for item in parameters if isinstance(item, dict)]
    return {
        "file": _relative_file(str(file_name), project_name),
        "class": "<module>" if class_name in {"%dflt", "@dummyClass"} else class_name,
        "name": name, "kind": kind, "parameter_types": parameter_types,
        "signature": f"{name}({', '.join(parameter_types)})",
        "return_type": type_text(signature.get("returnType", {})),
    }


# 临时运行 ArkAnalyzer 并提取调用边。
def _read_ir(project_dir: Path, project_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """在临时副本上运行 ArkAnalyzer，不在项目中保留 ArkIR。"""
    if not ARKANALYZER.is_file():
        raise FileNotFoundError(f"ArkAnalyzer executable not found: {ARKANALYZER}")
    with tempfile.TemporaryDirectory(prefix="alphatrans-arkts-phase-b-") as temp_dir:
        temp_root = Path(temp_dir)
        analysis_dir = temp_root / project_name
        # ArkAnalyzer 只看到源码副本，依赖和上一阶段产物不进入本次 IR。
        shutil.copytree(project_dir, analysis_dir, ignore=shutil.ignore_patterns(
            ".git", ".hvigor", "build", "node_modules", "oh_modules",
            "callgraph.txt", "trusted.txt", "untrusted.jsonl"))
        ir_dir = temp_root / "arkir"
        # ir 是本阶段的语义输入；与 cg 命令不同，这里需要保留方法签名、类型和 CFG。
        command = [str(ARKANALYZER), "ir", str(analysis_dir), "-f", "json", "-o", str(ir_dir)]
        if os.environ.get("OHOS_SDK_HOME"):
            command.extend(["--ohos-sdk-home", os.environ["OHOS_SDK_HOME"]])
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(ir_dir.rglob("*.json"))]
    methods, calls = [], []
    # ArkIR JSON 相当于本迁移中的语义查询源：在这里提取方法类型和调用边。
    # 逐个方法读取签名和 CFG，同时收集 caller-callee 关系。
    for document in documents:
        for ark_class in document.get("classes", []):
            for method in ark_class.get("methods", []):
                signature = method.get("signature", {})
                caller = _method_record(signature, project_name)
                ir_name = str(signature.get("name", ""))
                if not ir_name.startswith("%"):
                    methods.append(caller)
                body = method.get("body")
                if not isinstance(body, dict) or ir_name.startswith("%AM"):
                    # %AM 是 ArkAnalyzer 为闭包生成的内部方法，不对应独立源码声明。
                    continue
                # CFG block 内可能嵌套表达式，因此用递归查找三种 CallExpr。
                for block in body.get("cfg", {}).get("blocks", []):
                    for statement in block.get("stmts", []):
                        for expression in _find_call_exprs(statement):
                            callee_signature = expression.get("method")
                            if not isinstance(callee_signature, dict):
                                continue
                            callee = _method_record(callee_signature, project_name)
                            call_kind = {"StaticCallExpr": "S", "PtrCallExpr": "D", "InstanceCallExpr": "I"}.get(expression.get("_"), "D")
                            if callee["kind"] == "constructor" or str(callee_signature.get("name")) == "%instInit":
                                call_kind = "C"
                            calls.append({"caller": caller, "callee": callee, "kind": call_kind})
    return methods, calls


# 遍历文件中的 callable 声明。
def _method_candidates(file_data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for function in file_data["functions"]:
        function["className"] = "<module>"
        yield function
    for class_data in file_data["classes"]:
        yield from class_data["methods"]


# 用 ArkIR 结果补充 AST 信息。
def _enrich_with_ir(files: list[dict[str, Any]], methods: list[dict[str, Any]], project_dir: Path) -> None:
    """用 ArkIR 推断类型补充 AST 声明类型，同时保留二者供 schema 对照。"""
    index: dict[tuple[str, str, str, str, int], list[dict[str, Any]]] = {}
    for method in methods:
        key = (method["file"], method["class"], method["name"], method["kind"], len(method["parameter_types"]))
        index.setdefault(key, []).append(method)
    # AST 声明通过路径、owner、名称、kind 和参数数量匹配 ArkIR 方法。
    for file_data in files:
        relative = str(Path(file_data["path"]).relative_to(project_dir)).replace("\\", "/")
        file_data["relativePath"] = relative
        for method in _method_candidates(file_data):
            key = (relative, method["className"], method["name"], method["kind"], len(method["parameters"]))
            candidates = index.get(key, [])
            if not candidates and method["kind"] == "function":
                candidates = index.get((relative, "<module>", method["name"], "method", len(method["parameters"])), [])
            # 找不到精确 IR 方法时保留 AST 类型，保证不因解析不完整丢失声明。
            resolved = candidates[0] if candidates else None
            method["resolvedReturnType"] = resolved["return_type"] if resolved else method["returnType"]
            if resolved:
                for parameter, resolved_type in zip(method["parameters"], resolved["parameter_types"]):
                    parameter["resolvedType"] = resolved_type
            for parameter in method["parameters"]:
                parameter.setdefault("resolvedType", parameter["type"])


# 执行统一 AST、ArkIR 分析。
def analyze_project(project_name: str) -> dict[str, Any]:
    """统一入口：AST 负责语法/位置，ArkIR 负责类型和调用语义。"""
    project_dir = (PROJECTS_ROOT / project_name).resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"ArkTS project not found: {project_dir}")
    files = _run_ast(source_files(project_dir))
    methods, calls = _read_ir(project_dir, project_name)
    _enrich_with_ir(files, methods, project_dir)
    return {"project": project_name, "projectDir": str(project_dir), "files": files, "irMethods": methods, "calls": calls}


# 生成源码位置字符串。
def location(path: str | Path, item: dict[str, Any] | None = None) -> str:
    if item is None:
        return f"file:///{str(path).lstrip('/')}:0:0:0:0"
    return f"file:///{str(path).lstrip('/')}:{item['startLine']}:{item['startColumn']}:{item['endLine']}:{item['endColumn']}"


# 生成竖线分隔输出行。
def pipe_row(values: Iterable[Any]) -> str:
    """保持原版竖线分隔格式；ArkTS union type 中的竖线使用可逆转义。"""
    # 辅助函数：处理 clean。
    def clean(value: Any) -> str:
        if value is None:
            return "null"
        return str(value).replace("\n", " ").replace("|", "\\u007c")
    return "| " + " | ".join(clean(value) for value in values) + " |"
