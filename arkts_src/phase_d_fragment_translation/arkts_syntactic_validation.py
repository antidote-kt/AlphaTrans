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


def _normalize_callable_code(code: str, expected: str | None) -> str:
    """抽取目标 callable，并统一装饰器、def 与方法体的相对缩进。"""
    if not expected:
        return code
    lines = code.splitlines()
    def_index = None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith(f"def {expected}(") or stripped.startswith(
            f"async def {expected}("
        ):
            def_index = index
            break
    if def_index is None:
        return code

    # 丢弃模型附带的类声明或解释，只保留紧邻目标函数的装饰器和函数。
    start = def_index
    while start > 0 and lines[start - 1].lstrip().startswith("@"):
        start -= 1
    fragment = lines[start:]
    def_indent = len(lines[def_index]) - len(lines[def_index].lstrip())
    normalized: list[str] = []
    relative_def = def_index - start
    for index, line in enumerate(fragment):
        if index <= relative_def:
            normalized.append(line.lstrip())
            continue
        if def_indent and line.startswith(" " * def_indent):
            line = line[def_indent:]
        # 模型偶尔让方法体与 def 同级；至少恢复一级 Python 缩进。
        if line.strip() and not line[0].isspace():
            line = "    " + line
        normalized.append(line)
    return "\n".join(normalized)


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
            # 字段片段只接受第一条赋值语句，忽略模型附带的其他定义。
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

    # 从骨架取得目标函数名，防止模型生成语法正确但名称错误的函数。
    expected = _expected_name(partial_translation, fragment_type)
    code = _normalize_callable_code(code, expected)
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [], f"{exc.msg} at line {exc.lineno}"

    # 仅截取与骨架名称一致的函数或异步函数。
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
        # 类方法恢复一级缩进，并包装到临时类中进行语法检查。
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
