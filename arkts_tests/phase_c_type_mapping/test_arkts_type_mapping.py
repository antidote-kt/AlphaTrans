import unittest
from arkts_src.phase_c_type_mapping.arkts_type_mapping_rules import candidate

class TypeMappingTest(unittest.TestCase):
    """验证 ArkTS 基础类型和泛型规则。"""
    def test_primitives(self):
        self.assertEqual(candidate("string"), "str")
        self.assertEqual(candidate("boolean"), "bool")
    def test_containers(self):
        self.assertEqual(candidate("Array<string>"), "list[str]")
        self.assertEqual(candidate("Map<string, number>"), "dict[str, float]")
    def test_union(self):
        self.assertEqual(candidate("string | null"), "str | None")
