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
    """按 AlphaTrans 原版格式收集项目类型并写入 s1_input.json。

    `s1_input.json` 保持为 ``类型名 -> 当前映射``：项目自定义类型映射为自身，
    外部类型使用空字符串等待 LLM 翻译。类型出现位置另存为 type_locations.json，
    不改变原版类型翻译脚本预期的输入结构。
    """
    schema_dir = DATA / "schemas" / project
    found: dict = {}
    classes: set[str] = set()
    for path in sorted(schema_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        _walk(data, found, classes, {"file": data.get("path", str(path))})

    # types.txt 是两列竖线格式，只读取第一列类型名，避免把整行文本拆成伪类型。
    query = DATA / "query_outputs" / project / f"{project}_types.txt"
    if query.exists():
        for line_no, line in enumerate(query.read_text(encoding="utf-8").splitlines(), 1):
            columns = [item.strip() for item in line.split("|")]
            if len(columns) >= 3 and columns[1]:
                _add(found, columns[1], {"file": str(query), "line": line_no, "field": "query"})

    out = DATA / "type_resolution" / project
    out.mkdir(parents=True, exist_ok=True)
    # 与原版一致：项目类已有目标名，SDK/外部类型留空交给后续翻译。
    s1_input = {name: (name if name in classes else "") for name in sorted(found)}
    (out / "s1_input.json").write_text(json.dumps(s1_input, ensure_ascii=False, indent=4), encoding="utf-8")
    (out / "type_locations.json").write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
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
