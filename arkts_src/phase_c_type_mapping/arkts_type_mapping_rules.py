"""ArkTS 到 Python 的候选类型规则。"""
from __future__ import annotations

import re

# 这些是 ArkTS 与 Python typing 之间可以稳定转换的基础类型。
SIMPLE = {"string": "str", "boolean": "bool", "bigint": "int", "any": "Any", "unknown": "Any", "void": "None", "never": "NoReturn", "null": "None", "undefined": "None"}


def candidate(source: str) -> str:
    """返回确定性候选结果；无法判断时返回空字符串。

    规则只生成候选，不推断变量的运行时具体子类；项目自定义类型
    和 HarmonyOS SDK 类型交由 LLM 或后续适配表处理。
    """
    # 去除 schema 可能带入的空白，保证同一类型得到同一映射。
    text = source.strip()
    if text in SIMPLE:
        return SIMPLE[text]
    # ArkTS number 同时覆盖整数和浮点数，先以 float 作为保守候选。
    if text == "number":
        return "float"
    match = re.fullmatch(r"(?:Array|ReadonlyArray)<(.+)>", text)
    if match:
        return f"list[{candidate(match.group(1)) or 'Any'}]"
    if text.endswith("[]"):
        return f"list[{candidate(text[:-2]) or 'Any'}]"
    match = re.fullmatch(r"Map<(.+),\s*(.+)>", text)
    if match:
        return f"dict[{candidate(match.group(1)) or 'Any'}, {candidate(match.group(2)) or 'Any'}]"
    match = re.fullmatch(r"Set<(.+)>", text)
    if match:
        return f"set[{candidate(match.group(1)) or 'Any'}]"
    match = re.fullmatch(r"Promise<(.+)>", text)
    if match:
        return f"Awaitable[{candidate(match.group(1)) or 'Any'}]"
    # 联合类型逐项转换；无法识别的分支暂时使用 Any。
    if "|" in text:
        parts = [candidate(part.strip()) or "Any" for part in text.split("|")]
        return " | ".join(dict.fromkeys(parts))
    # 常见函数类型不需要查文档，直接转换为 Callable 占位表达式。
    if text.startswith("(") and "=>" in text:
        return "Callable[..., Any]"
    if text.startswith("@") or "." in text:
        return "Any"
    return ""
