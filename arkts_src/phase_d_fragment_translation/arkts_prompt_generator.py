"""构建 ArkTS fragment 到 Python 实现的组合式翻译 prompt。"""
from __future__ import annotations

import json
from pathlib import Path


class ArkTSPromptGenerator:
    """按当前 fragment、局部状态和调用依赖生成 prompt。"""

    def __init__(self, translation_dir: Path, fragment: dict, feedback: str = ""):
        self.translation_dir = translation_dir
        self.fragment = fragment
        self.feedback = feedback
        self.schema_path = translation_dir / f"{fragment['schema_name']}_python_partial.json"
        self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))

    def _fragment_data(self) -> dict:
        """返回字段、类方法或顶层函数对应的 schema 节点。"""
        fragment_type = self.fragment["fragment_type"]
        if fragment_type == "function":
            return self.schema["functions"][self.fragment["fragment_name"]]
        class_data = self.schema["classes"][self.fragment["class_name"]]
        collection = "fields" if fragment_type == "field" else "methods"
        return class_data[collection][self.fragment["fragment_name"]]

    @staticmethod
    def _translated_or_partial(item: dict) -> str:
        """优先返回已验证翻译，否则返回 C 阶段骨架。"""
        selected = item.get("translation") or item.get("partial_translation") or []
        return "\n".join(selected).rstrip()

    def _related_fields(self, fragment_data: dict) -> str:
        """只加入当前源码实际引用的本类字段，控制 prompt 长度。"""
        if self.fragment["class_name"] == "<module>":
            return ""
        body = "".join(fragment_data.get("body", []))
        class_data = self.schema["classes"][self.fragment["class_name"]]
        snippets: list[str] = []
        for field_name, field_data in class_data.get("fields", {}).items():
            # 只提供当前片段可能用到的字段，避免无关类上下文扩大 prompt。
            if field_name in body:
                snippets.append(self._translated_or_partial(field_data))
        return "\n".join(snippets)

    def _callee_context(self, fragment_data: dict) -> str:
        """加入已翻译被调用函数；未翻译时仅加入其 Python 签名。"""
        snippets: list[str] = []
        for call in fragment_data.get("calls", []):
            # 外部库调用和无法定位到 schema callable 的 ArkIR 调用不提供上下文。
            if not isinstance(call, list) or len(call) < 3 or call[0] == "library" or ":" not in call[2]:
                continue
            # 调用边中的 schema 名直接定位被调用 fragment 所在的 partial schema。
            path = self.translation_dir / f"{call[0]}_python_partial.json"
            if not path.exists():
                continue
            target_schema = json.loads(path.read_text(encoding="utf-8"))
            if call[1] in {"", "<module>"}:
                target = target_schema.get("functions", {}).get(call[2])
            else:
                target = target_schema.get("classes", {}).get(call[1], {}).get("methods", {}).get(call[2])
            if target:
                snippets.append(self._translated_or_partial(target))
        return "\n\n".join(dict.fromkeys(snippets))

    def _partial_signature(self, fragment_data: dict) -> str:
        """返回必须由 LLM 保持的 Python partial translation。"""
        return "\n".join(fragment_data.get("partial_translation", [])).rstrip()

    def generate(self) -> str:
        """生成包含源码、骨架、依赖和验证反馈的完整 prompt。"""
        # 源码决定实现语义，partial translation 约束 Python 签名。
        data = self._fragment_data()
        source = "".join(data.get("body", [])).rstrip()
        partial = self._partial_signature(data)
        fields = self._related_fields(data)
        callees = self._callee_context(data)
        class_declaration = ""
        if self.fragment["class_name"] != "<module>":
            # 类方法提供所属类声明，顶层函数不需要该上下文。
            class_declaration = self.schema["classes"][self.fragment["class_name"]].get(
                "python_class_declaration", ""
            ).rstrip()

        # 固定约束放在前面，防止模型输出整个文件或改变 C 阶段生成的签名。
        sections = [
            "Translate exactly one ArkTS fragment into Python 3.11.",
            "Preserve the provided Python function name, parameters, decorators and return annotation.",
            "Return only one ```python``` code block containing the field or callable implementation.",
            "Do not generate surrounding modules, unrelated classes, explanations, tests or Markdown outside the code block.",
            "For HarmonyOS APIs without a direct Python runtime equivalent, preserve the mapped type and implement the repository-level behavior as closely as possible.",
            f"Fragment type: {self.fragment['fragment_type']}",
            f"ArkTS source:\n```arkts\n{source}\n```",
            f"Required Python skeleton:\n```python\n{partial}\n```",
        ]
        if class_declaration:
            sections.append(f"Containing class:\n```python\n{class_declaration}\n```")
        if fields:
            sections.append(f"Referenced fields:\n```python\n{fields}\n```")
        if callees:
            sections.append(f"Available callees:\n```python\n{callees}\n```")
        if self.feedback:
            # 重试时追加上一轮错误，使模型针对验证失败原因修正。
            sections.append(
                "The previous translation failed validation. Correct this error:\n"
                f"```text\n{self.feedback}\n```"
            )
        return "\n\n".join(sections)
