#!/usr/bin/env python3
"""Generate README, index.html, and catalog.json from files under books/."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape, unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOKS_DIR = ROOT / "books"
README_PATH = ROOT / "README.md"
INDEX_PATH = ROOT / "index.html"
CATALOG_PATH = ROOT / "catalog.json"
SUPPORTED_SUFFIXES = {".html", ".htm", ".pdf"}

CATEGORY_LABELS = {
    "economics": "经济学",
    "econ": "经济学",
    "finance": "金融学",
    "statistics": "统计学",
    "math": "数学",
    "literature": "文学",
    "history": "历史学",
    "politics": "政治学",
    "science": "科学",
    "other": "其他",
}

GROUP_TITLE_OVERRIDES = {
    "RCK 模型_交互课程讲义": "RCK ��型数值方法与宏观校准",
    "RCK 模型数值方法与宏观校准_图解课程讲义": "RCK 模型数值方法与宏观校准",
    "从偏好到福利：MWG 需求理论交互教材": "MWG 需求理论",
    "教育如何成为信号：Spence 1973 劳动市场信号深度解读": "Spence 劳动市场信号",
    "看得见的数值分析 · 交互动画书": "看得见的数值分析",
    "博弈论与市场设计_第8章_交互读本": "博弈论与市场设计 第8章",
}


def slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def document_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".pdf":
        return "pdf"
    return "file"


def human_kind(kind: str) -> str:
    if kind == "html":
        return "HTML"
    if kind == "pdf":
        return "PDF"
    return "FILE"


def infer_category(path: Path) -> str:
    rel_parts = path.relative_to(BOOKS_DIR).parts
    if len(rel_parts) >= 2:
        return rel_parts[0]
    return "other"


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category.lower(), category or "其他").replace("-", " ")


def normalize_name(path: Path) -> str:
    value = path.stem.replace("_", " ")
    value = re.sub(r"[-_]+", " ", value)
    return re.sub(r"\s+", " ", value).strip() or path.name


def extract_title(path: Path) -> str:
    if document_kind(path) == "pdf":
        return normalize_name(path)

    text = read_text(path)
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if match:
        title = unescape(re.sub(r"<.*?>", "", match.group(1)))
        title = re.sub(r"\s+", " ", title).strip()
        if title:
            return title
    return normalize_name(path)


def extract_description(path: Path) -> str:
    if document_kind(path) == "pdf":
        return "PDF 文档"

    text = read_text(path)
    patterns = [
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            description = unescape(re.sub(r"\s+", " ", match.group(1))).strip()
            if description:
                return description

    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", text, flags=re.I | re.S)
    for paragraph in paragraphs:
        cleaned = re.sub(r"<.*?>", "", paragraph)
        cleaned = unescape(re.sub(r"\s+", " ", cleaned)).strip()
        if cleaned:
            return cleaned[:160]

    return "知识文档"


def group_title_for(title: str) -> str:
    value = title.strip()
    for override_key, override_value in GROUP_TITLE_OVERRIDES.items():
        if override_key in value or value.startswith(override_key):
            return override_value

    cleaned = re.sub(r"\s*[:：].*$", "", value)
    cleaned = re.sub(r"\s*[—–-].*$", "", cleaned)
    cleaned = re.sub(r"\s*\|\s*.*$", "", cleaned)
    cleaned = re.sub(r"\s*（.*?）\s*$", "", cleaned)
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if "RCK" in value and "模型" in value:
        return "RCK 模型数值方法与宏观校准"
    if "Spence" in value or "劳动市场信号" in value:
        return "Spence 劳动市场信号"
    if "MWG" in value or "需求理论" in value:
        return "MWG 需求理论"
    if "数值分析" in value:
        return "看得见的数值分析"
    if "博弈论与市场设计" in value:
        return "博弈论与市场设计 第8章"

    if cleaned:
        return cleaned
    return value


def collect_books() -> list[dict]:
    if not BOOKS_DIR.exists():
        return []

    entries: list[dict] = []
    for path in sorted(BOOKS_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if path.name.lower() == "index.html":
            continue

        kind = document_kind(path)
        relative_path = path.relative_to(ROOT).as_posix()
        title = extract_title(path)
        category = infer_category(path)

        entries.append(
            {
                "id": slugify(f"{title}-{kind}"),
                "title": title,
                "group": group_title_for(title),
                "category": category,
                "category_label": category_label(category),
                "path": relative_path,
                "format": kind,
                "kind": human_kind(kind),
                "language": "zh-CN",
                "description": extract_description(path),
                "updated": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d"),
            }
        )

    return sorted(entries, key=lambda item: (item["category"], item["group"], item["title"]))


def group_books(entries: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for item in entries:
        key = f"{item['category']}::{item['group']}"
        group = grouped.setdefault(
            key,
            {
                "category": item["category"],
                "category_label": item["category_label"],
                "title": item["group"],
                "items": [],
                "description": item["description"],
            },
        )
        group["items"].append(item)
    return list(grouped.values())


def render_readme(entries: list[dict]) -> str:
    grouped = group_books(entries)
    if not grouped:
        return (
            "# 知识书库 · Knowledge Library\n\n"
            "本仓库用于归档已确认的知识类 HTML 书籍、交互教材与学习资料，便于离线阅读和长期保存。\n\n"
            "## 书籍目录\n\n"
            "当前尚无已确认的书籍文件。\n\n"
            "## 如何阅读\n\n"
            "- 直接打开 HTML 文件可在浏览器中阅读；PDF 文件可用浏览器或 PDF 阅读器打开。\n"
            "- 公式、字体和交互图均已内嵌，可离线使用。\n"
            "- 若需要查看源码或历史版本，可在 GitHub 上查看对应文件记录。\n"
            "- 也可以直接打开仓库根目录的 `index.html`，从书目页面浏览全部内容。\n\n"
            "## 归档规则\n\n"
            "- HTML / PDF 书籍统一保存到 `books/<学科>/`。\n"
            "- 修改已有成果时优先更新原文件路径，保留版本历史。\n"
            "- 上传或修订后，应同步更新 `catalog.json`、`index.html` 和相关目录说明。\n"
            "- 保留教材原始来源说明、适用条件和字体许可。\n"
            "- 仅提交已确认的最终成果，避免上传无关中间文件或临时数据。\n"
        )

    rows = [
        "# 知识书库 · Knowledge Library",
        "",
        "本仓库用于归档已确认的知识类 HTML 书籍、交互教材、PDF 文档与学习资料，便于离线阅读和长期保存。",
        "",
        "## 书籍目录",
        "",
        "| 分类 | 主题 | 文件 | 内容 |",
        "| --- | --- | --- | --- |",
    ]

    for group in grouped:
        category = escape(group["category_label"])
        title = escape(group["title"])
        links = " / ".join(
            f"[{escape(item['kind'])} · {escape(item['title'])}]({item['path']})"
            for item in group["items"]
        )
        desc = escape(group["description"]) if group["items"] else "知识文档"
        rows.append(f"| {category} | {title} | {links} | {desc} |")

    rows.extend(
        [
            "",
            "## 如何阅读",
            "",
            "- 直接打开 HTML 文件可在浏览器中阅读；PDF 文件可使用浏览器或本地 PDF 阅读器打开。",
            "- 公式、字体和交互图均已内嵌，可离线使用。",
            "- 若需要查看源码或历史版本，可在 GitHub 上查看对应文件记录。",
            "- 也可以直接打开仓库根目录的 `index.html`，从书目页面浏览全部内容。",
            "",
            "## 归档规则",
            "",
            "- HTML / PDF 书籍统一保存到 `books/<学科>/`。",
            "- 修改已有成果时优先更新原文件路径，保留版本历史。",
            "- 上传或修订后，应同步更新 `catalog.json`、`index.html` 和相关目录说明。",
            "- 保留教材原始来源说明、适用条件和字体许可。",
            "- 仅提交已确认的最终成果，避免上传无关中间文件或临时数据。",
            "",
            "## 说明",
            "",
            "本仓库面向知识沉淀与资料归档，适合在本地或 GitHub 上长期保管和检索。",
            "",
        ]
    )
    return "\n".join(rows) + "\n"


def render_index_html(entries: list[dict]) -> str:
    grouped = group_books(entries)
    sections = []
    for group in grouped:
        links = []
        for item in group["items"]:
            label = f"{item['kind']} · {item['title']}"
            links.append(f"<a href=\"{escape(item['path'], quote=True)}\">{escape(label)}</a>")
        title = escape(group["title"])
        desc = escape(group["items"][0]["description"]) if group["items"] else "知识文档"
        meta = " / ".join(escape(item["updated"]) for item in group["items"])
        sections.append(
            "<article class=\"group\">"
            f"<small>{escape(group['category_label'])} · {escape(group['category'].upper())}</small>"
            f"<h2>{title}</h2>"
            f"<div class=\"file-list\">{''.join(f'<div class=\"file-link\">{link}</div>' for link in links)}</div>"
            f"<p>{desc}</p>"
            f"<div class='meta'>更新于 {meta}</div>"
            "</article>"
        )

    html = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>知识书库 · Knowledge Library</title>
<style>
:root{{color-scheme:light dark;--bg:#fbfaf6;--fg:#193238;--muted:#627675;--line:#d6dfd9;--accent:#006c69;--card:#fff;--badge:#edf4f2}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:17px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:48px 22px 80px}}
small{{display:block;color:var(--muted);letter-spacing:.14em;text-transform:uppercase;margin-bottom:12px}}
h1{{margin:0 0 8px;font-size:clamp(2rem,3vw,3rem);line-height:1.2}}
p{{margin:0}}
.group{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-top:18px;box-shadow:0 6px 22px rgba(25,50,56,.04)}}
.group h2{{margin:0 0 12px;font-size:clamp(1.25rem,2.2vw,1.8rem);line-height:1.4}}
.group p{{color:var(--fg);opacity:.92}}
.file-list{{display:flex;flex-wrap:wrap;gap:10px 14px;margin:0 0 14px}}
.file-link{{padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:var(--badge)}}
.file-link a{{color:var(--accent);text-decoration:none;font-weight:600}}
.file-link a:hover{{text-decoration:underline}}
.meta{{margin-top:10px;font-size:.84rem;color:var(--muted)}}
footer{{margin-top:28px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:.95rem}}
@media (prefers-color-scheme: dark) {{
  :root{{--bg:#172329;--fg:#edf7f5;--muted:#afc4c0;--line:#2e4043;--accent:#67d9d4;--card:#1c2b2d;--badge:#20363a}}
  body{{background:var(--bg);color:var(--fg)}}
  .group{{background:var(--card);border-color:var(--line)}}
}}
</style>
</head>
<body>
<main>
  <small>KNOWLEDGE LIBRARY</small>
  <h1>知识书库</h1>
  <p>在这里保存知识，展开推导，也让图像帮助理解。</p>
  {''.join(sections)}
  <footer>下载仓库后，在浏览器中打开本页即可浏览书目。教材支持离线阅读。</footer>
</main>
</body>
</html>
'''
    return html


def main() -> None:
    entries = collect_books()
    grouped = group_books(entries)
    CATALOG_PATH.write_text(
        json.dumps({"title": "知识书库", "groups": grouped}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(render_readme(entries), encoding="utf-8")
    INDEX_PATH.write_text(render_index_html(entries), encoding="utf-8")
    print(f"Updated catalog with {len(grouped)} grouped topics.")


if __name__ == "__main__":
    main()
