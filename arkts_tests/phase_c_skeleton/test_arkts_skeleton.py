"""ArkTS 骨架生成关键规则测试。"""
import ast
import unittest

from arkts_src.phase_c_skeleton.arkts_create_skeleton import (
    _python_type,
    _render_class,
    _safe_name,
)
from arkts_src.phase_c_skeleton.arkts_get_dependencies import _topological_order


class ArkTSSkeletonTest(unittest.TestCase):
    """验证类型语法、ABC 接口和依赖顺序。"""

    def test_project_generic_is_python_syntax(self) -> None:
        self.assertEqual(_python_type("BaseMapper<T>", {"BaseMapper<T>": "BaseMapper<T>"}), "BaseMapper[T]")

    def test_interface_uses_abc(self) -> None:
        lines, _ = _render_class(
            "Logger",
            {"kind": "interface", "is_interface": True, "fields": {}, "methods": {}},
            {},
            {"Logger"},
        )
        source = "from abc import ABC\n" + "\n".join(lines)
        ast.parse(source)
        self.assertIn("class Logger(ABC):", source)

    def test_dependency_precedes_dependent(self) -> None:
        order = _topological_order({"Child": {"Parent"}, "Parent": set()})
        self.assertLess(order.index("Parent"), order.index("Child"))

    def test_invalid_identifier_is_sanitized(self) -> None:
        self.assertEqual(_safe_name("##storage"), "storage")


if __name__ == "__main__":
    unittest.main()
