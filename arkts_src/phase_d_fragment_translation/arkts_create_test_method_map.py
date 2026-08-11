"""从 partial schema 生成测试调用映射和全局 callable 调用图。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def _translation_dir(project: str, model: str, prompt_type: str, temperature: str) -> Path:
    """返回 C 阶段生成的 partial schema 目录。"""
    return DATA / "schemas" / "translations" / model / prompt_type / temperature / project


def _callable_id(schema_name: str, class_name: str, callable_name: str) -> str:
    """使用限定标识区分不同 ArkTS 模块中的同名 callable。"""
    return f"{schema_name}|{class_name}|{callable_name}"


def _calls(callable_data: dict) -> list[dict]:
    """只保留能够映射到项目 partial schema 的调用边。"""
    result: list[dict] = []
    for call in callable_data.get("calls", []):
        if not isinstance(call, list) or len(call) < 3 or call[0] == "library":
            continue
        # Phase B 的方法标识包含 start-end:name；没有冒号的 ArkIR 内部调用不作为 fragment。
        if ":" not in call[2]:
            continue
        result.append(
            {
                "schema": call[0],
                "class": call[1] or "<module>",
                "callable": call[2],
            }
        )
    return result


def create_test_method_map(
    project: str,
    model: str,
    prompt_type: str = "body",
    temperature: str = "0.0",
) -> dict:
    """生成项目 callable 调用图，并标记 ArkTS 测试入口。

    Java 原版只遍历类方法；ArkTS 允许顶层函数，因此使用 ``<module>`` 作为
    顶层 callable 的所属类标识。``src.test`` 和 ``src.ohosTest`` 中的 callable
    统一标记为测试入口，供后续组合验证选择测试。
    """
    translation_dir = _translation_dir(project, model, prompt_type, temperature)
    graph: dict[str, dict] = {}

    for path in sorted(translation_dir.glob("*_python_partial.json")):
        schema_name = path.name.removesuffix("_python_partial.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        is_test_schema = ".src.test." in schema_name or ".src.ohosTest." in schema_name

        for class_name, class_data in schema.get("classes", {}).items():
            for callable_name, callable_data in class_data.get("methods", {}).items():
                fragment_id = _callable_id(schema_name, class_name, callable_name)
                graph[fragment_id] = {
                    "schema": schema_name,
                    "class": class_name,
                    "callable": callable_name,
                    "kind": callable_data.get("kind", "method"),
                    "is_test": is_test_schema,
                    "calls": _calls(callable_data),
                }

        # ArkTS 顶层函数没有 Java 对应结构，但仍需要参与调用排序和测试翻译。
        for callable_name, callable_data in schema.get("functions", {}).items():
            fragment_id = _callable_id(schema_name, "<module>", callable_name)
            graph[fragment_id] = {
                "schema": schema_name,
                "class": "<module>",
                "callable": callable_name,
                "kind": callable_data.get("kind", "function"),
                "is_test": is_test_schema,
                "calls": _calls(callable_data),
            }

    out = DATA / "call_graphs" / project
    out.mkdir(parents=True, exist_ok=True)
    (out / "call_graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return graph


def main() -> None:
    """执行命令行测试调用映射生成。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("model")
    parser.add_argument("prompt_type", nargs="?", default="body")
    parser.add_argument("temperature", nargs="?", default="0.0")
    args = parser.parse_args()
    graph = create_test_method_map(
        args.project, args.model, args.prompt_type, args.temperature
    )
    tests = sum(bool(item["is_test"]) for item in graph.values())
    edges = sum(len(item["calls"]) for item in graph.values())
    print(f"CALLABLES={len(graph)} TEST_CALLABLES={tests} EDGES={edges}")


if __name__ == "__main__":
    main()
