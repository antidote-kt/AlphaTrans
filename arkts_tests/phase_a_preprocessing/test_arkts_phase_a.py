from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from arkts_src.phase_a_preprocessing.arkts_generate_cg import convert_arkir_documents
from arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs import (
    extract_imports,
    is_trusted,
    reduce_project,
)


class CallGraphConversionTests(unittest.TestCase):
    def test_maps_arkir_call_sites_to_original_text_shape(self):
        def method(file_name, owner, name, parameters=None):
            return {
                "declaringClass": {
                    "name": owner,
                    "declaringFile": {"projectName": "Demo", "fileName": file_name},
                },
                "name": name,
                "parameters": parameters or [],
                "returnType": {"_": "VoidType"},
            }

        caller = method("entry/src/main/ets/Main.ets", "Main", "run")
        expressions = [
            {"_": "InstanceCallExpr", "method": method("lib/src/main/ets/Service.ets", "Service", "work", [{"type": {"_": "StringType"}}]), "args": []},
            {"_": "StaticCallExpr", "method": method("lib/src/main/ets/Factory.ets", "Factory", "create"), "args": []},
            {"_": "InstanceCallExpr", "method": method("lib/src/main/ets/Factory.ets", "Factory", "constructor"), "args": []},
            {"_": "StaticCallExpr", "method": method("lib/src/main/ets/utils.ets", "%dflt", "helper"), "args": []},
            {"_": "PtrCallExpr", "method": method("lib/src/main/ets/utils.ets", "%dflt", "%AM0"), "args": []},
        ]
        documents = [{
            "classes": [{
                "signature": caller["declaringClass"],
                "category": 0,
                "methods": [{
                    "signature": caller,
                    "body": {"cfg": {"blocks": [{"stmts": [{"_": "CallStmt", "expr": expr} for expr in expressions]}]}},
                }],
            }],
        }]
        lines = convert_arkir_documents(documents)
        text = "\n".join(lines)
        self.assertIn("(M)lib.Service:work(string)", text)
        self.assertIn("(S)lib.Factory:create()", text)
        self.assertIn("(O)lib.Factory:<init>()", text)
        self.assertIn("(S)lib.utils:helper()", text)
        self.assertIn("(D)lib.utils:%AM0()", text)
        self.assertTrue(all(line.startswith(("M:", "C:")) for line in lines))


class DependencyReductionTests(unittest.TestCase):
    def test_extracts_multiline_import(self):
        imports = extract_imports("import {\n  A, B\n} from 'pkg'\n")
        self.assertEqual("pkg", imports[0]["module"])

    def test_distinguishes_side_effect_and_bound_imports(self):
        text = 'import "reflect-metadata";\nimport { A } from "pkg";\n'
        imports = extract_imports(text)
        self.assertEqual(["reflect-metadata", "pkg"], [item["module"] for item in imports])
        self.assertEqual("", imports[0]["body"])
        self.assertEqual("{ A }", imports[1]["body"])

    def test_platform_and_project_modules_are_trusted(self):
        for module in {
            "@kit.ArkTS",
            "@kit.LocalizationKit",
            "@kit.CoreFileKit",
            "@kit.NetworkKit",
            "@kit.PerformanceAnalysisKit",
            "@ohos/hypium",
            "@kit.ArkData",
        }:
            self.assertTrue(is_trusted(module, {"rdbplus"}), module)
        self.assertTrue(is_trusted("rdbplus", {"rdbplus"}))
        self.assertTrue(is_trusted("rdbplus/core", {"rdbplus"}))
        self.assertTrue(is_trusted("../Employee", {"rdbplus"}))
        self.assertFalse(is_trusted("third-party", {"rdbplus"}))
        self.assertFalse(is_trusted("@ohos/hamock", {"rdbplus"}))
        self.assertFalse(is_trusted("@ohos/axios", {"rdbplus"}))
        self.assertFalse(is_trusted("@kit.ThirdParty", {"rdbplus"}))

    def test_discovers_only_modules_present_in_sdk(self):
        from arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs import discover_sdk_modules
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kit = root / "ets" / "kits" / "@kit.AbilityKit.d.ts"
            api = root / "ets" / "api" / "@ohos.promptAction.d.ts"
            kit.parent.mkdir(parents=True)
            api.parent.mkdir(parents=True)
            kit.write_text("")
            api.write_text("")
            modules = discover_sdk_modules([root])
        self.assertEqual({"@kit.AbilityKit", "@ohos.promptAction"}, modules)
        self.assertNotIn("@ohos/axios", modules)

    def test_removes_class_extending_third_party_and_its_callers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original" / "Demo"
            reduced = root / "reduced" / "Demo"
            original.mkdir(parents=True)
            reduced.mkdir(parents=True)
            (reduced / "callgraph.txt").write_text(
                "M:Main:use() (M)Main$Local:work()\n", encoding="utf-8"
            )
            (reduced / "oh-package.json5").write_text("{name: \"demo\"}")
            source = reduced / "Main.ets"
            source.write_text(
                "import { ExternalBase } from \"third-party\"\n"
                "export class Local extends ExternalBase {\n"
                "  work(): void {}\n"
                "}\n"
                "export function use(): void { new Local().work() }\n"
                "export function keep(): number { return 1 }\n",
                encoding="utf-8",
            )
            with patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.ORIGINAL_PROJECTS",
                root / "original",
            ), patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.REDUCED_PROJECTS",
                root / "reduced",
            ), patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.discover_sdk_modules",
                return_value=set(),
            ):
                trusted, untrusted, removed = reduce_project("Demo")
            result = source.read_text(encoding="utf-8")
            self.assertEqual((0, 1, 3), (trusted, untrusted, removed))
            self.assertRegex(result, r"class Local\s*\{\s*\}")
            self.assertNotIn("function use", result)
            self.assertIn("function keep", result)

    def test_propagates_third_party_dependency_to_callers_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original" / "Demo"
            reduced = root / "reduced" / "Demo"
            original.mkdir(parents=True)
            reduced.mkdir(parents=True)
            (reduced / "callgraph.txt").write_text(
                "M:Main:caller() (S)Main:bad()\n", encoding="utf-8"
            )
            manifest = reduced / "oh-package.json5"
            manifest.write_text(
                "{\n  name: \"demo\",\n  dependencies: {\n"
                "    \"third-party\": \"1.0.0\",\n  },\n}\n",
                encoding="utf-8",
            )
            source = reduced / "Main.ets"
            source.write_text(
                "import { Client } from \"third-party\"\n"
                "export function bad(): void { Client.run() }\n"
                "export function caller(): void { bad() }\n"
                "export function keep(): number { return 1 }\n",
                encoding="utf-8",
            )
            with patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.ORIGINAL_PROJECTS",
                root / "original",
            ), patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.REDUCED_PROJECTS",
                root / "reduced",
            ), patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.discover_sdk_modules",
                return_value=set(),
            ):
                trusted, untrusted, removed = reduce_project("Demo")

            result = source.read_text(encoding="utf-8")
            self.assertEqual((0, 2, 4), (trusted, untrusted, removed))
            self.assertNotIn("Client", result)
            self.assertNotIn("function bad", result)
            self.assertNotIn("function caller", result)
            self.assertIn("function keep", result)
            self.assertNotIn("third-party", manifest.read_text(encoding="utf-8"))

    def test_writes_original_outputs_and_only_removes_unused_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original" / "Demo"
            reduced = root / "reduced" / "Demo"
            original.mkdir(parents=True)
            reduced.mkdir(parents=True)
            (reduced / "callgraph.txt").write_text("M:A:a() (S)B:b()\n")
            (reduced / "oh-package.json5").write_text('{"name":"demo"}')
            source = reduced / "Main.ets"
            source.write_text(
                "import { relationalStore } from '@kit.ArkData'\n"
                "import { Unused } from 'third-party'\n"
                "export function main() { return relationalStore }\n"
            )
            with patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.ORIGINAL_PROJECTS",
                root / "original",
            ), patch(
                "arkts_src.phase_a_preprocessing.arkts_reduce_third_party_libs.REDUCED_PROJECTS",
                root / "reduced",
            ):
                trusted, untrusted, removed = reduce_project("Demo")

            self.assertEqual((1, 1, 1), (trusted, untrusted, removed))
            self.assertIn("@kit.ArkData", (reduced / "trusted.txt").read_text())
            record = json.loads((reduced / "untrusted.jsonl").read_text())
            self.assertEqual("third-party", extract_imports(record["body"])[0]["module"])
            self.assertNotIn("third-party", source.read_text())
            self.assertTrue((reduced / "callgraph.txt").is_file())


if __name__ == "__main__":
    unittest.main()
