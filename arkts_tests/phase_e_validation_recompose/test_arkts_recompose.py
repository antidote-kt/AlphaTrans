"""测试 partial schema 重组时的 fragment 选择。"""
import unittest

from arkts_src.phase_e_validation_recompose.arkts_recompose import (
    _render_schema,
    _selected_lines,
)


class ArkTSRecomposeTest(unittest.TestCase):
    """验证已通过翻译和失败翻译的重组选择。"""

    def test_use_parseable_translation(self) -> None:
        item = {
            "translation": ["    def f(self):", "        return 1"],
            "partial_translation": ["    def f(self):", "        pass"],
            "syntactic_validation": "parseable",
        }
        self.assertIn("return 1", "\n".join(_selected_lines(item)))

    def test_fallback_to_partial(self) -> None:
        item = {
            "translation": [],
            "partial_translation": ["    def f(self):", "        pass"],
            "syntactic_validation": "pending",
        }
        self.assertIn("pass", "\n".join(_selected_lines(item)))

    def test_add_pytest_alias_for_hypium_entry(self) -> None:
        """Hypium 外层函数重组后应提供 pytest 可收集的 test_ 别名。"""
        schema = {
            "python_imports": [],
            "classes": {},
            "functions": {
                "1-4:abilityTest": {
                    "partial_translation": ["def abilityTest():", "    pass"],
                    "syntactic_validation": "pending",
                }
            },
        }
        rendered = _render_schema(schema, is_test_schema=True)
        self.assertIn("test_abilityTest = abilityTest", rendered)


if __name__ == "__main__":
    unittest.main()
