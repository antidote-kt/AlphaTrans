"""将各 partial schema 中的 fragment 翻译重组为完整 Python 项目。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def _selected_lines(item: dict) -> list[str]:
    """成功翻译时选择 translation，否则保留带 pass 的骨架。"""
    translation = item.get("translation") or []
    if translation and item.get("syntactic_validation") == "parseable":
        return translation
    return item.get("partial_translation") or []


def _enum_lines(class_name: str, class_data: dict) -> list[str]:
    """重组 enum；枚举成员不是可独立翻译的普通 Python 字段。"""
    lines = [f"class {class_name}(Enum):"]
    fields = class_data.get("fields", {})
    for index, (name, field) in enumerate(fields.items(), 1):
        value = field.get("initializer")
        if not isinstance(value, str) or not value.strip():
            value = f"auto()  # {index}"
        value = value.replace("true", "True").replace("false", "False")
        lines.append(f"    {name} = {value}")
    if not fields:
        lines.append("    pass")
    return lines


def _module_path(schema_name: str) -> Path:
    """保持 ArkTS schema 模块边界生成 Python 包路径。"""
    parts = schema_name.split(".")
    return Path(*parts[:-1]) / f"{parts[-1]}.py"


def _ensure_packages(root: Path, parent: Path) -> None:
    """逐级创建 __init__.py，使重组项目可通过点分路径导入。"""
    current = root
    (current / "__init__.py").touch()
    for part in parent.relative_to(root).parts:
        current /= part
        current.mkdir(exist_ok=True)
        (current / "__init__.py").touch()


def _class_order(schema: dict) -> list[str]:
    """在同一文件中保证项目父类先于子类。"""
    classes = schema.get("classes", {})
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(name: str) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            return
        state[name] = 1
        data = classes[name]
        for base in data.get("extends", []) + data.get("implements", []):
            base_name = base.split("<", 1)[0].strip()
            if base_name in classes:
                visit(base_name)
        state[name] = 2
        order.append(name)

    for class_name in classes:
        visit(class_name)
    return order


def _render_schema(schema: dict, is_test_schema: bool = False) -> str:
    """根据 partial schema 当前状态渲染一个完整 Python 模块。"""
    # 先去重并写入 C 阶段生成的 import，再按继承顺序输出类定义。
    lines = list(dict.fromkeys(schema.get("python_imports", []))) + [""]
    for class_name in _class_order(schema):
        class_data = schema["classes"][class_name]
        if class_data.get("kind") == "enum":
            lines.extend(_enum_lines(class_name, class_data) + [""])
            continue

        declaration = class_data.get("python_class_declaration", f"class {class_name}:\n").rstrip()
        lines.append(declaration)
        members = 0
        # 字段必须位于方法之前；失败的字段由 _selected_lines 回退到骨架。
        for field in class_data.get("fields", {}).values():
            if field.get("kind") == "enum_member":
                continue
            lines.extend(line.rstrip("\n") for line in _selected_lines(field))
            members += 1
        # 方法保持 partial schema 中的稳定顺序，便于错误行回溯到对应 fragment。
        for method in class_data.get("methods", {}).values():
            if members:
                lines.append("")
            lines.extend(line.rstrip("\n") for line in _selected_lines(method))
            members += 1
        if not members:
            lines.append("    pass")
        lines.append("")

    # ArkTS 顶层函数必须放在类定义之外，不能按原版 Java 的类方法路径处理。
    test_aliases: list[str] = []
    for function_key, function in schema.get("functions", {}).items():
        lines.extend(line.rstrip("\n") for line in _selected_lines(function))
        lines.append("")
        # Hypium 外层函数不一定以 test 开头；增加别名供 pytest 收集。
        if is_test_schema:
            function_name = function_key.split(":", 1)[-1]
            if not function_name.startswith("test"):
                test_aliases.append(f"test_{function_name} = {function_name}")
    lines.extend(test_aliases)
    return "\n".join(lines).rstrip() + "\n"


def recompose_project(
    project: str,
    model: str,
    prompt_type: str = "body",
    temperature: str = "0.0",
) -> Path:
    """重组完整项目并返回输出根目录。"""
    translation_dir = (
        DATA / "schemas" / "translations" / model / prompt_type / temperature / project
    )
    output_root = (
        DATA / "recomposed_projects" / model / prompt_type / temperature / project
    )
    output_root.mkdir(parents=True, exist_ok=True)

    # 一个 partial schema 对应一个 Python 模块；schema 限定名转换为包目录，
    # 不把不同 ArkTS 文件中的类合并到同一 Python 文件。
    for path in sorted(translation_dir.glob("*_python_partial.json")):
        schema_name = path.name.removesuffix("_python_partial.json")
        schema = json.loads(path.read_text(encoding="utf-8"))
        output_path = output_root / _module_path(schema_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_packages(output_root, output_path.parent)
        is_test_schema = (
            ".src.test." in schema_name or ".src.ohosTest." in schema_name
        )
        output_path.write_text(
            _render_schema(schema, is_test_schema), encoding="utf-8"
        )

    # 与原版一致使用 Black；未安装时不影响后续 AST/compile 验证。
    subprocess.run(
        [sys.executable, "-m", "black", "--quiet", str(output_root)],
        capture_output=True,
        text=True,
    )
    return output_root


def main() -> None:
    """执行命令行项目重组。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("model")
    parser.add_argument("prompt_type", nargs="?", default="body")
    parser.add_argument("temperature", nargs="?", default="0.0")
    args = parser.parse_args()
    output = recompose_project(
        args.project, args.model, args.prompt_type, args.temperature
    )
    print(f"RECOMPOSED={output}")


if __name__ == "__main__":
    main()
