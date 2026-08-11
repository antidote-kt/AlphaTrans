"""根据 callable 调用图生成 fragment 依赖优先的翻译顺序。"""
from __future__ import annotations

import json
from pathlib import Path


def _visit(
    fragment_id: str,
    dependencies: dict[str, set[str]],
    state: dict[str, int],
    order: list[str],
) -> None:
    """深度优先访问依赖；遇到递归回边时保留稳定源码顺序。"""
    if state.get(fragment_id) == 2:
        return
    if state.get(fragment_id) == 1:
        return
    state[fragment_id] = 1
    for dependency in sorted(dependencies.get(fragment_id, set())):
        if dependency in dependencies:
            _visit(dependency, dependencies, state, order)
    state[fragment_id] = 2
    order.append(fragment_id)


def get_fragment_traversal(call_graph_path: Path, translation_dir: Path) -> list[dict]:
    """生成字段优先、被调用者优先、测试最后的 fragment 顺序。"""
    graph = json.loads(call_graph_path.read_text(encoding="utf-8"))
    dependencies: dict[str, set[str]] = {fragment_id: set() for fragment_id in graph}
    for fragment_id, item in graph.items():
        for call in item.get("calls", []):
            target = f"{call['schema']}|{call['class']}|{call['callable']}"
            if target in graph and target != fragment_id:
                dependencies[fragment_id].add(target)

    callable_order: list[str] = []
    state: dict[str, int] = {}
    for fragment_id in sorted(graph):
        _visit(fragment_id, dependencies, state, callable_order)

    fields: list[dict] = []
    for path in sorted(translation_dir.glob("*_python_partial.json")):
        schema_name = path.name.removesuffix("_python_partial.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        for class_name, class_data in schema.get("classes", {}).items():
            for field_name, field_data in class_data.get("fields", {}).items():
                # Enum 会在重组时整体生成，不需要把每个成员交给 LLM 翻译。
                if field_data.get("kind") == "enum_member":
                    continue
                fields.append(
                    {
                        "schema_name": schema_name,
                        "class_name": class_name,
                        "fragment_name": field_name,
                        "fragment_type": "field",
                        "is_test": False,
                    }
                )

    callables = [
        {
            "schema_name": graph[fragment_id]["schema"],
            "class_name": graph[fragment_id]["class"],
            "fragment_name": graph[fragment_id]["callable"],
            "fragment_type": "function"
            if graph[fragment_id]["class"] == "<module>"
            else "method",
            "is_test": bool(graph[fragment_id]["is_test"]),
        }
        for fragment_id in callable_order
    ]
    non_tests = [item for item in callables if not item["is_test"]]
    tests = [item for item in callables if item["is_test"]]
    traversal = fields + non_tests + tests

    output = call_graph_path.with_name("fragment_traversal.json")
    output.write_text(json.dumps(traversal, ensure_ascii=False, indent=4), encoding="utf-8")
    return traversal
