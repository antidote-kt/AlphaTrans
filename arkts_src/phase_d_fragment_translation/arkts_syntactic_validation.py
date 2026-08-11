"""提取并验证 LLM 生成的单个 Python fragment。"""
from __future__ import annotations

import ast
import re
import textwrap


def _code_block(generation: str) -> str:
    """读取第一个 Markdown Python 代码块；没有代码块时使用原始响应。"""
    match = re.search(r"```(?:python)?\s*(.*?)```", generation, re.DOTALL | re.IGNORECASE)
    return (match.group(1) if match else generation).strip()


def _expected_name(partial_translation: list[str], fragment_type: str) -> str | None:
    """从 C 阶段骨架中读取必须保持的 Python callable 名称。"""
    if fragment_type == "field":
        return None
    source = textwrap.dedent("\n".join(partial_translation))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = ast.parse(f"class Dummy:\n{textwrap.indent(source, '    ')}")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return None


def _node_source(source: str, node: ast.AST) -> str:
    """按 AST 行号截取节点及其装饰器，避免保留模型生成的无关代码。"""
    lines = source.splitlines()
    decorator_lines = [item.lineno for item in getattr(node, "decorator_list", [])]
    start = min(decorator_lines + [node.lineno]) - 1
    return "\n".join(lines[start : node.end_lineno])


def validate_generation(
    generation: str,
    fragment_type: str,
    partial_translation: list[str],
    in_class: bool,
) -> tuple[bool, list[str], str]:
    """验证字段或 callable，并返回可直接写入 partial schema 的代码行。"""
    code = textwrap.dedent(_code_block(generation))
    if not code:
        return False, [], "model did not generate code"

    if fragment_type == "field":
        try:
            tree = ast.parse(code)
            assignments = [
                node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
            ]
            if not assignments:
                return False, [], "model did not generate a field assignment"
            selected = _node_source(code, assignments[0])
            indented = textwrap.indent(selected, "    ") if in_class else selected
            ast.parse(f"class Dummy:\n{indented}" if in_class else indented)
            return True, indented.splitlines(), ""
        except SyntaxError as exc:
            return False, [], f"{exc.msg} at line {exc.lineno}"

    expected = _expected_name(partial_translation, fragment_type)
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [], f"{exc.msg} at line {exc.lineno}"

    callable_node = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and (expected is None or node.name == expected)
        ),
        None,
    )
    if callable_node is None:
        return False, [], f"model did not generate callable {expected or ''}".strip()

    selected = textwrap.dedent(_node_source(code, callable_node))
    if in_class:
        selected = textwrap.indent(selected, "    ")
        validation_source = f"class Dummy:\n{selected}"
    else:
        validation_source = selected
    try:
        ast.parse(validation_source)
        compile(validation_source, "<fragment>", "exec")
    except SyntaxError as exc:
        return False, [], f"{exc.msg} at line {exc.lineno}"
    return True, selected.splitlines(), ""
