from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from arkts_analysis import AST_HELPER, OHOS_TYPESCRIPT, pipe_row, type_text
from arkts_export_query_outputs import OUTPUT_NAMES


FIXTURE = Path(__file__).with_name("fixtures") / "Sample.ets"


class AstAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        completed = subprocess.run(
            ["node", str(AST_HELPER), str(OHOS_TYPESCRIPT)],
            input=json.dumps({"files": [str(FIXTURE.resolve())]}),
            text=True,
            capture_output=True,
            check=True,
        )
        cls.file = json.loads(completed.stdout)["files"][0]

    def test_arkts_declarations(self) -> None:
        self.assertEqual([item["kind"] for item in self.file["classes"]], ["interface", "class"])
        self.assertEqual(self.file["classes"][1]["typeParameters"], ["T"])
        self.assertEqual([item["kind"] for item in self.file["classes"][1]["methods"]], ["constructor", "getter"])
        self.assertEqual(self.file["functions"][0]["name"], "make")

    def test_source_locations_are_one_based(self) -> None:
        imported = self.file["imports"][0]
        self.assertEqual((imported["startLine"], imported["startColumn"]), (1, 1))


class CompatibilityTest(unittest.TestCase):
    def test_original_query_output_count(self) -> None:
        self.assertEqual(len(OUTPUT_NAMES), 15)

    def test_union_type_does_not_break_pipe_columns(self) -> None:
        row = pipe_row(["caller", "string|number", "callee"])
        self.assertEqual(len(row.split("|")[1:-1]), 3)
        self.assertIn("\\u007c", row)

    def test_arkir_union_type_mapping(self) -> None:
        value = {"_": "UnionType", "types": [{"_": "StringType"}, {"_": "NumberType"}]}
        self.assertEqual(type_text(value), "string|number")


if __name__ == "__main__":
    unittest.main()
