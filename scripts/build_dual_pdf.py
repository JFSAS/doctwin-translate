#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz


FONT_CANDIDATES = [
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def font_path() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("No CJK font found")


def load_translations(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = clean_text(value.get("target", ""))
            else:
                result[key] = clean_text(str(value))
        return result
    if isinstance(data, list):
        return {item["id"]: clean_text(item.get("target", "")) for item in data}
    raise ValueError("translations must be a dict or list")


def background_color(pix: fitz.Pixmap, rect: fitz.Rect, foreground: tuple[float, float, float]) -> tuple[float, float, float]:
    midx = (rect.x0 + rect.x1) / 2
    midy = (rect.y0 + rect.y1) / 2
    points = [
        (rect.x0 - 6, midy),
        (rect.x1 + 6, midy),
        (midx, rect.y0 - 6),
        (midx, rect.y1 + 6),
        (rect.x0 - 6, rect.y0 - 6),
        (rect.x1 + 6, rect.y0 - 6),
        (midx, midy),
    ]
    fg = tuple(round(c * 255) for c in foreground)
    colors: list[tuple[int, int, int]] = []
    for x, y in points:
        xi = min(max(int(round(x)), 0), pix.width - 1)
        yi = min(max(int(round(y)), 0), pix.height - 1)
        r, g, b = pix.pixel(xi, yi)[:3]
        if r < 45 and g < 45 and b < 45:
            continue
        if abs(r - fg[0]) + abs(g - fg[1]) + abs(b - fg[2]) < 70:
            continue
        colors.append((r, g, b))
    if not colors:
        return (1, 1, 1)
    saturated = [c for c in colors if max(c) - min(c) > 35]
    if saturated:
        saturated.sort(key=lambda c: (max(c) - min(c), sum(c)), reverse=True)
        r, g, b = saturated[0]
        return (r / 255.0, g / 255.0, b / 255.0)
    nonwhite = [c for c in colors if min(c) < 245]
    white = [c for c in colors if min(c) >= 245]
    if len(nonwhite) > len(white):
        r = round(sum(c[0] for c in nonwhite) / len(nonwhite))
        g = round(sum(c[1] for c in nonwhite) / len(nonwhite))
        b = round(sum(c[2] for c in nonwhite) / len(nonwhite))
        return (r / 255.0, g / 255.0, b / 255.0)
    return (1, 1, 1)


def cover_rect(page: fitz.Page, rect: fitz.Rect, fill: tuple[float, float, float]) -> None:
    r = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
    page.draw_rect(r, color=fill, fill=fill, overlay=True)


def insert_fit(page: fitz.Page, rect: fitz.Rect, text: str, size: float, color, fontfile: str) -> None:
    size = max(min(size * 0.88, 34), 6.2)
    for _ in range(14):
        rc = page.insert_textbox(
            rect,
            text,
            fontsize=size,
            fontfile=fontfile,
            fontname="cjk",
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
        )
        if rc >= 0:
            return
        size *= 0.90
    page.insert_textbox(
        rect,
        text,
        fontsize=max(size, 5.0),
        fontfile=fontfile,
        fontname="cjk",
        color=color,
        align=fitz.TEXT_ALIGN_LEFT,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--units", required=True)
    parser.add_argument("--translations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--right-extra", type=float, default=80.0)
    parser.add_argument("--force-white-background", action="store_true")
    args = parser.parse_args()

    src = Path(args.input).expanduser()
    units = json.loads(Path(args.units).read_text(encoding="utf-8"))
    translations = load_translations(Path(args.translations))
    missing = [u["id"] for u in units if not translations.get(u["id"])]
    if missing and not args.allow_missing:
        raise SystemExit(f"Missing {len(missing)} translations, first: {missing[:10]}")

    by_page: dict[int, list[dict[str, Any]]] = {}
    for unit in units:
        by_page.setdefault(int(unit["page"]), []).append(unit)

    fontfile = font_path()
    source = fitz.open(src)
    result = fitz.open()

    for page_no, src_page in enumerate(source, 1):
        width, height = src_page.rect.width, src_page.rect.height
        out_page = result.new_page(width=width * 2, height=height)
        out_page.show_pdf_page(fitz.Rect(0, 0, width, height), source, page_no - 1)
        out_page.show_pdf_page(fitz.Rect(width, 0, width * 2, height), source, page_no - 1)
        if page_no not in by_page:
            continue
        pix = src_page.get_pixmap(alpha=False)
        for unit in by_page[page_no]:
            target_text = translations.get(unit["id"], "")
            if not target_text:
                continue
            if clean_text(target_text) == clean_text(unit.get("text", "")):
                continue
            bbox = fitz.Rect(unit["bbox"])
            color = tuple(unit.get("color", [0, 0, 0]))
            size = float(unit.get("font_size", 12.0))
            fill = (1, 1, 1) if args.force_white_background or (bbox.y0 < 90 and size > 16) else background_color(pix, bbox, color)
            extra = args.right_extra if bbox.width > 80 else 35
            target = fitz.Rect(bbox.x0 + width, bbox.y0, bbox.x1 + width + extra, bbox.y1 + 4)
            cover_rect(out_page, target, fill)
            insert_fit(out_page, target, target_text, size, color, fontfile)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out, garbage=4, deflate=True)
    print(out.resolve())


if __name__ == "__main__":
    main()
