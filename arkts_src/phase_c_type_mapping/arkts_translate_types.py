"""调用 LLM 翻译 ArkTS 类型并生成原版兼容的映射文件。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# 保持与 AlphaTrans 相同的配置入口和全局映射文件位置。
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def _llm_translate(type_name: str, description: dict, model_name: str) -> str:
    """调用 OpenAI 兼容接口，返回单个 Python 类型表达式。

    模型配置沿用 configs/model_configs.yaml；prompt 同时提供 ArkTS
    类型描述和规则候选，要求模型只返回可嵌入 Python 签名的表达式。
    """
    import yaml
    from openai import OpenAI
    # 延迟导入，允许不配置 OpenAI 时仍运行规则映射和单元测试。
    models = yaml.safe_load((ROOT / "configs" / "model_configs.yaml").read_text())['models']
    info = models[model_name]
    client_options = {k: v for k, v in info.items() if k in {'api_key', 'base_url', 'default_headers'}}
    client_options.update({'timeout': 180.0, 'max_retries': 3})
    client = OpenAI(**client_options)
    # 候选结果只作为参考，LLM 可以结合描述修正 number、SDK 和自定义类型。
    prompt = ("Translate this ArkTS type to a Python 3.11 typing expression. "
              "Return only the expression, no Markdown. Preserve project type names.\n"
              f"ArkTS type: {type_name}\nDescription: {json.dumps(description, ensure_ascii=False)}")
    response = client.chat.completions.create(
        model=info['model_id'],
        messages=[
            {"role": "system", "content": "You translate ArkTS types to Python typing."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=2048,
        stream=False,
        reasoning_effort="low",
        extra_body={"thinking": {"type": "enabled"}},
    )
    if not response.choices:
        raise RuntimeError("model response has no choices")
    content = response.choices[0].message.content or ""
    text = content.strip().replace("`", "")
    if not text:
        raise RuntimeError("model response content is empty")
    return text.splitlines()[0].strip()


def translate(project: str, model_name: str | None = None) -> dict:
    """翻译项目类型并生成全局映射和项目元数据。

    项目内类型直接使用 schema 映射；外部类型指定 model_name 时调用 LLM，
    未指定模型或调用失败时标记 unresolved 并暂存为 Any。
    """
    base = DATA / "type_resolution" / project
    types = json.loads((base / "s1_input.json").read_text(encoding="utf-8"))
    descriptions = json.loads((base / "type_description.json").read_text(encoding="utf-8"))
    mapping = {}
    # 每个源类型只生成一条最终映射，同时在 metadata 中保留处理来源。
    for source, existing in types.items():
        # 项目内类型已有 schema 映射，直接保留，不调用 LLM。
        if existing:
            method, status, target = "schema", "mapped", existing
        elif model_name:
            try:
                target = _llm_translate(source, descriptions.get(source, {}), model_name)
                method, status = "llm", "mapped"
            except Exception as exc:
                metadata_error = str(exc)
                method, status, target = "llm", "unresolved", "Any"
        else:
            method, status, target = "llm", "unresolved", "Any"
        mapping[source] = {"translated_type": target, "description": descriptions.get(source, {}), "method": method, "status": status, "confidence": 1.0 if method == "schema" else 0.8}
        if "metadata_error" in locals():
            mapping[source]["error"] = metadata_error
            print(f"TYPE={source} METHOD={method} STATUS={status} ERROR={metadata_error}")
            del metadata_error
        else:
            print(f"TYPE={source} METHOD={method} STATUS={status} TARGET={target}")
    out = DATA / "type_resolution"
    out.mkdir(parents=True, exist_ok=True)
    # 保持 AlphaTrans 原版格式：全局表的 value 仍是 Python 类型字符串；
    # method、confidence 等 ArkTS 增补信息另存 metadata，避免影响旧读取代码。
    (out / "universal_type_map_final.json").write_text(json.dumps({k: v["translated_type"] for k, v in mapping.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / "mapping_metadata.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / "s1_output.json").write_text(json.dumps({k: v["translated_type"] for k, v in mapping.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return mapping


def main() -> None:
    """执行命令行类型翻译。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("model", nargs="?")
    args = parser.parse_args()
    result = translate(args.project, args.model)
    print(f"TRANSLATED={len(result)} MODEL={args.model or 'none'}")


if __name__ == "__main__":
    main()
