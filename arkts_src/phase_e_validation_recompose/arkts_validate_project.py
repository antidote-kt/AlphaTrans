"""验证重组 Python 项目的语法、模块导入和 pytest 执行。"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def validate_project(project_root: Path, run_tests: bool = True) -> dict:
    """返回可直接反馈给 fragment LLM 的结构化验证结果。"""
    report: dict = {
        "success": True,
        "syntax_errors": [],
        "import_errors": [],
        "test": {"status": "not-run", "output": ""},
    }
    python_files = sorted(project_root.rglob("*.py"))

    # 第一层验证只解析和编译源码，不执行模块顶层语句。
    for path in python_files:
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path))
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            report["success"] = False
            report["syntax_errors"].append(
                {
                    "file": str(path.relative_to(project_root)),
                    "line": exc.lineno,
                    "message": exc.msg,
                }
            )

    # 把重组项目根目录放入 PYTHONPATH，保证仓库内模块按真实包路径解析。
    environment = dict(os.environ)
    old_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(project_root) + (
        os.pathsep + old_path if old_path else ""
    )
    # 第二层验证为每个模块启动独立解释器，暴露缺失依赖和循环导入问题。
    for path in python_files:
        if path.name == "__init__.py":
            continue
        module = ".".join(path.relative_to(project_root).with_suffix("").parts)
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode:
            report["success"] = False
            report["import_errors"].append(
                {"module": module, "message": result.stderr.strip()}
            )

    # 只把由 ArkTS src/test 和 src/ohosTest 重组出的模块交给 pytest 收集。
    test_files = [
        path
        for path in python_files
        if "/src/test/" in path.as_posix() or "/src/ohosTest/" in path.as_posix()
    ]
    # 第三层验证执行目标 Python 测试，并把 coverage.xml 保存在重组项目根目录；
    # 该覆盖率只描述 Python 目标项目，不代表 ArkTS 源项目覆盖率。
    if run_tests and test_files:
        coverage_path = project_root / "coverage.xml"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                *[str(path) for path in test_files],
                "--cov=.",
                f"--cov-report=xml:{coverage_path}",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            env=environment,
        )
        # pytest 退出码 5 表示未收集到测试；记录状态，但不伪装为测试通过。
        if result.returncode == 0:
            report["test"] = {"status": "passed", "output": result.stdout}
        elif result.returncode == 5:
            report["test"] = {"status": "not-collected", "output": result.stdout + result.stderr}
        else:
            report["success"] = False
            report["test"] = {"status": "failed", "output": result.stdout + result.stderr}
    return report


def write_validation_report(project_root: Path, report: dict) -> Path:
    """把最终验证结果保存在重组项目根目录。"""
    output = project_root / "validation_result.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=4), encoding="utf-8")
    return output


def main() -> None:
    """执行命令行项目验证。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("model")
    parser.add_argument("prompt_type", nargs="?", default="body")
    parser.add_argument("temperature", nargs="?", default="0.0")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    project_root = (
        DATA
        / "recomposed_projects"
        / args.model
        / args.prompt_type
        / args.temperature
        / args.project
    )
    report = validate_project(project_root, run_tests=not args.skip_tests)
    output = write_validation_report(project_root, report)
    print(f"VALID={report['success']} REPORT={output}")
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
