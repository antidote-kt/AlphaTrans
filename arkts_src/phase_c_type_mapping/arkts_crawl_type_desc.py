"""使用 Playwright 查询 ArkTS 类型的官方文档搜索页。"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"
BROWSER_HELPER = Path(__file__).with_name("arkts_render_doc.js")
DOC_SEARCH = "https://developer.huawei.com/consumer/cn/doc/search?val={}&type=all"


def crawl_type(type_name: str) -> tuple[str, str, str]:
    """访问官方搜索页并返回链接、正文和摘要。"""
    search_url = DOC_SEARCH.format(quote(type_name))
    result = subprocess.run(
        ["node", str(BROWSER_HELPER), search_url, type_name],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    page = json.loads(result.stdout)
    text = page.get("resultText", "").strip()  # 只保留搜索结果区域。
    link = search_url  # 保留可复现的官方搜索链接。
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    summary = "。".join(lines[2:4]).strip() if len(lines) > 2 else ""
    return link, text, summary


def describe(project: str) -> dict:
    """为 s1_input 中所有空值类型查询官方搜索页。"""
    base = DATA / "type_resolution" / project
    source = json.loads((base / "s1_input.json").read_text(encoding="utf-8"))
    descriptions = {}
    for type_name, mapped in source.items():
        if mapped != "":
            continue
        try:
            link, text, summary = crawl_type(type_name)
            status = "found" if text else "empty_page"
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            link, text, summary = "", "", ""
            status = f"error:{type(exc).__name__}"
        descriptions[type_name] = {"link": link, "text": text, "summarized_text": summary}
        print(f"TYPE={type_name} STATUS={status}")
    (base / "type_description.json").write_text(json.dumps(descriptions, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"DESCRIPTIONS={len(descriptions)} FOUND={sum(bool(item['text']) for item in descriptions.values())}")
    return descriptions


def main() -> None:
    """运行类型文档查询。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    args = parser.parse_args()
    describe(args.project)


if __name__ == "__main__":
    main()
