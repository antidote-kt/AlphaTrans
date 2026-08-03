#!/usr/bin/env python3
"""Remove third-party dependencies from an ArkTS reduced-project copy.

The policy mirrors AlphaTrans's Java reducer: platform/test/logging facilities
and project-local modules are trusted; other imports are dependency-removal
roots. ArkTS AST ranges are used for edits and callgraph.txt is used to
propagate dependency removal to callers.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_PROJECTS = REPO_ROOT / "arkts_projects" / "original_projects"
REDUCED_PROJECTS = REPO_ROOT / "arkts_projects" / "automated_reduced_projects"
# JS 辅助程序与本文件同目录。ArkIR 能给出调用语义，但没有安全编辑源码所需的字符范围，
# 因此这里用 AST 补充类、方法和 import 在源文件中的起止位置。
AST_HELPER = Path(__file__).with_name("arkts_ast_inventory.js")
# 复用 ArkAnalyzer 自带的 ArkTS/TypeScript 解析器，避免再安装一套语法版本可能不同的解析器。
OHOS_TYPESCRIPT = (
    REPO_ROOT / "arkts_tools" / "arkanalyzer" / "node_modules" / "arkanalyzer"
    / "lib" / "node_modules" / "ohos-typescript"
)

# 按功能覆盖 AlphaTrans 原白名单；@kit.ArkData 是任务要求的额外保留项。
TRUSTED_MODULES = {
    "@kit.ArkTS",                   # java.lang / java.util / java.math
    "@kit.LocalizationKit",         # java.text / java.time
    "@kit.CoreFileKit",             # java.io / java.nio
    "@kit.NetworkKit",              # java.net
    "@ohos/hypium",                 # org.junit / org.opentest4j / junit
    "@kit.PerformanceAnalysisKit",  # org.slf4j.Logger
    "@kit.ArkData",                 # 额外纳入
}
SOURCE_SUFFIXES = {".ets", ".ts"}
IGNORED_PARTS = {".git", ".hvigor", "node_modules", "oh_modules", "build"}

# 带绑定的 import：会把名称引入当前文件，例如：
# import RdbStore from "pkg"、import { RdbStore as Store } from "pkg"、
# import * as data from "pkg"。body 用于继续提取这些本地名称并判断哪些声明使用了它们。
IMPORT_RE = re.compile(
    r"(?P<statement>^[ \t]*import(?!\s*['\"])\s+(?P<body>.*?)\s+from\s+"
    r"(?P<quote>['\"])(?P<module>.*?)(?P=quote)[ \t]*;?)",
    re.MULTILINE | re.DOTALL,
)
# 纯副作用 import：不引入任何本地名称，只要求加载模块并执行其初始化代码，例如：
# import "reflect-metadata"。因为这种语法没有“body from”，不能由 IMPORT_RE 匹配。
SIDE_EFFECT_IMPORT_RE = re.compile(
    r"(?P<statement>^[ \t]*import\s+(?P<quote>['\"])(?P<module>.*?)"
    r"(?P=quote)[ \t]*;?)",
    re.MULTILINE,
)
# AlphaTrans/JavaCG 兼容边：M:<调用方> (<调用类型>)<被调用方>。
CALLGRAPH_RE = re.compile(r"^M:(\S+) \([A-Z]\)(\S+)$")


# 收集当前阶段需要分析的源码文件。
def source_files(project_dir: Path) -> list[Path]:
    """收集实际业务和测试 ArkTS/TS 源码，排除构建产物、依赖目录及 Hvigor 脚本。"""
    return sorted(
        path for path in project_dir.rglob("*")
        if path.is_file()
        and path.suffix in SOURCE_SUFFIXES
        and path.name != "hvigorfile.ts"
        and not any(part in IGNORED_PARTS for part in path.parts)
    )


# 读取项目 manifest 中的内部模块名称。
def project_module_names(project_dir: Path) -> set[str]:
    """读取各 oh-package.json5 的 name，得到当前仓库内可直接导入的逻辑模块名。

    例如 rdbplus/oh-package.json5 中的 name=rdbplus 表示 import "rdbplus" 或
    import "rdbplus/..." 指向本仓库模块；它相当于 Java 中用 package 前缀识别内部代码，
    但不是从目录名猜测或硬编码得到的。
    """
    names: set[str] = set()
    for manifest in project_dir.rglob("oh-package.json5"):
        if any(part in IGNORED_PARTS for part in manifest.parts):
            continue
        text = manifest.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)
        if match:
            names.add(match.group(1))
    return names


# 辅助函数：处理 _sdk_roots。
def _sdk_roots() -> list[Path]:
    """尝试从环境变量和仓库目录发现已安装 HarmonyOS SDK 的根目录。"""
    candidates = [
        os.environ.get("OHOS_SDK_HOME"),
        os.environ.get("DEVECO_SDK_HOME"),
        str(REPO_ROOT.parent / "command-line-tools" / "sdk"),
    ]
    roots: list[Path] = []
    for value in candidates:
        if not value:
            continue
        path = Path(value).expanduser()
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


# 扫描已安装 SDK 并收集平台模块。
def discover_sdk_modules(roots: Iterable[Path] | None = None) -> set[str]:
    """从已安装 SDK 声明文件发现真实平台模块，如 @kit.ArkUI、@ohos.promptAction。"""
    modules: set[str] = set()
    for root in roots if roots is not None else _sdk_roots():
        for declaration in root.rglob("@*.d.ts"):
            name = declaration.name[:-5]
            if name.startswith(("@kit.", "@ohos.", "@system.")):
                modules.add(name)
        for declaration in root.rglob("@*.d.ets"):
            name = declaration.name[:-6]
            if name.startswith(("@kit.", "@ohos.", "@system.")):
                modules.add(name)
    return modules


# 提取源码中的两类 import 声明。
def extract_imports(text: str) -> list[dict[str, object]]:
    """提取带绑定 import 和纯副作用 import，并避免同一语句被两个规则重复记录。"""
    found: list[dict[str, object]] = []
    occupied: list[tuple[int, int]] = []
    for regex in (IMPORT_RE, SIDE_EFFECT_IMPORT_RE):
        for match in regex.finditer(text):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            occupied.append((match.start(), match.end()))
            found.append({
                "statement": match.group("statement").strip(),
                "body": match.groupdict().get("body", "") or "",
                "module": match.group("module"),
                "start": match.start(),
                "end": match.end(),
            })
    return sorted(found, key=lambda item: int(item["start"]))


# 根据项目、白名单和 SDK 判断模块可信性。
def is_trusted(module: str, modules: set[str], sdk_modules: set[str] | None = None) -> bool:
    """判断 import 是否属于项目内部、功能白名单或已安装 HarmonyOS SDK。

    ./ 和 ../ 是当前文件的相对路径；rdbplus 及 rdbplus/ 子路径来自项目清单 name。
    其余裸模块名只有命中显式白名单或真实 SDK 声明时才可信。
    """
    return (
        module.startswith("./")
        or module.startswith("../")
        or any(module == name or module.startswith(f"{name}/") for name in modules)
        or module in TRUSTED_MODULES
        or module in (sdk_modules or set())
    )


# 提取 import 引入的本地符号。
def imported_symbols(body: str) -> set[str]:
    """取得带绑定 import 在当前文件中可见的名称，供 AST 污染定位使用。"""
    body = re.sub(r"^type\s+", "", body.strip())
    symbols: set[str] = set()
    named = re.search(r"\{(.*?)\}", body, re.DOTALL)
    if named:
        for item in named.group(1).split(","):
            item = item.strip()
            if item:
                symbols.add(re.split(r"\s+as\s+", item)[-1].strip())
    namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", body)
    if namespace:
        symbols.add(namespace.group(1))
    prefix = body.split("{", 1)[0].split(",", 1)[0].strip()
    if prefix and not prefix.startswith("*") and re.fullmatch(r"[A-Za-z_$][\w$]*", prefix):
        symbols.add(prefix)
    return symbols


# 把文件路径转换为模块 owner。
def _module_owner(file_name: str) -> str:
    value = re.sub(r"\.(ets|ts|js|d\.ts)$", "", file_name.strip())
    value = value.replace("/src/main/ets/", "/")
    value = value.replace("/src/test/", "/test/")
    value = value.replace("/src/ohosTest/ets/", "/ohosTest/")
    value = re.sub(r"[^A-Za-z0-9_$./-]+", "_", value)
    return value.replace("/", ".").strip(".") or "module"


# 辅助函数：处理 _owner。
def _owner(file_name: str, class_name: str | None) -> str:
    module = _module_owner(file_name)
    if not class_name or class_name in {"%dflt", "@dummyClass"}:
        return module
    if class_name == module.rsplit(".", 1)[-1]:
        return module
    return f"{module}${class_name}"


# 辅助函数：处理 _declaration_key。
def _declaration_key(file_name: str, declaration: dict[str, Any]) -> str:
    name = str(declaration["name"])
    if name == "constructor":
        name = "<init>"
    return f"{_owner(file_name, declaration.get('className'))}:{name}"


# 辅助函数：处理 _signature_key。
def _signature_key(signature: str) -> str:
    return signature.split("(", 1)[0]


# 解析兼容调用图中的 caller-callee 边。
def parse_callgraph(path: Path) -> list[tuple[str, str]]:
    """读取兼容 JavaCG 文本格式的调用边，并去掉参数部分以对齐 AST 声明键。"""
    edges: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = CALLGRAPH_RE.match(line)
        if match:
            edges.append((_signature_key(match.group(1)), _signature_key(match.group(2))))
    return edges


# 调用 AST 桥接脚本获取源码声明信息。
def ast_inventory(files: list[Path]) -> list[dict[str, Any]]:
    """调用 JS/ohos-typescript AST 辅助程序，取得可安全编辑的声明范围和标识符。"""
    if not AST_HELPER.is_file() or not OHOS_TYPESCRIPT.is_dir():
        raise FileNotFoundError("ArkTS AST helper or ArkAnalyzer ohos-typescript is unavailable")
    result = subprocess.run(
        ["node", str(AST_HELPER), str(OHOS_TYPESCRIPT)],
        input=json.dumps({"files": [str(path) for path in files]}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)["files"]


# 读取各 oh-package.json5 的依赖。
def _manifest_dependencies(project_dir: Path) -> dict[Path, dict[str, str]]:
    """解析 JSON5 清单中的运行、开发和动态依赖；不能直接用标准 JSON 解析器。"""
    paths = sorted(
        path for path in project_dir.rglob("oh-package.json5")
        if not any(part in IGNORED_PARTS for part in path.parts)
    )
    if not paths:
        return {}
    completed = subprocess.run(
        ["node", str(AST_HELPER), str(OHOS_TYPESCRIPT)],
        input=json.dumps({"manifests": [str(path) for path in paths]}),
        text=True,
        capture_output=True,
        check=True,
    )
    parsed = json.loads(completed.stdout)["manifests"]
    result: dict[Path, dict[str, str]] = {}
    for path in paths:
        data = parsed.get(str(path), {})
        deps: dict[str, str] = {}
        for section in ("dependencies", "devDependencies", "dynamicDependencies"):
            value = data.get(section, {}) if isinstance(data, dict) else {}
            if isinstance(value, dict):
                deps.update({str(name): str(spec) for name, spec in value.items()})
        result[path] = deps
    return result


# 从 manifest 中删除指定依赖。
def _remove_manifest_entries(path: Path, modules: set[str]) -> int:
    text = path.read_text(encoding="utf-8")
    removed = 0
    for module in sorted(modules):
        pattern = re.compile(
            rf"(?m)^[ \t]*(['\"]){re.escape(module)}\1\s*:\s*(['\"]).*?\2\s*,?[ \t]*(?://.*)?\n?"
        )
        text, count = pattern.subn("", text)
        removed += count
    if removed:
        path.write_text(text, encoding="utf-8")
    return removed


# 按字符范围应用源码编辑。
def _apply_edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    accepted: list[tuple[int, int, str]] = []
    for start, end, replacement in sorted(edits, key=lambda item: (item[0], -item[1])):
        if any(start >= outer_start and end <= outer_end for outer_start, outer_end, _ in accepted):
            continue
        accepted.append((start, end, replacement))
    for start, end, replacement in sorted(accepted, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


# 执行依赖分类、污染传播和源码裁剪。
def reduce_project(project_name: str) -> tuple[int, int, int]:
    """分类依赖、定位第三方污染声明、沿调用图反向传播并仅编辑待裁剪副本。"""
    project_dir = REDUCED_PROJECTS / project_name
    original_dir = ORIGINAL_PROJECTS / project_name
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Reduced ArkTS project not found: {project_dir}")
    if project_dir.resolve() == original_dir.resolve():
        raise RuntimeError("Refusing to edit the original ArkTS project")
    callgraph_path = project_dir / "callgraph.txt"
    if not callgraph_path.is_file():
        raise FileNotFoundError(f"callgraph.txt not found in {project_dir}")

    # 先建立分析边界：业务/测试源码、项目模块、SDK 模块和 manifest 依赖。
    files = source_files(project_dir)
    project_modules = project_module_names(project_dir)
    sdk_modules = discover_sdk_modules()
    manifests = _manifest_dependencies(project_dir)

    trusted: set[str] = set()
    untrusted: list[str] = []
    third_party_modules: set[str] = set()
    imports_by_file: dict[Path, list[dict[str, object]]] = {}
    symbols_by_file: dict[Path, set[str]] = {}

    # 第一遍只分类 import，并记录不可信 import 引入的本地符号。
    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for item in extract_imports(text):
            statement = str(item["statement"])
            module = str(item["module"])
            if is_trusted(module, project_modules, sdk_modules):
                trusted.add(statement.rstrip(";"))
                continue
            third_party_modules.add(module)
            imports_by_file.setdefault(file_path, []).append(item)
            symbols_by_file.setdefault(file_path, set()).update(imported_symbols(str(item["body"])))
            relative_path = f"{project_name}/{file_path.relative_to(project_dir).as_posix()}"
            untrusted.append(json.dumps(
                {"body": statement.rstrip(";"), "path": relative_path},
                ensure_ascii=False,
                sort_keys=True,
            ))

    # manifest 依赖单独检查，因为它可能没有对应的源码 import。
    third_party_manifest_modules: dict[Path, set[str]] = {}
    for manifest, dependencies in manifests.items():
        for module, specifier in dependencies.items():
            if specifier.startswith(("file:", "./", "../")):
                continue
            if not is_trusted(module, project_modules, sdk_modules):
                third_party_modules.add(module)
                third_party_manifest_modules.setdefault(manifest, set()).add(module)
                relative_path = f"{project_name}/{manifest.relative_to(project_dir).as_posix()}"
                untrusted.append(json.dumps(
                    {"body": f"\"{module}\": \"{specifier}\"", "path": relative_path},
                    ensure_ascii=False,
                    sort_keys=True,
                ))

    removed_imports = removed_methods = removed_classes = removed_manifest = 0
    unresolved_files: set[Path] = set()
    if third_party_modules:
        # 只有确实发现候选依赖时才建立 AST inventory 和污染集合。
        inventory = ast_inventory(files)
        tainted_methods: set[str] = set()
        tainted_classes: set[str] = set()
        declarations_by_key: dict[str, tuple[Path, dict[str, Any]]] = {}
        classes_by_key: dict[str, tuple[Path, dict[str, Any]]] = {}

        # AST 标出直接使用第三方符号的声明，作为污染传播的初始集合。
        for file_info in inventory:
            file_path = Path(file_info["path"])
            relative = file_path.relative_to(project_dir).as_posix()
            symbols = symbols_by_file.get(file_path, set())
            for ark_class in file_info["classes"]:
                class_key = _owner(relative, str(ark_class["name"]))
                classes_by_key[class_key] = (file_path, ark_class)
                if symbols.intersection(ark_class["identifiers"]):
                    tainted_classes.add(class_key)
            for declaration in file_info["declarations"]:
                key = _declaration_key(relative, declaration)
                declarations_by_key[key] = (file_path, declaration)
                if symbols.intersection(declaration["identifiers"]):
                    tainted_methods.add(key)
                    if declaration.get("override") or declaration["name"] in {
                        "constructor", "beforeAll", "beforeEach", "afterEach", "afterAll"
                    }:
                        class_name = declaration.get("className")
                        if class_name:
                            tainted_classes.add(_owner(relative, str(class_name)))

        # 调用图按“callee 已污染 → caller 也污染”反向闭包传播。
        changed = True
        edges = parse_callgraph(callgraph_path)
        while changed:
            changed = False
            # 规则1：类被污染 → 类内所有方法自动污染
            for class_key in list(tainted_classes):
                for key, (_, declaration) in declarations_by_key.items():
                    if declaration.get("className") and key.startswith(f"{class_key}:") and key not in tainted_methods:
                        tainted_methods.add(key)
                        changed = True
            # 规则2：调用图反向传播：被调用者污染 → 调用者污染
            for caller, callee in edges:
                if callee in tainted_methods and caller in declarations_by_key and caller not in tainted_methods:
                    tainted_methods.add(caller)
                    changed = True
                    _, declaration = declarations_by_key[caller]
                    if declaration.get("override") or declaration["name"] == "constructor":
                        owner = caller.rsplit(":", 1)[0]
                        if owner in classes_by_key and owner not in tainted_classes:
                            tainted_classes.add(owner)

        # AST 位置转成待执行编辑；类替换为空壳，方法直接删除。
        edits_by_file: dict[Path, list[tuple[int, int, str]]] = {}
        for class_key in tainted_classes:
            if class_key in classes_by_key:
                file_path, ark_class = classes_by_key[class_key]
                replacement = ("export " if ark_class.get("exported") else "") + f"class {ark_class['name']} {{}}"
                edits_by_file.setdefault(file_path, []).append(
                    (int(ark_class["start"]), int(ark_class["end"]), replacement)
                )
                removed_classes += 1
        for key in tainted_methods:
            if key not in declarations_by_key:
                continue
            file_path, declaration = declarations_by_key[key]
            class_name = declaration.get("className")
            if class_name and _owner(file_path.relative_to(project_dir).as_posix(), str(class_name)) in tainted_classes:
                continue
            edits_by_file.setdefault(file_path, []).append(
                (int(declaration["start"]), int(declaration["end"]), "")
            )
            removed_methods += 1

        # 先模拟删除方法/类，再判断 import 是否仍被剩余源码使用。
        for file_path, items in imports_by_file.items():
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            tentative = edits_by_file.get(file_path, []).copy()
            ranges = [(start, end) for start, end, _ in tentative]
            removable_items: list[dict[str, object]] = []
            for item in items:
                symbols = imported_symbols(str(item["body"]))
                remaining = text
                for start, end in ranges:
                    remaining = remaining[:start] + " " * (end - start) + remaining[end:]
                item_start, item_end = int(item["start"]), int(item["end"])
                remaining = remaining[:item_start] + " " * (item_end - item_start) + remaining[item_end:]
                if symbols and any(re.search(rf"\b{re.escape(symbol)}\b", remaining) for symbol in symbols):
                    unresolved_files.add(file_path)
                    continue
                removable_items.append(item)
                tentative.append((int(item["start"]), int(item["end"]), ""))
            edits_by_file[file_path] = tentative
            removed_imports += len(removable_items)

        # 所有范围确认后按倒序应用，避免前面删除改变后续字符偏移。
        for file_path, edits in edits_by_file.items():
            if not edits:
                continue
            text = file_path.read_text(encoding="utf-8")
            file_path.write_text(_apply_edits(text, edits), encoding="utf-8")

        # unresolved import 不强制删除对应 manifest 依赖，避免破坏可构建性。
        unresolved_modules = {
            str(item["module"])
            for file_path in unresolved_files
            for item in imports_by_file.get(file_path, [])
        }
        for manifest, modules in third_party_manifest_modules.items():
            removed_manifest += _remove_manifest_entries(manifest, modules - unresolved_modules)

    (project_dir / "trusted.txt").write_text(
        "\n".join(sorted(trusted)) + ("\n" if trusted else ""), encoding="utf-8"
    )
    (project_dir / "untrusted.jsonl").write_text(
        "\n".join(sorted(untrusted)) + ("\n" if untrusted else ""), encoding="utf-8"
    )
    removed_total = removed_imports + removed_methods + removed_classes + removed_manifest
    print(
        f"Trusted imports: {len(trusted)}; third-party imports: {len(untrusted)}; "
        f"removed imports/methods/classes/manifest entries: "
        f"{removed_imports}/{removed_methods}/{removed_classes}/{removed_manifest}; "
        f"unresolved files: {len(unresolved_files)}."
    )
    return len(trusted), len(untrusted), removed_total


# 处理命令行并启动脚本。
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    args = parser.parse_args()
    try:
        reduce_project(args.project_name)
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
