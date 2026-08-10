"""根据 ArkTS schema 生成 AlphaTrans 兼容的项目依赖文件。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# 本文件位于 arkts_src/phase_c_skeleton，向上两级定位 AlphaTrans 仓库根目录。
ROOT = Path(__file__).resolve().parents[2]
# ArkTS 迁移产物统一使用 arkts_data，避免修改原版 data 目录。
DATA = ROOT / "arkts_data"


def _load_schemas(project: str) -> dict[str, dict]:
    """读取项目的全部 Phase B schema，并以文件名主干作为模块标识。"""
    # Phase B 为每个 ArkTS 源文件生成一个 JSON schema。
    schema_dir = DATA / "schemas" / project
    # path.stem 与 schema 中 calls 的模块名一致，可直接关联 ArkAnalyzer 调用边。
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(schema_dir.glob("*.json"))
    }


def _class_nodes(schemas: dict[str, dict]) -> tuple[dict[str, tuple[str, str]], dict[str, list[str]]]:
    """建立限定节点及简单类名索引，避免 ArkTS 不同模块的同名类互相覆盖。"""
    nodes: dict[str, tuple[str, str]] = {}
    by_name: dict[str, list[str]] = {}
    for module, schema in schemas.items():
        # 只有顶层函数的文件没有 class，用 <module> 表示模块级依赖节点。
        class_names = list(schema.get("classes", {})) or ["<module>"]
        for class_name in class_names:
            # ArkTS 项目可能在不同模块定义同名类，因此节点使用“模块:类名”。
            node = f"{module}:{class_name}"
            nodes[node] = (module, class_name)
            by_name.setdefault(class_name, []).append(node)
    return nodes, by_name


def _type_names(value: object) -> set[str]:
    """从 ArkTS 类型表达式中提取可能引用的类名。"""
    if not isinstance(value, str):
        return set()
    # 泛型、联合类型和限定类型都先拆为标识符，再与项目类索引匹配。
    return set(re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*", value))


def _resolve_named_dependency(
    name: str,
    current_module: str,
    by_name: dict[str, list[str]],
) -> str | None:
    """优先选择同模块或唯一类名，无法唯一确定时不制造错误依赖。"""
    candidates = by_name.get(name, [])
    # 全项目只有一个同名类时可以直接确定依赖目标。
    if len(candidates) == 1:
        return candidates[0]
    # 存在同名类时只接受当前模块中的唯一匹配，避免依赖指向错误模块。
    same_module = [node for node in candidates if node.startswith(f"{current_module}:")]
    return same_module[0] if len(same_module) == 1 else None


def _member_type_values(member: dict) -> list[str]:
    """读取字段、参数和返回值中的源码类型。"""
    values: list[str] = []
    # types 用于字段，return_types 用于方法；两者均保存 [源码类型, ArkIR 类型]。
    for pair in member.get("types", []) + member.get("return_types", []):
        if isinstance(pair, list) and pair and isinstance(pair[0], str):
            values.append(pair[0])
    # parameter_details 是 ArkTS 增补字段，保留参数源码类型及 optional/rest/default。
    for parameter in member.get("parameter_details", []):
        if isinstance(parameter, dict) and isinstance(parameter.get("type"), str):
            values.append(parameter["type"])
    return values


def _topological_order(graph: dict[str, set[str]]) -> list[str]:
    """生成依赖优先的稳定顺序；遇到循环时忽略回边并继续。"""
    order: list[str] = []
    # state: 1 表示当前 DFS 路径，2 表示节点已经写入最终顺序。
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            # 再次遇到访问中的节点说明存在环；忽略回边，保留其余可排序关系。
            return
        state[node] = 1
        for dependency in sorted(graph.get(node, set())):
            if dependency in graph:
                visit(dependency)
        state[node] = 2
        order.append(node)

    for node in sorted(graph):
        visit(node)
    return order


def generate_dependencies(project: str) -> tuple[dict, dict]:
    """生成 dependencies.json 和 traversal.json。"""
    schemas = _load_schemas(project)
    nodes, by_name = _class_nodes(schemas)
    # graph 的方向是“当前节点 -> 当前节点依赖的节点”。
    graph: dict[str, set[str]] = {node: set() for node in nodes}

    for node, (module, class_name) in nodes.items():
        schema = schemas[module]
        class_data = schema.get("classes", {}).get(class_name, {})

        # 继承、接口、字段和方法签名均会影响骨架中的 Python 类型依赖。
        type_values: list[str] = []
        type_values.extend(class_data.get("extends", []))
        type_values.extend(class_data.get("implements", []))
        for field in class_data.get("fields", {}).values():
            type_values.extend(_member_type_values(field))
        callables = list(class_data.get("methods", {}).values())
        if class_name == "<module>":
            # 无类文件的调用边存放在顶层 functions 中。
            callables.extend(schema.get("functions", {}).values())
        for callable_data in callables:
            type_values.extend(_member_type_values(callable_data))
            # Phase B 已把 ArkAnalyzer 调用图写入 calls，项目内调用直接形成依赖。
            for call in callable_data.get("calls", []):
                if not isinstance(call, list) or not call or call[0] == "library":
                    continue
                target_module = call[0]
                target_class = call[1] if len(call) > 1 and call[1] else "<module>"
                target_node = f"{target_module}:{target_class}"
                if target_node in graph and target_node != node:
                    graph[node].add(target_node)

        for type_value in type_values:
            for name in _type_names(type_value):
                dependency = _resolve_named_dependency(name, module, by_name)
                if dependency and dependency != node:
                    graph[node].add(dependency)

    # 与原版保持相同的二元依赖项：[依赖类名, 依赖模块路径]。
    dependencies = {
        node: [[nodes[dependency][1], nodes[dependency][0]] for dependency in sorted(values)]
        for node, values in graph.items()
    }
    # traversal.json 为后续骨架生成提供依赖优先的稳定顺序。
    order = _topological_order(graph)
    traversal = {str(index): node for index, node in enumerate(order)}

    out = DATA / "dependencies" / project
    out.mkdir(parents=True, exist_ok=True)
    (out / "dependencies.json").write_text(
        json.dumps(dependencies, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    (out / "traversal.json").write_text(
        json.dumps(traversal, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    return dependencies, traversal


def main() -> None:
    """执行 ArkTS 项目依赖生成。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    args = parser.parse_args()
    dependencies, traversal = generate_dependencies(args.project)
    edges = sum(len(values) for values in dependencies.values())
    print(f"DEPENDENCIES={len(dependencies)} EDGES={edges} TRAVERSAL={len(traversal)}")


if __name__ == "__main__":
    main()
