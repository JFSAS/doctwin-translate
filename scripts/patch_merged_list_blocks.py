#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz

from patch_dual_text_lines import color, resolve_babeldoc_font


SOURCE_LIST_MARKER_RE = re.compile(r"(^|\s)[–-]\s+\S")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}")


def text_of_block(block: dict) -> str:
    return "\n".join(
        "".join(span["text"] for span in line.get("spans", []))
        for line in block.get("lines", [])
    )


def norm(text: str) -> str:
    text = (text or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def cjk_key(text: str) -> str:
    chars = CJK_RE.findall(text or "")
    return "".join(chars[:6])


def source_items(source: str) -> list[str]:
    source = source or ""
    matches = list(re.finditer(r"[–-]\s+", source))
    if not matches:
        return []
    items: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        item = source[match.end() : end].strip()
        if item:
            items.append(item)
    return items


def source_has_merged_list(source: str) -> bool:
    return len(SOURCE_LIST_MARKER_RE.findall(source or "")) >= 2


def source_words(item: str) -> set[str]:
    cleaned = re.sub(r"\{v\d+\}", " ", item or "")
    return {word.lower() for word in WORD_RE.findall(cleaned)}


def item_matches_block(item: str, block_text: str) -> bool:
    words = source_words(item)
    if not words:
        return False
    block_words = {word.lower() for word in WORD_RE.findall(block_text or "")}
    return bool(words & block_words)


def find_right_block(page: fitz.Page, half_width: float, lines: list[str]) -> dict | None:
    keys = [cjk_key(line) for line in lines if cjk_key(line)]
    if not keys:
        return None
    blocks = [
        block
        for block in page.get_text("dict").get("blocks", [])
        if block.get("type") == 0 and block.get("bbox", [0])[0] >= half_width
    ]
    best: tuple[int, float, dict] | None = None
    for block in blocks:
        text = text_of_block(block)
        cjk_text = "".join(CJK_RE.findall(text))
        score = sum(1 for key in keys if key and key in cjk_text)
        if score < 2:
            continue
        area = (block["bbox"][2] - block["bbox"][0]) * (block["bbox"][3] - block["bbox"][1])
        if best is None or score > best[0] or (score == best[0] and area < best[1]):
            best = (score, area, block)
    return best[2] if best else None


def find_left_line_tops(page: fitz.Page, half_width: float, items: list[str]) -> list[float]:
    blocks = [
        block
        for block in page.get_text("dict").get("blocks", [])
        if block.get("type") == 0 and block.get("bbox", [0])[0] < half_width
    ]
    dash_blocks = []
    for block in blocks:
        text = norm(text_of_block(block))
        if text.startswith(("–", "-")):
            dash_blocks.append((block, text))
    dash_blocks.sort(key=lambda pair: (pair[0]["bbox"][1], pair[0]["bbox"][0]))

    needed = len(items)
    if needed < 2:
        return []
    for start in range(0, len(dash_blocks) - needed + 1):
        run = dash_blocks[start : start + needed]
        first_ok = item_matches_block(items[0], run[0][1])
        last_ok = item_matches_block(items[-1], run[-1][1])
        if first_ok and last_ok:
            return [float(block["bbox"][1]) for block, _text in run]
    return []


def iter_tracking_paragraphs(tracking: dict):
    for page_index, page_data in enumerate(tracking.get("page", []), start=1):
        for paragraph in page_data.get("paragraph", []):
            yield page_index, paragraph


def materialize_placeholders(text: str, paragraph: dict) -> str:
    result = text
    for placeholder in paragraph.get("placeholders", []) or []:
        pid = placeholder.get("id")
        chars = str(placeholder.get("formula_chars", ""))
        if pid is None or not chars:
            continue
        result = result.replace("{v" + str(pid) + "}", chars)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="BabelDOC dual PDF")
    parser.add_argument("--tracking", required=True, help="BabelDOC translate_tracking.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--lang-out", default="zh-CN")
    parser.add_argument("--font-scale", type=float, default=1.0)
    parser.add_argument("--min-font-size", type=float, default=10.0)
    parser.add_argument("--max-font-size", type=float, default=18.0)
    parser.add_argument("--fill", default="#ffffff")
    parser.add_argument("--color", default="#000080")
    args = parser.parse_args()

    doc = fitz.open(args.input)
    tracking = json.loads(Path(args.tracking).read_text(encoding="utf-8"))
    half_width = float(doc[0].rect.width) / 2.0
    fontfile = resolve_babeldoc_font(args.lang_out, "sans-serif", False)
    patched: list[dict] = []
    skipped: list[dict] = []

    for page_no, paragraph in iter_tracking_paragraphs(tracking):
        source = str(paragraph.get("input", ""))
        output = materialize_placeholders(str(paragraph.get("output", "")), paragraph)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not source_has_merged_list(source) or len(lines) < 2:
            continue
        items = source_items(source)
        if len(items) < 2:
            continue
        page = doc[page_no - 1]
        right_block = find_right_block(page, half_width, lines)
        left_tops = find_left_line_tops(page, half_width, items)
        if not right_block or len(left_tops) < len(lines):
            skipped.append(
                {
                    "page": page_no,
                    "source": source,
                    "reason": "could not match right block or left line coordinates",
                }
            )
            continue

        right_lines = right_block.get("lines", [])
        first_line_text = ""
        if right_lines:
            first_line_text = "".join(
                span.get("text", "") for span in right_lines[0].get("spans", [])
            ).strip()
        if first_line_text.startswith("●") and not lines[0].startswith("●") and len(right_lines) > 1:
            paint_lines = right_lines[1:]
            bbox = fitz.Rect(paint_lines[0]["bbox"])
            for line in paint_lines[1:]:
                bbox |= fitz.Rect(line["bbox"])
        else:
            paint_lines = right_lines
            bbox = fitz.Rect(right_block["bbox"])
        page.draw_rect(
            fitz.Rect(bbox.x0 - 2, bbox.y0 - 2, bbox.x1 + 6, bbox.y1 + 4),
            color=color(args.fill),
            fill=color(args.fill),
            overlay=True,
        )
        span_sizes = [
            float(span.get("size", 12))
            for line in paint_lines
            for span in line.get("spans", [])
            if span.get("size")
        ]
        base_size = max(span_sizes) if span_sizes else 18.0
        fontsize = min(args.max_font_size, max(args.min_font_size, base_size * args.font_scale))
        x = float(bbox.x0)
        width = float(doc[page_no - 1].rect.width - x - 22)
        for line_text, top in zip(lines, left_tops):
            page.insert_text(
                (x, top + fontsize),
                line_text,
                fontsize=fontsize,
                fontname="bdoc_list_patch",
                fontfile=fontfile,
                color=color(args.color),
                overlay=True,
            )
        patched.append({"page": page_no, "source": source, "lines": len(lines)})

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    report = {
        "output": str(output),
        "patched_count": len(patched),
        "patched": patched[:80],
        "skipped_count": len(skipped),
        "skipped": skipped[:80],
    }
    report_path = output.with_suffix(output.suffix + ".merged-list-report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
