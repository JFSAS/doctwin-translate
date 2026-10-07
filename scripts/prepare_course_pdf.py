#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import fitz


DEFAULT_TERMS = [
    ("Systemnahe Programmierung", "系统级编程 (systems programming)", "zh-CN"),
    ("Programmiersprache C", "C 语言", "zh-CN"),
    ("Gültigkeitsbereich", "作用域 (scope)", "zh-CN"),
    ("Zeiger", "指针 (pointer)", "zh-CN"),
    ("Speicherverwaltung", "内存管理 (memory management)", "zh-CN"),
    ("Speicherklasse", "存储类 (storage class)", "zh-CN"),
    ("Deklaration", "声明 (declaration)", "zh-CN"),
    ("Definition", "定义 (definition)", "zh-CN"),
    ("Header-Datei", "头文件 (header file)", "zh-CN"),
    ("Linker", "链接器 (linker)", "zh-CN"),
    ("Compiler", "编译器 (compiler)", "zh-CN"),
    ("Heap-Segment", "堆段 (heap segment)", "zh-CN"),
    ("Stack-Segment", "栈段 (stack segment)", "zh-CN"),
    ("Textsegment", "文本段 (text segment)", "zh-CN"),
    ("Datensegment", "数据段 (data segment)", "zh-CN"),
    ("Memory Safety", "内存安全 (memory safety)", "zh-CN"),
    ("Buffer Overflow", "缓冲区溢出 (buffer overflow)", "zh-CN"),
    ("Use-After-Free", "释放后使用 (use-after-free)", "zh-CN"),
    ("Format-String-Attack", "格式化字符串攻击 (format string attack)", "zh-CN"),
    ("struct", "struct 结构体", "zh-CN"),
    ("union", "union 共用体", "zh-CN"),
    ("enum", "enum 枚举", "zh-CN"),
    ("typedef", "typedef 类型定义", "zh-CN"),
]


CODE_TOKENS = [
    "{",
    "}",
    ";",
    "#include",
    "printf",
    "scanf",
    "malloc",
    "free",
    "gcc",
    "clang",
    "return",
    "main(",
    "%d",
    "%s",
    ".c",
    ".h",
]


def parse_pages(spec: str | None, total: int) -> set[int]:
    if not spec:
        return set(range(1, total + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) if a else 1
            end = int(b) if b else total
            pages.update(range(max(1, start), min(total, end) + 1))
        else:
            pages.add(int(part))
    return pages


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("ﬀ", "ff").replace("ﬁ", "fi")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def span_color(span: dict[str, Any]) -> tuple[float, float, float]:
    value = span.get("color", 0)
    return (
        ((value >> 16) & 255) / 255.0,
        ((value >> 8) & 255) / 255.0,
        (value & 255) / 255.0,
    )


def block_info(block: dict[str, Any]) -> dict[str, Any]:
    spans = [span for line in block.get("lines", []) for span in line.get("spans", [])]
    text = clean_text(" ".join(span.get("text", "") for span in spans))
    fonts = sorted({span.get("font", "") for span in spans})
    sizes = [span.get("size", 12.0) for span in spans]
    color = span_color(spans[0]) if spans else (0, 0, 0)
    return {
        "text": text,
        "fonts": fonts,
        "size": max(sizes) if sizes else 12.0,
        "color": color,
        "bbox": block.get("bbox"),
        "span_count": len(spans),
    }


def classify(text: str, fonts: list[str], bbox: list[float], page_height: float) -> str:
    if not text:
        return "empty"
    if bbox and bbox[1] > page_height - 40:
        return "footer"
    mono = fonts and all(("Mono" in f or "Menlo" in f or "Code" in f) for f in fonts)
    if mono:
        return "code"
    if any(tok in text for tok in CODE_TOKENS):
        if len(text) < 180 or text.count(";") >= 1:
            return "code"
    if re.fullmatch(r"[-\d\s/.:+#%()<>_=,]+", text):
        return "symbols"
    if len(text) <= 1:
        return "tiny"
    return "translate"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--pages", default=None, help="1-based pages, e.g. 15- or 1,3,5-9")
    parser.add_argument("--lang-in", default="de")
    parser.add_argument("--lang-out", default="zh-CN")
    args = parser.parse_args()

    src = Path(args.input).expanduser()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(src)
    selected = parse_pages(args.pages, doc.page_count)
    units: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for page_index, page in enumerate(doc, 1):
        page_dict = page.get_text("dict")
        for block_index, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue
            info = block_info(block)
            text = info["text"]
            bbox = info["bbox"]
            if not bbox:
                continue
            kind = classify(text, info["fonts"], bbox, page.rect.height)
            record = {
                "id": f"p{page_index:03d}_b{block_index:03d}",
                "page": page_index,
                "kind": kind,
                "text": text,
                "bbox": bbox,
                "fonts": info["fonts"],
                "font_size": info["size"],
                "color": info["color"],
                "span_count": info["span_count"],
            }
            if page_index in selected and kind == "translate":
                units.append(record)
            else:
                skipped.append(record)

    manifest = {
        "input": str(src),
        "page_count": doc.page_count,
        "page_size": [doc[0].rect.width, doc[0].rect.height] if doc.page_count else None,
        "pages": args.pages,
        "lang_in": args.lang_in,
        "lang_out": args.lang_out,
        "unit_count": len(units),
        "skipped_count": len(skipped),
    }

    (workdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (workdir / "units.json").write_text(json.dumps(units, ensure_ascii=False, indent=2), encoding="utf-8")
    (workdir / "skipped_units.json").write_text(json.dumps(skipped, ensure_ascii=False, indent=2), encoding="utf-8")

    template = {u["id"]: {"source": u["text"], "target": ""} for u in units}
    (workdir / "translation_template.json").write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")

    with (workdir / "glossary_seed.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "tgt_lng"])
        for row in DEFAULT_TERMS:
            writer.writerow(row)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"units: {workdir / 'units.json'}")
    print(f"template: {workdir / 'translation_template.json'}")
    print(f"glossary: {workdir / 'glossary_seed.csv'}")


if __name__ == "__main__":
    main()
