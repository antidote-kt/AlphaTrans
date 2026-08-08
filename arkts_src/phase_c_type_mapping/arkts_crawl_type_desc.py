"""查询未映射 ArkTS 类型的官方文档。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "arkts_data"


def _imports(project: str) -> dict[str, str]:
    """建立导入符号到模块名的索引。"""
    result = {}
    for schema in (DATA / "schemas" / project).glob("*.json"):
        try:
            data = json.loads(schema.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for item in data.get("imports", {}).values():
            module = item.get("module", "")  # 用模块名缩小官方文档搜索范围。
            for name in re.findall(r"\b[A-Za-z_$][\w$]*\b", " ".join(item.get("body", []))):
                result.setdefault(name, module)
    return result


def _web_description(type_name: str, module: str) -> tuple[str, str, str]:
    """查询官方文档并提取正文摘要。"""
    query = quote(f"site:developer.huawei.com/consumer/cn/doc/harmonyos-references {module} {type_name}")  # 限定官方文档域名。
    headers = {"User-Agent": "AlphaTrans-ArkTS-TypeCrawler/1.0"}  # 设置普通浏览器标识。
    try:
        search = requests.get(f"https://www.bing.com/search?q={query}", headers=headers, timeout=15)
        search.raise_for_status()
    except requests.RequestException:
        return "", "", ""  # 网络失败时保留原版空描述。
    soup = BeautifulSoup(search.text, "html.parser")
    links = [a.get("href", "") for a in soup.select("a[href]")]
    official_links = [link for link in links if "developer.huawei.com/consumer/cn/doc/" in link]  # 丢弃非官方结果。
    for link in official_links[:5]:
        try:
            page = requests.get(link, headers=headers, timeout=15)
            page.raise_for_status()
        except requests.RequestException:
            continue
        page_soup = BeautifulSoup(page.text, "html.parser")
        main = page_soup.select_one("main") or page_soup.select_one("article") or page_soup.body
        text = " ".join(main.stripped_strings) if main else ""
        if text:
            summary = re.split(r"[。.!！？]", text, maxsplit=1)[0].strip()
            return link, text, summary
    return "", "", ""


def describe(project: str) -> dict:
    """查询空映射类型并写出原版三字段描述。"""
    base = DATA / "type_resolution" / project
    source = json.loads((base / "s1_input.json").read_text(encoding="utf-8"))
    # import 只提供搜索上下文，mapped 才是筛选条件。
    imports = _imports(project)
    descriptions = {}
    for type_name, mapped in source.items():
        if mapped != "":
            continue  # 项目内已有映射，不查文档。
        if type_name.startswith("(") and "=>" in type_name:
            continue  # 函数类型由规则映射处理。
        module = imports.get(type_name.split(".")[0], "")  # 获取搜索用模块名。
        link, text, summary = _web_description(type_name, module)
        descriptions[type_name] = {"link": link, "text": text, "summarized_text": summary}
    (base / "type_description.json").write_text(json.dumps(descriptions, ensure_ascii=False, indent=4), encoding="utf-8")
    return descriptions


def main() -> None:
    """执行命令行官方文档查询。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    args = parser.parse_args()
    result = describe(args.project)
    print(f"DESCRIPTIONS={len(result)} FOUND={sum(bool(item['text']) for item in result.values())}")


if __name__ == "__main__":
    main()
