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

    return sorted(entries, key=lambda item: (item["category"], item["title"]))


def render_readme(entries: list[dict]) -> str:
    if not entries:
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
        "| 分类 | 书籍 | 格式 | 内容 |",
        "| --- | --- | --- | --- |",
    ]

    for item in entries:
        rows.append(
            f"| {escape(item['category_label'])} | [{escape(item['title'])}]({item['path']}) | {escape(item['kind'])} | {escape(item['description'])} |"
        )

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
    cards = []
    for item in entries:
        kind = escape(item["kind"])
        cards.append(
            "<article>"
            f"<small>{escape(item['category_label'])} · {escape(item['category'].upper())}</small>"
            f"<div class='kind-badge'>{kind}</div>"
            f"<h2><a href=\"{escape(item['path'], quote=True)}\">{escape(item['title'])}</a></h2>"
            f"<p>{escape(item['description'])}</p>"
            f"<div class='meta'>更新于 {escape(item['updated'])}</div>"
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
.kind-badge{{display:inline-block;margin:0 0 10px;padding:4px 10px;border-radius:999px;background:var(--badge);color:var(--accent);font-size:.75rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
article{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin-top:18px;box-shadow:0 6px 22px rgba(25,50,56,.04)}}
article h2{{margin:0 0 10px;font-size:clamp(1.2rem,2vw,1.8rem);line-height:1.4}}
article h2 a{{color:var(--accent);text-decoration:none}}
article h2 a:hover{{text-decoration:underline}}
article p{{color:var(--fg);opacity:.92}}
.meta{{margin-top:10px;font-size:.84rem;color:var(--muted)}}
footer{{margin-top:28px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:.95rem}}
@media (prefers-color-scheme: dark) {{
  :root{{--bg:#172329;--fg:#edf7f5;--muted:#afc4c0;--line:#2e4043;--accent:#67d9d4;--card:#1c2b2d;--badge:#20363a}}
  body{{background:var(--bg);color:var(--fg)}}
  article{{background:var(--card);border-color:var(--line)}}
}}
</style>
</head>
<body><main>
<small>KNOWLEDGE LIBRARY</small>
<h1>知识书库</h1>
<p>在这里保存知识，展开推导，也让图像帮助理解。</p>
{''.join(cards)}
<footer>下载仓库后，在浏览器中打开本页即可浏览书目。教材支持离线阅读。</footer>
</main></body></html>
'''
    return html


def main() -> None:
    entries = collect_books()
    CATALOG_PATH.write_text(
        json.dumps({"title": "知识书库", "books": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    README_PATH.write_text(render_readme(entries), encoding="utf-8")
    INDEX_PATH.write_text(render_index_html(entries), encoding="utf-8")
    print(f"Updated catalog with {len(entries)} books.")


if __name__ == "__main__":
    main()
