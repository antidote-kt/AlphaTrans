"""从 Phase B schema 和查询输出收集 ArkTS 类型。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Phase C 只读取 Phase B 产物；类型映射结果统一放在 arkts_data。
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def _portable_location(location: dict) -> dict:
    """将工作区绝对路径转换为仓库相对路径，保证结果可移植。"""
    result = dict(location)
    filename = result.get("file")
    if isinstance(filename, str):
        try:
            result["file"] = str(Path(filename).resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            result["file"] = filename
    return result


def _add(found: dict, value: object, location: dict) -> None:
    """记录类型及其出现位置，位置信息与原版输入表分开保存。"""
    if not isinstance(value, str):
        return
    value = value.strip()
    if not value or value in {"unknown", "void"}:
        return
    found.setdefault(value, []).append(_portable_location(location))


def _walk(value: object, found: dict, classes: set[str], location: dict) -> None:
    """递归读取 schema 类型，并收集项目内定义的类名。"""
    if isinstance(value, dict):
        # classes 的键就是项目自定义类；接口、struct 和 enum 也作为项目类型保留。
        for class_name in value.get("classes", {}):
            if isinstance(class_name, str):
                classes.add(class_name)
        for key, item in value.items():
            if key in {"type", "resolved_type", "return_type", "extends", "implements"}:
                items = item if isinstance(item, list) else [item]
                for one in items:
                    if isinstance(one, list):
                        for nested in one:
                            _add(found, nested, {**location, "field": key})
                    else:
                        _add(found, one, {**location, "field": key})
            _walk(item, found, classes, location)
    elif isinstance(value, list):
        for item in value:
            _walk(item, found, classes, location)


def collect_types(project: str) -> dict:
    """收集项目类型并生成 AlphaTrans 兼容的类型翻译输入。"""
    # Phase B 为每个 ArkTS 源文件生成一个 schema，类型收集以这些文件为主要输入。
    schema_dir = DATA / "schemas" / project
    # found 保存“类型名 -> 出现位置”，classes 单独保存项目自己声明的类型。
    found: dict = {}
    classes: set[str] = set()
    for path in sorted(schema_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # 单个 schema 无法读取时跳过，避免阻止其余源码类型的收集。
            continue
        # 递归收集字段、参数、返回值、继承关系中的源码类型和 resolved_type。
        _walk(data, found, classes, {"file": data.get("path", str(path))})

    # query output 用于补充 schema 遍历可能遗漏的类型，保持与原版数据流一致。
    # types.txt 是两列竖线格式，只读取第一列类型名，避免把整行文本拆成伪类型。
    query = DATA / "query_outputs" / project / f"{project}_types.txt"
    if query.exists():
        for line_no, line in enumerate(query.read_text(encoding="utf-8").splitlines(), 1):
            # 例如“| String | string |”拆分后，columns[1] 是 ArkTS 源码类型。
            columns = [item.strip() for item in line.split("|")]
            if len(columns) >= 3 and columns[1]:
                # 记录查询文件和行号，便于追溯该类型为何进入映射流程。
                _add(
                    found,
                    columns[1],
                    {"file": str(query), "line": line_no, "field": "query"},
                )

    # 类型翻译产物与项目隔离保存，不修改 Phase B schema 和原版 data 目录。
    out = DATA / "type_resolution" / project
    out.mkdir(parents=True, exist_ok=True)
    # 泛型实例使用其基础类判断，避免把项目类型送到官方文档搜索。
    def is_project_type(name: str) -> bool:
        base_name = name.strip()
        base_name = base_name.removeprefix("new ").strip()
        base_name = base_name.split("<", 1)[0].strip()
        base_name = base_name.removesuffix("[]").strip()
        return base_name in classes

    # 类型参数没有独立官方文档，保留符号本身，不参与文档抓取。
    def is_type_parameter(name: str) -> bool:
        base_name = name.strip().removesuffix("[]").strip()
        return base_name.isidentifier() and len(base_name) <= 2 and base_name[0].isupper()

    # 与原版一致：项目类型和类型参数保留原名，SDK/外部类型留空等待 LLM 翻译。
    s1_input = {
        name: (name if is_project_type(name) or is_type_parameter(name) else "")
        for name in sorted(found)
    }
    # s1_input.json 只保存“类型名 -> 当前映射”，供后续文档抓取和类型翻译读取。
    (out / "s1_input.json").write_text(
        json.dumps(s1_input, ensure_ascii=False, indent=4), encoding="utf-8"
    )
    # 类型出现位置单独保存，避免改变 AlphaTrans 原版 s1_input.json 的输入结构。
    (out / "type_locations.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return s1_input


def main() -> None:
    """执行命令行类型收集。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    args = parser.parse_args()
    result = collect_types(args.project)
    print(f"TYPES={len(result)}")


if __name__ == "__main__":
    main()
