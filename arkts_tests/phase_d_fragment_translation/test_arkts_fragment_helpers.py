"""仅测试不访问网络的 fragment 顺序和语法提取逻辑。"""
import unittest

from arkts_src.phase_d_fragment_translation.arkts_syntactic_validation import (
    validate_generation,
)


class ArkTSFragmentHelperTest(unittest.TestCase):
    """验证模型响应抽取和 fragment Python 语法。"""

    def test_extract_class_method(self) -> None:
        generation = """```python
def query(self, sql: str) -> int:
    return 1
```"""
        ok, lines, feedback = validate_generation(
            generation,
            "method",
            ["    def query(self, sql: str) -> int:\n", "        pass\n"],
            True,
        )
        self.assertTrue(ok, feedback)
        self.assertIn("    def query", "\n".join(lines))

    def test_reject_wrong_callable_name(self) -> None:
        ok, _, _ = validate_generation(
            "```python\ndef other() -> None:\n    pass\n```",
            "function",
            ["def expected() -> None:\n", "    pass\n"],
            False,
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
