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
    """生成项目 callable 调用图，并标记 ArkTS 测试入口。"""
    translation_dir = _translation_dir(project, model, prompt_type, temperature)
    # model、prompt_type 和 temperature 只用于定位 C 阶段输出目录；
    # 本脚本不请求 LLM，也不会修改任何 fragment 的翻译结果。
    # graph 节点对应可独立翻译的 callable，调用边直接复用 Phase B
    # 已写入 partial schema 的 calls 信息。
    graph: dict[str, dict] = {}

    for path in sorted(translation_dir.glob("*_python_partial.json")):
        # schema 名由模块和源码路径组成，用它区分不同文件中的同名类或函数。
        schema_name = path.name.removesuffix("_python_partial.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        # ArkTS 的单元测试和设备测试目录都视作测试入口来源。
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
    # 该图表示静态调用依赖，不表示测试运行时覆盖率。
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
