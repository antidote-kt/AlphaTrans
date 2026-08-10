"""根据 ArkTS schema 和类型映射生成并验证 Python 项目骨架。

处理过程与 AlphaTrans 原版 create_skeleton.py 对应：先按 traversal.json 确定
文件顺序，再生成 Python 类、字段和 callable 签名，同时把 partial_translation
等状态写回副本 schema。原始 ArkTS schema 和源码均不会被修改。
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import keyword
import os
import re
import subprocess
import sys
from pathlib import Path

# 本文件位于 arkts_src/phase_c_skeleton，向上两级定位仓库根目录。
ROOT = Path(__file__).resolve().parents[2]
# 所有 ArkTS 骨架、依赖和 partial schema 均写入独立的 arkts_data。
DATA = ROOT / "arkts_data"


def _safe_name(name: str, fallback: str = "value") -> str:
    """把 ArkTS 标识符转换为合法 Python 标识符。

    Args:
        name: schema 中保存的 ArkTS 名称，可能包含 ``##``、``$`` 或 Python 关键字。
        fallback: 名称清理后为空时使用的替代名称。

    Returns:
        可用于 Python 类名、字段名、方法名或参数名的标识符。
    """
    # ArkTS 编译器可能产生 ##storage 等 Python 不允许的标识符，统一替换非法字符。
    value = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_") or fallback
    # Python 标识符不能以数字开头。
    if value[0].isdigit():
        value = f"_{value}"
    # class、from 等 Python 关键字通过后缀下划线消除冲突。
    if keyword.iskeyword(value):
        value += "_"
    return value


def _split_generic_arguments(text: str) -> list[str]:
    """按顶层逗号拆分 ArkTS 泛型参数。

    普通 ``str.split(',')`` 会错误拆分 ``Map<string, Array<number>>``，因此需要
    记录尖括号深度，只在最外层拆分。

    Args:
        text: 不含最外层尖括号的泛型参数文本。

    Returns:
        保持原有嵌套结构的参数列表。
    """
    result: list[str] = []
    # depth 记录嵌套泛型层级，只有 depth=0 的逗号才是当前泛型的分隔符。
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    result.append(text[start:].strip())
    return [item for item in result if item]


def _python_type(source_type: str, type_map: dict[str, str]) -> str:
    """把一个 ArkTS 类型渲染为可解析的 Python 类型表达式。

    Args:
        source_type: schema 中记录的 ArkTS 源码类型。
        type_map: Phase C ``s1_output.json`` 的完整映射。

    Returns:
        Python 类型注解。项目类型保持名称不变，只把 ``T[]``、``A<T>`` 等
        ArkTS 表示法改成 ``list[T]``、``A[T]``，不重新进行语义翻译。
    """
    source = (source_type or "").strip()
    # ArkTS void 对应 Python 无返回值 None。
    if source == "void":
        return "None"
    # schema 无法确定类型时使用 Any，保证骨架仍是合法 Python。
    if not source or source in {"unknown", "undefined"}:
        return "Any"
    # 项目类型和外部类型都优先读取 Phase C 的 s1_output.json。
    mapped = type_map.get(source, source).strip() or "Any"
    mapped = mapped.replace("\\u007c", "|")
    # future annotations 已处理前向引用，去掉 LLM 返回的外层引号便于组合 Optional。
    if len(mapped) >= 2 and mapped[0] == mapped[-1] and mapped[0] in "'\"" and re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*", mapped[1:-1]):
        mapped = mapped[1:-1]
    # schema 映射为自身的项目数组仍使用 ArkTS [] 语法，这里只转换表示形式。
    if mapped.endswith("[]"):
        return f"list[{_python_type(mapped[:-2], type_map)}]"
    # BaseMapper<T> 等项目泛型保留类型名，只把尖括号改为 Python 方括号。
    match = re.fullmatch(r"([^<]+)<(.+)>", mapped)
    if match:
        base = match.group(1).strip()
        args = ", ".join(_python_type(item, type_map) for item in _split_generic_arguments(match.group(2)))
        return f"{base}[{args}]"
    return mapped


def _source_type(member: dict, field: str) -> str:
    """从 schema 的二元类型记录中取得源码类型。

    Phase B 将字段和返回值记录为 ``[[source_type, resolved_type]]``。骨架生成
    使用第一项查询 Phase C 映射，避免把 ArkIR 的擦除类型误当成源码签名。
    """
    values = member.get(field, [])
    # Phase B 的类型字段格式是 [[源码类型, ArkIR 解析类型]]，骨架优先使用源码类型键查映射。
    if values and isinstance(values[0], list) and values[0]:
        return values[0][0]
    return "void" if field == "return_types" else "unknown"


def _default_value(parameter: dict) -> str | None:
    """把 ArkTS 可选参数或默认值转换为安全的 Python 默认值。

    仅直接保留数字、布尔值和字符串字面量。对象表达式、函数调用等需要方法体
    翻译才能确定，因此骨架阶段统一使用 ``None``。
    """
    # 必选且没有默认值的参数不生成等号。
    if not parameter.get("optional") and parameter.get("default") is None:
        return None
    value = parameter.get("default")
    # ArkTS undefined/null 和只有 optional 标记的参数统一使用安全默认值 None。
    if value in {None, "undefined", "null"}:
        return "None"
    if value in {"true", "false"}:
        return value.title()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", str(value)):
        return str(value)
    if isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value
    return "None"


def _parameter_list(callable_data: dict, type_map: dict[str, str], include_self: bool) -> str:
    """生成 callable 的完整 Python 参数列表。

    Args:
        callable_data: 方法或顶层函数的 schema。
        type_map: ArkTS 到 Python 的类型映射。
        include_self: 实例方法为 True，staticmethod 和顶层函数为 False。

    Returns:
        可直接放入 ``def name(...)`` 的参数文本，包含 optional、default 和 rest。
    """
    # 实例方法需要 self，staticmethod 和顶层函数不需要。
    parts = ["self"] if include_self else []
    # Python 不允许必选参数出现在默认参数之后，因此记录是否已经出现默认值。
    default_seen = False
    for index, parameter in enumerate(callable_data.get("parameter_details", [])):
        name = _safe_name(parameter.get("name", ""), f"arg{index}")
        annotation = _python_type(parameter.get("type") or parameter.get("resolved_type") or "unknown", type_map)
        default = _default_value(parameter)
        if parameter.get("rest"):
            # ArkTS ...args: string[] 对应 Python *args: str，注解描述单个可变参数元素。
            if annotation.startswith("list[") and annotation.endswith("]"):
                annotation = annotation[5:-1]
            parts.append(f"*{name}: {annotation}")
            continue
        if default is not None:
            default_seen = True
            parts.append(f"{name}: {annotation} = {default}")
        elif default_seen:
            parts.append(f"{name}: {annotation} = None")
        else:
            parts.append(f"{name}: {annotation}")
    return ", ".join(parts)


def _method_name(key: str) -> str:
    """从 ``起始行-结束行:方法名`` 格式的 schema 键中取得方法名。"""
    return key.split(":", 1)[1] if ":" in key else key


def _render_callable(
    key: str,
    data: dict,
    type_map: dict[str, str],
    in_class: bool,
    abstract: bool,
) -> list[str]:
    """生成一个 callable 的 Python 签名和空方法体。

    Args:
        key: schema callable 标识，格式通常为 ``start-end:name``。
        data: callable schema，包含 kind、modifiers、参数和返回类型。
        type_map: Phase C 类型映射。
        in_class: 是否位于类内部，用于决定是否生成 self。
        abstract: 所属类是否为 interface 或抽象类。

    Returns:
        不带类级缩进的代码行；调用方根据模块级或类级位置添加缩进。
    """
    kind = data.get("kind", "method")
    original_name = _method_name(key)
    # ArkTS constructor 不以类名作为方法名，直接根据 kind 转换为 __init__。
    name = "__init__" if data.get("is_constructor") or kind == "constructor" else _safe_name(original_name)
    modifiers = set(data.get("modifiers", []))
    is_static = in_class and "static" in modifiers
    include_self = in_class and not is_static
    # async 修饰符来自 schema modifiers，保留为 Python async def。
    prefix = "async def" if "async" in modifiers else "def"
    parameters = _parameter_list(data, type_map, include_self)
    return_type = "None" if name == "__init__" else _python_type(_source_type(data, "return_types"), type_map)
    lines: list[str] = []
    # getter/setter 使用 Python property；普通静态方法使用 staticmethod。
    if kind == "getter":
        lines.append("@property")
    elif kind == "setter":
        lines.append(f"@{_safe_name(original_name)}.setter")
    elif is_static:
        lines.append("@staticmethod")
    # 与 AlphaTrans 原版一致，interface/abstract class 的方法标记为 abstractmethod。
    if abstract and name != "__init__":
        lines.append("@abstractmethod")
    lines.append(f"{prefix} {name}({parameters}) -> {return_type}:")
    lines.append("    pass")
    return lines


def _enum_value(field: dict, index: int) -> str:
    """把 ArkTS 枚举成员初始值转换为 Python 表达式。

    字符串、数字和布尔字面量可以安全复用；复杂表达式留到 fragment 阶段，
    骨架中使用 ``auto()`` 保证 Enum 定义可执行。
    """
    value = field.get("initializer")
    if isinstance(value, str) and re.fullmatch(r"(?:-?\d+(?:\.\d+)?|true|false|'[^']*'|\"[^\"]*\")", value):
        return value.replace("true", "True").replace("false", "False")
    return f"auto()  # {index}"


def _render_class(name: str, data: dict, type_map: dict[str, str], project_classes: set[str]) -> tuple[list[str], str]:
    """生成单个 ArkTS class、interface、struct 或 enum 的 Python 骨架。

    Args:
        name: ArkTS 类型名。
        data: 类型对应的 schema。
        type_map: Phase C 类型映射。
        project_classes: 项目内定义的类名集合，用于过滤无法导入的 SDK 父类。

    Returns:
        ``(代码行, 类声明)``。代码行包含字段和方法；类声明单独写入 partial schema。
    """
    class_name = _safe_name(name, "GeneratedClass")
    kind = data.get("kind", "class")
    abstract = bool(data.get("is_abstract") or data.get("is_interface") or kind == "interface")
    # ArkTS enum 使用标准库 Enum；interface 和抽象类使用原版采用的 ABC。
    if kind == "enum":
        declaration = f"class {class_name}(Enum):"
    else:
        bases: list[str] = []
        for base in data.get("extends", []) + data.get("implements", []):
            base_name = re.split(r"[<.(]", base)[0].strip()
            # 只把项目内父类写入 Python 继承列表；HarmonyOS SDK 父类没有 Python 实现，不能直接继承。
            if base_name in project_classes and base_name != name:
                bases.append(_safe_name(base_name))
        if abstract:
            bases.append("ABC")
        declaration = f"class {class_name}({', '.join(dict.fromkeys(bases))}):" if bases else f"class {class_name}:"

    lines = [declaration]
    if kind == "enum":
        fields = data.get("fields", {})
        for index, (field_name, field) in enumerate(fields.items(), 1):
            lines.append(f"    {_safe_name(field_name)} = {_enum_value(field, index)}")
        if not fields:
            lines.append("    pass")
        return lines, declaration

    for field_name, field in data.get("fields", {}).items():
        if field.get("kind") == "enum_member":
            continue
        python_name = _safe_name(field_name)
        # 沿用原版命名约定：private 使用双下划线，protected 使用单下划线。
        if "private" in field.get("modifiers", []):
            python_name = f"__{python_name}"
        elif "protected" in field.get("modifiers", []):
            python_name = f"_{python_name}"
        annotation = _python_type(_source_type(field, "types"), type_map)
        if field.get("optional") and "None" not in annotation:
            annotation = f"{annotation} | None"
        lines.append(f"    {python_name}: {annotation} = None")

    methods = sorted(data.get("methods", {}).items(), key=lambda item: item[1].get("start", 0))
    # ArkTS schema 中 setter 可能位于 getter 前；只交换同名 property，其他方法保持源码顺序。
    for index, (key, method) in enumerate(methods):
        if method.get("kind") != "setter":
            continue
        getter_index = next(
            (
                candidate_index
                for candidate_index in range(index + 1, len(methods))
                if _method_name(methods[candidate_index][0]) == _method_name(key)
                and methods[candidate_index][1].get("kind") == "getter"
            ),
            None,
        )
        if getter_index is not None:
            methods[index], methods[getter_index] = methods[getter_index], methods[index]
    for key, method in methods:
        rendered = _render_callable(key, method, type_map, True, abstract)
        lines.append("")
        lines.extend(f"    {line}" if line else "" for line in rendered)
    if len(lines) == 1:
        lines.append("    pass")
    return lines, declaration


def _module_path(schema_name: str) -> Path:
    """将 ArkTS schema 模块名转换为 Python 包路径。

    例如 ``rdbplus.src.main.ets.core.Connection`` 转换为
    ``rdbplus/src/main/ets/core/Connection.py``，从而保留源码模块边界。
    """
    # schema 名已由 Phase B 按“模块.源码目录.文件名”生成，直接展开为 Python 包目录。
    parts = schema_name.split(".")
    return Path(*parts[:-1]) / f"{parts[-1]}.py"


def _base_imports(schema_name: str, schema: dict, class_locations: dict[str, list[str]]) -> list[str]:
    """为项目内继承和接口实现生成运行时必需的 Python import。

    方法参数和字段注解受 ``from __future__ import annotations`` 保护，不需要立即
    导入；父类会在 class 声明时求值，所以必须生成真实 import。
    """
    imports: list[str] = []
    for class_data in schema.get("classes", {}).values():
        for base in class_data.get("extends", []) + class_data.get("implements", []):
            base_name = re.split(r"[<.(]", base)[0].strip()
            locations = class_locations.get(base_name, [])
            # 同名类无法唯一定位时不生成猜测 import；同文件父类也不需要 import。
            if len(locations) != 1 or locations[0] == schema_name:
                continue
            statement = f"from {locations[0]} import {_safe_name(base_name)}"
            if statement not in imports:
                imports.append(statement)
    return imports


def _update_translation_state(item: dict, partial: list[str], model: str) -> None:
    """写入后续 fragment 翻译依赖的 partial schema 状态。

    字段名尽量与 AlphaTrans 原版保持一致。任务明确不迁移 GraalVM，因此不增加
    ``graal_validation``；其余生成状态均初始化为 pending 或空列表。
    """
    # partial_translation 保存当前签名和 pass，下一阶段只需替换方法体。
    item["partial_translation"] = partial
    item["translation"] = []
    # 生成实现、语法验证等状态在 fragment 阶段开始前均为 pending。
    item["translation_status"] = "pending"
    item["syntactic_validation"] = "pending"
    item["elapsed_time"] = 0
    item["generation_timestamp"] = 0
    item["model_name"] = model
    item["include_implementation"] = True


def _ensure_packages(root: Path, parent: Path) -> None:
    """为骨架目录逐级建立 ``__init__.py``。

    这样 schema 的点分模块路径可以被 Python import，最后的包级验证也能发现
    父类 import、目录层次和循环依赖问题。
    """
    current = root
    # 每级目录写入 __init__.py，使 dotted schema 路径可以作为 Python 包导入。
    (current / "__init__.py").touch()
    for part in parent.relative_to(root).parts:
        current /= part
        current.mkdir(exist_ok=True)
        (current / "__init__.py").touch()


def create_skeleton(project: str, model: str, prompt_type: str, temperature: str) -> tuple[int, int]:
    """生成整个 ArkTS 项目的 Python 骨架并验证。

    Args:
        project: ArkTS 项目名，例如 ``RdbPlus``。
        model: 类型翻译使用的模型名，同时用于原版兼容的输出目录和状态字段。
        prompt_type: 后续 fragment 翻译类型，当前默认 ``body``。
        temperature: 后续生成温度，当前默认 ``0.0``；骨架阶段不调用模型。

    Returns:
        ``(生成的源模块数, 验证错误数)``。错误包括语法、Black 和包导入错误。
    """
    # 输入一：Phase B 的文件级 ArkTS schema。
    schema_dir = DATA / "schemas" / project
    # 输入二：Phase C 已确认的 ArkTS -> Python 类型映射。
    type_map = json.loads((DATA / "type_resolution" / project / "s1_output.json").read_text(encoding="utf-8"))
    # 输入三：依赖生成步骤输出的依赖优先遍历顺序。
    traversal_path = DATA / "dependencies" / project / "traversal.json"
    traversal = json.loads(traversal_path.read_text(encoding="utf-8"))
    order = {node: index for index, node in enumerate(traversal.values())}
    schemas = [(path.stem, json.loads(path.read_text(encoding="utf-8"))) for path in schema_dir.glob("*.json")]
    # 一个 schema 可能包含多个类，取其中最早的遍历序号作为文件生成顺序。
    schemas.sort(key=lambda item: min((order.get(f"{item[0]}:{name}", 10**9) for name in item[1].get("classes", {}) or ["<module>"]), default=10**9))
    project_classes = {name for _, schema in schemas for name in schema.get("classes", {})}
    class_locations: dict[str, list[str]] = {}
    for schema_name, schema in schemas:
        for class_name in schema.get("classes", {}):
            class_locations.setdefault(class_name, []).append(schema_name)

    # 原版分别保存可执行 Python 骨架和带翻译状态的 partial schema。
    skeleton_root = DATA / "skeletons" / project
    translation_root = DATA / "schemas" / "translations" / model / prompt_type / temperature / project
    skeleton_root.mkdir(parents=True, exist_ok=True)
    translation_root.mkdir(parents=True, exist_ok=True)
    generated = 0
    errors = 0

    for schema_name, schema in schemas:
        # 深拷贝保证 Phase B 原始 schema 不会被新增的 Python 状态字段修改。
        target_schema = copy.deepcopy(schema)
        imports = ["from __future__ import annotations", "from abc import ABC, abstractmethod", "from enum import Enum, auto", "from typing import *"]
        imports.extend(_base_imports(schema_name, schema, class_locations))
        lines = imports + [""]
        # python_imports 会被下一阶段重组器读取，因此与实际骨架文件保持一致。
        target_schema["python_imports"] = imports.copy()

        # 一个 ArkTS 文件可能包含多个 class/interface/struct/enum，依次写入同一模块。
        for class_name, class_data in schema.get("classes", {}).items():
            rendered, declaration = _render_class(class_name, class_data, type_map, project_classes)
            lines.extend(rendered + [""])
            target_class = target_schema["classes"][class_name]
            # 原版在 schema 中保存 Python class 声明，fragment 重组时无需重新推导继承。
            target_class["python_class_declaration"] = declaration + "\n"
            # 字段先保存类型注解骨架，字段初始化逻辑在 fragment 翻译阶段补全。
            for key, field in target_class.get("fields", {}).items():
                annotation = _python_type(_source_type(field, "types"), type_map)
                _update_translation_state(field, [f"    {_safe_name(key)}: {annotation} = None\n"], model)
            # callable 的 partial_translation 保存签名和 pass，不包含 ArkTS 方法体。
            for key, method in target_class.get("methods", {}).items():
                partial = [f"    {line}\n" for line in _render_callable(key, method, type_map, True, bool(class_data.get("is_abstract") or class_data.get("is_interface")))]
                _update_translation_state(method, partial, model)

        # ArkTS 允许类外顶层函数，原版 Java 流程没有这一分支。
        for key, function in schema.get("functions", {}).items():
            rendered = _render_callable(key, function, type_map, False, False)
            lines.extend(rendered + [""])
            _update_translation_state(target_schema["functions"][key], [f"{line}\n" for line in rendered], model)

        # 汇总当前 ArkTS 文件对应的完整 Python 模块。
        source = "\n".join(lines).rstrip() + "\n"
        relative_path = _module_path(schema_name)
        output_path = skeleton_root / relative_path
        # 只在 arkts_data/skeletons 下创建目标文件，不修改裁剪后的 ArkTS 项目。
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_packages(skeleton_root, output_path.parent)
        output_path.write_text(source, encoding="utf-8")

        # ast.parse 与 compile 均不执行方法体，用于定位文件级 Python 语法错误。
        try:
            ast.parse(source, filename=str(output_path))
            compile(source, str(output_path), "exec")
        except SyntaxError as exc:
            errors += 1
            print(f"SYNTAX_ERROR={output_path}:{exc.lineno}:{exc.msg}")

        # partial schema 保留原 schema 的 callable 标识，供下一阶段按 fragment 精确回写。
        partial_path = translation_root / f"{schema_name}_python_partial.json"
        partial_path.write_text(json.dumps(target_schema, ensure_ascii=False, indent=4), encoding="utf-8")
        generated += 1

    # 与原版一样使用 Black 格式化；环境未安装 Black 时仍保留 compile 验证结果。
    # Black 同时承担格式规范化和额外的语法解析检查，与 AlphaTrans 原版一致。
    black = subprocess.run(
        [sys.executable, "-m", "black", "--quiet", str(skeleton_root)],
        capture_output=True,
        text=True,
    )
    if black.returncode not in {0, 1} or (black.returncode == 1 and "No module named black" not in black.stderr):
        print(f"BLACK_ERROR={black.stderr.strip()}")
        errors += 1

    # 原版会执行每个骨架文件；这里按 Python 包导入，检查继承 import 和模块结构。
    environment = dict(os.environ)
    previous_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(skeleton_root) + (os.pathsep + previous_path if previous_path else "")
    for path in sorted(skeleton_root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        module = ".".join(path.relative_to(skeleton_root).with_suffix("").parts)
        # 每个模块单独启动解释器，避免前一个模块的 sys.modules 状态掩盖导入问题。
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode:
            errors += 1
            print(f"IMPORT_ERROR={module}:{result.stderr.strip().splitlines()[-1]}")
    return generated, errors


def main() -> None:
    """解析命令行参数，执行骨架生成，并用非零退出码报告验证失败。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("model")
    parser.add_argument("prompt_type", nargs="?", default="body")
    parser.add_argument("temperature", nargs="?", default="0.0")
    args = parser.parse_args()
    generated, errors = create_skeleton(args.project, args.model, args.prompt_type, args.temperature)
    print(f"SKELETONS={generated} SYNTAX_ERRORS={errors}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
