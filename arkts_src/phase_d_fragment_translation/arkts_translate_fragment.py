"""执行 ArkTS fragment 组合式翻译、局部验证和失败重试。"""
from __future__ import annotations

import argparse
import datetime
import json
import time
from pathlib import Path

import yaml
from openai import OpenAI

from arkts_src.phase_d_fragment_translation.arkts_get_fragment_traversal import get_fragment_traversal
from arkts_src.phase_d_fragment_translation.arkts_prompt_generator import ArkTSPromptGenerator
from arkts_src.phase_d_fragment_translation.arkts_syntactic_validation import validate_generation
from arkts_src.phase_e_validation_recompose.arkts_recompose import recompose_project
from arkts_src.phase_e_validation_recompose.arkts_validate_project import (
    validate_project,
    write_validation_report,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def _fragment_item(schema: dict, fragment: dict) -> dict:
    """返回 fragment 在 partial schema 中对应的可修改节点。"""
    if fragment["fragment_type"] == "function":
        return schema["functions"][fragment["fragment_name"]]
    class_data = schema["classes"][fragment["class_name"]]
    collection = "fields" if fragment["fragment_type"] == "field" else "methods"
    return class_data[collection][fragment["fragment_name"]]


def _load_schema(translation_dir: Path, fragment: dict) -> tuple[Path, dict]:
    """读取 fragment 所在 partial schema。"""
    path = translation_dir / f"{fragment['schema_name']}_python_partial.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _save_schema(path: Path, schema: dict) -> None:
    """保存更新后的 partial schema。"""
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=4), encoding="utf-8")


def _client(model_name: str) -> tuple[OpenAI, dict]:
    """沿用 AlphaTrans 模型配置，并增加显式超时和自动重试。"""
    models = yaml.safe_load((ROOT / "configs" / "model_configs.yaml").read_text())["models"]
    info = models[model_name]
    options = {
        key: value
        for key, value in info.items()
        if key in {"api_key", "base_url", "default_headers"}
    }
    options.update({"timeout": 180.0, "max_retries": 3})
    return OpenAI(**options), info


def _prompt_model(
    client: OpenAI,
    model_info: dict,
    model_name: str,
    prompt: str,
    temperature: float,
) -> str:
    """调用 OpenAI 兼容接口并返回最终文本。"""
    request = {
        "model": model_info["model_id"],
        "messages": [
            {"role": "system", "content": "You translate ArkTS repository fragments into Python."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": min(int(model_info.get("max_new_tokens", 8192)), 8192),
        "stream": False,
    }
    # DeepSeek V4 使用低强度思考，避免推理内容耗尽 fragment 输出预算。
    if model_name.startswith("deepseek-v4"):
        request["reasoning_effort"] = "low"
        request["extra_body"] = {"thinking": {"type": "enabled"}}
    response = client.chat.completions.create(**request)
    if not response.choices:
        raise RuntimeError("model response has no choices")
    content = response.choices[0].message.content or ""
    if not content.strip():
        reason = response.choices[0].finish_reason
        raise RuntimeError(f"model response content is empty; finish_reason={reason}")
    return content


def _set_result(
    item: dict,
    translation: list[str],
    status: str,
    syntactic: str,
    composition: str,
    elapsed: float,
    feedback: str = "",
) -> None:
    """更新 fragment 状态；不写入任务明确排除的 GraalVM 字段。"""
    item["translation"] = translation
    item["translation_status"] = status
    item["syntactic_validation"] = syntactic
    item["composition_validation"] = composition
    item["validation_feedback"] = feedback
    item["elapsed_time"] = elapsed
    item["generation_timestamp"] = datetime.datetime.now().isoformat()


def _feedback(report: dict) -> str:
    """压缩结构化项目错误，作为下一次 LLM 修复输入。"""
    return json.dumps(report, ensure_ascii=False, indent=2)[:12000]


def _fragment_label(fragment: dict) -> str:
    """返回适合进度日志显示的 fragment 限定名。"""
    return "|".join(
        [fragment["schema_name"], fragment["class_name"], fragment["fragment_name"]]
    )


def _short_error(message: str, limit: int = 240) -> str:
    """把多行错误压缩成单行，避免进度日志被完整堆栈淹没。"""
    return " ".join(message.split())[:limit]


def translate_one(
    fragment: dict,
    translation_dir: Path,
    project: str,
    model_name: str,
    prompt_type: str,
    temperature_text: str,
    client: OpenAI,
    model_info: dict,
    attempts: int,
    initial_feedback: str = "",
) -> bool:
    """翻译一个 fragment，并在语法或组合失败时携带反馈重试。"""
    start = time.time()
    label = _fragment_label(fragment)
    feedback = initial_feedback
    schema_path, schema = _load_schema(translation_dir, fragment)
    item = _fragment_item(schema, fragment)
    # 支持断点续跑：已有可解析翻译且没有新的反馈时直接跳过，避免仓库级
    # 翻译中断后重复消耗模型调用。
    if (
        item.get("translation_status") == "attempted"
        and item.get("syntactic_validation") == "parseable"
        and not initial_feedback
    ):
        print(f"FRAGMENT={label} STATUS=skipped", flush=True)
        return True

    for attempt in range(1, attempts + 1):
        try:
            print(
                f"FRAGMENT={label} ATTEMPT={attempt}/{attempts} STATUS=requesting",
                flush=True,
            )
            # 每轮根据最新 schema 重建 prompt，使当前 fragment 能引用已完成的
            # 字段和被调用函数；feedback 保存上一轮验证错误。
            prompt = ArkTSPromptGenerator(translation_dir, fragment, feedback).generate()
            generation = _prompt_model(
                client, model_info, model_name, prompt, float(temperature_text)
            )
            ok, translated_lines, syntax_feedback = validate_generation(
                generation,
                fragment["fragment_type"],
                item.get("partial_translation", []),
                fragment["class_name"] != "<module>",
            )
            # 先验证函数 AST、名称和缩进；未通过时不写 partial schema，只把
            # 具体错误加入下一轮 prompt。
            if not ok:
                feedback = syntax_feedback
                print(
                    f"FRAGMENT={label} ATTEMPT={attempt}/{attempts} "
                    f"STATUS=syntax_retry ERROR={_short_error(feedback)}",
                    flush=True,
                )
                continue

            _set_result(
                item,
                translated_lines,
                "attempted",
                "parseable",
                "pending",
                time.time() - start,
            )
            _save_schema(schema_path, schema)

            # 每个 fragment 写回后重组一次，及时发现 import、继承和模块执行错误。
            print(f"FRAGMENT={label} STATUS=validating", flush=True)
            project_root = recompose_project(project, model_name, prompt_type, temperature_text)
            report = validate_project(project_root, run_tests=False)
            if report["success"]:
                schema_path, schema = _load_schema(translation_dir, fragment)
                item = _fragment_item(schema, fragment)
                _set_result(
                    item,
                    translated_lines,
                    "attempted",
                    "parseable",
                    "passed",
                    time.time() - start,
                )
                _save_schema(schema_path, schema)
                print(
                    f"FRAGMENT={label} STATUS=passed ELAPSED={time.time() - start:.1f}s",
                    flush=True,
                )
                return True
            feedback = _feedback(report)
            print(
                f"FRAGMENT={label} ATTEMPT={attempt}/{attempts} "
                f"STATUS=composition_retry ERROR={_short_error(feedback)}",
                flush=True,
            )
        except Exception as exc:
            feedback = str(exc)
            print(
                f"FRAGMENT={label} ATTEMPT={attempt}/{attempts} "
                f"STATUS=request_retry ERROR={_short_error(feedback)}",
                flush=True,
            )

    # 全部尝试失败后记录最后错误。translation 留空，重组器会回退到 C 阶段
    # 的 partial_translation，使项目仍保留可检查的 Python 骨架。
    schema_path, schema = _load_schema(translation_dir, fragment)
    item = _fragment_item(schema, fragment)
    _set_result(
        item,
        [],
        "failed",
        "non-parseable",
        "failed",
        time.time() - start,
        feedback,
    )
    _save_schema(schema_path, schema)
    print(
        f"FRAGMENT={label} STATUS=failed ELAPSED={time.time() - start:.1f}s "
        f"ERROR={_short_error(feedback)}",
        flush=True,
    )
    return False


def _affected_fragments(report: dict, traversal: list[dict]) -> list[dict]:
    """根据语法、导入或 pytest 反馈选择需要再次翻译的 fragment。"""
    modules: set[str] = set()
    for error in report.get("syntax_errors", []):
        modules.add(error["file"].removesuffix(".py").replace("/", "."))
    for error in report.get("import_errors", []):
        modules.add(error["module"])
    if modules:
        return [item for item in traversal if item["schema_name"] in modules]
    if report.get("test", {}).get("status") == "failed":
        return [item for item in traversal if item.get("is_test")]
    return []


def translate_project(
    project: str,
    temperature: str,
    model_name: str,
    prompt_type: str = "body",
    attempts: int = 3,
    validation_rounds: int = 1,
) -> dict:
    """按依赖顺序翻译，并在最终验证失败后进行有限迭代修正。"""
    translation_dir = (
        DATA / "schemas" / "translations" / model_name / prompt_type / temperature / project
    )
    call_graph_path = DATA / "call_graphs" / project / "call_graph.json"
    # traversal 合并字段顺序、项目内调用依赖和测试标记；它决定 LLM 调用顺序，
    # 但不改变 partial schema 中 fragment 的身份和源码范围。
    traversal = get_fragment_traversal(call_graph_path, translation_dir)
    print(
        f"TRANSLATION_START PROJECT={project} MODEL={model_name} "
        f"FRAGMENTS={len(traversal)}",
        flush=True,
    )
    client, model_info = _client(model_name)

    # 第一遍遍历所有 fragment。单个 fragment 的重试次数由 attempts 控制，
    # 一个 fragment 失败不会阻止后续 fragment 保存各自结果。
    completed = 0
    for index, fragment in enumerate(traversal, start=1):
        print(
            f"PROGRESS={index}/{len(traversal)} FRAGMENT={_fragment_label(fragment)}",
            flush=True,
        )
        if translate_one(
            fragment,
            translation_dir,
            project,
            model_name,
            prompt_type,
            temperature,
            client,
            model_info,
            attempts,
        ):
            completed += 1

    print(
        f"TRANSLATION_PASS COMPLETED={completed} FAILED={len(traversal) - completed}",
        flush=True,
    )

    # 首轮结束后重组完整项目并运行 pytest/pytest-cov。这里得到的是目标 Python
    # 的运行结果，不是 ArkTS 源项目的运行时覆盖率。
    print("PROJECT_VALIDATION STATUS=running", flush=True)
    project_root = recompose_project(project, model_name, prompt_type, temperature)
    report = validate_project(project_root, run_tests=True)
    print(
        f"PROJECT_VALIDATION STATUS={'passed' if report['success'] else 'failed'} "
        f"TEST={report['test']['status']}",
        flush=True,
    )
    for validation_round in range(1, validation_rounds + 1):
        if report["success"]:
            break
        affected = _affected_fragments(report, traversal)
        # 只重试能够由错误模块或失败测试定位到的 fragment，避免每轮重新请求
        # 整个仓库。项目级报告会作为统一 feedback 加入修复 prompt。
        if not affected:
            print("ITERATION STATUS=no_affected_fragments", flush=True)
            break
        print(
            f"ITERATION={validation_round}/{validation_rounds} "
            f"AFFECTED={len(affected)}",
            flush=True,
        )
        validation_feedback = _feedback(report)
        for fragment in affected:
            translate_one(
                fragment,
                translation_dir,
                project,
                model_name,
                prompt_type,
                temperature,
                client,
                model_info,
                1,
                validation_feedback,
            )
        project_root = recompose_project(project, model_name, prompt_type, temperature)
        report = validate_project(project_root, run_tests=True)
        print(
            f"ITERATION={validation_round}/{validation_rounds} "
            f"STATUS={'passed' if report['success'] else 'failed'}",
            flush=True,
        )

    # pytest 通过不代表所有 fragment 已实现；回退为 pass 的项仍判为未完成。
    incomplete: list[str] = []
    for fragment in traversal:
        _, schema = _load_schema(translation_dir, fragment)
        item = _fragment_item(schema, fragment)
        if not (
            item.get("translation_status") == "attempted"
            and item.get("syntactic_validation") == "parseable"
        ):
            incomplete.append(_fragment_label(fragment))
    report["fragment_translation"] = {
        "total": len(traversal),
        "completed": len(traversal) - len(incomplete),
        "incomplete": incomplete,
    }
    if incomplete:
        report["success"] = False
    print(
        f"FRAGMENT_SUMMARY COMPLETED={len(traversal) - len(incomplete)} "
        f"INCOMPLETE={len(incomplete)}",
        flush=True,
    )
    write_validation_report(project_root, report)
    return report


def main() -> None:
    """执行与原版 translate_fragment.sh 对应的组合式翻译主循环。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("temperature")
    parser.add_argument("model")
    parser.add_argument("--prompt-type", default="body")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--validation-rounds", type=int, default=1)
    args = parser.parse_args()
    report = translate_project(
        args.project,
        args.temperature,
        args.model,
        args.prompt_type,
        args.attempts,
        args.validation_rounds,
    )
    print(f"VALID={report['success']}")
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
