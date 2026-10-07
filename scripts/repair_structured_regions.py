#!/usr/bin/env python3
"""Repair structured slide regions in a BabelDOC side-by-side PDF.

This post-process copies code blocks, terminal blocks, and dense diagram/table
regions from the source page into the translated half of a dual PDF. It is
intended for lecture slides where BabelDOC's paragraph re-typesetting may damage
monospace code, formulas, stack diagrams, or table geometry.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class Region:
    rect: fitz.Rect
    reasons: set[str]


def is_close(color: tuple[float, ...] | None, target: tuple[float, float, float], tol: float = 0.035) -> bool:
    if color is None or len(color) < 3:
        return False
    return all(abs(color[i] - target[i]) <= tol for i in range(3))


def color_distance_from_white(color: tuple[float, ...] | None) -> float:
    if color is None or len(color) < 3:
        return 0.0
    return sum(abs(1.0 - color[i]) for i in range(3))


def rect_from_drawing(drawing: dict) -> fitz.Rect | None:
    rect = drawing.get("rect")
    if rect is None:
        return None
    r = fitz.Rect(rect)
    if r.is_empty or r.is_infinite:
        return None
    return r


def classify_rect(r: fitz.Rect, fill: tuple[float, ...] | None, page_rect: fitz.Rect) -> set[str]:
    reasons: set[str] = set()
    w, h = r.width, r.height
    if w < 55 or h < 12:
        return reasons
    if r.width > page_rect.width * 0.95 and r.height > page_rect.height * 0.95:
        return reasons

    # Beamer minted/listing backgrounds and terminal bodies.
    if is_close(fill, (0.973, 0.976, 0.980), 0.025) or is_close(fill, (0.973, 0.973, 0.973), 0.025):
        if w > 140 and h > 20:
            reasons.add("light-code")

    # Header bars for terminal/listing boxes. They are useful only near a box,
    # but keeping them here helps the unioned region preserve the original frame.
    if is_close(fill, (0.859, 0.859, 0.859), 0.035) or is_close(fill, (0.800, 0.800, 0.800), 0.035):
        if w > 140 and h > 16:
            reasons.add("code-header")

    # Colored stack/table/diagram areas. Exclude small decorative logos.
    if color_distance_from_white(fill) > 0.22 and w > 110 and h > 18:
        if not (r.y1 < 90 and r.x0 > page_rect.width * 0.75):
            reasons.add("colored-structure")

    return reasons


def union_regions(regions: list[Region], pad: float) -> list[Region]:
    merged: list[Region] = []
    for region in regions:
        grown = fitz.Rect(region.rect)
        grown.x0 -= pad
        grown.y0 -= pad
        grown.x1 += pad
        grown.y1 += pad
        absorbed = False
        for existing in merged:
            e = fitz.Rect(existing.rect)
            e.x0 -= pad
            e.y0 -= pad
            e.x1 += pad
            e.y1 += pad
            if e.intersects(grown):
                existing.rect |= region.rect
                existing.reasons |= region.reasons
                absorbed = True
                break
        if not absorbed:
            merged.append(Region(fitz.Rect(region.rect), set(region.reasons)))

    changed = True
    while changed:
        changed = False
        out: list[Region] = []
        for region in merged:
            for existing in out:
                e = fitz.Rect(existing.rect)
                r = fitz.Rect(region.rect)
                e.x0 -= pad
                e.y0 -= pad
                e.x1 += pad
                e.y1 += pad
                r.x0 -= pad
                r.y0 -= pad
                r.x1 += pad
                r.y1 += pad
                if e.intersects(r):
                    existing.rect |= region.rect
                    existing.reasons |= region.reasons
                    changed = True
                    break
            else:
                out.append(region)
        merged = out
    return merged


def detect_regions(page: fitz.Page, merge_pad: float) -> list[Region]:
    page_rect = page.rect
    candidates: list[Region] = []
    for drawing in page.get_drawings():
        r = rect_from_drawing(drawing)
        if r is None:
            continue
        reasons = classify_rect(r, drawing.get("fill"), page_rect)
        if reasons:
            candidates.append(Region(r, reasons))

    has_code = any(("light-code" in c.reasons or "code-header" in c.reasons) for c in candidates)
    has_colored_structure = any("colored-structure" in c.reasons for c in candidates)
    effective_merge_pad = max(merge_pad, 240.0) if has_code and has_colored_structure else merge_pad
    regions = union_regions(candidates, pad=effective_merge_pad)
    filtered: list[Region] = []
    for region in regions:
        r = region.rect & page_rect
        if r.width < 70 or r.height < 16:
            continue
        # Avoid replacing translated prose boxes that happen to have a colored
        # accent: require either a code-like rectangle or a dense colored area.
        area = r.width * r.height
        if "light-code" in region.reasons or "code-header" in region.reasons:
            filtered.append(Region(r, region.reasons))
        elif "colored-structure" in region.reasons and area > 16_000:
            filtered.append(Region(r, region.reasons))
    return filtered


def repair(
    source_pdf: Path,
    dual_pdf: Path,
    output_pdf: Path,
    pad: float,
    merge_pad: float,
    only_pages: set[int] | None,
) -> dict:
    source = fitz.open(source_pdf)
    dual = fitz.open(dual_pdf)
    if len(source) != len(dual):
        raise SystemExit(f"page count mismatch: source={len(source)} dual={len(dual)}")

    stats: dict[str, object] = {
        "source": str(source_pdf),
        "dual": str(dual_pdf),
        "output": str(output_pdf),
        "page_count": len(dual),
        "pages": [],
    }
    page_entries: list[dict[str, object]] = []

    for index in range(len(source)):
        page_no = index + 1
        if only_pages is not None and page_no not in only_pages:
            continue
        src_page = source[index]
        dual_page = dual[index]
        src_width = src_page.rect.width
        regions = detect_regions(src_page, merge_pad=merge_pad)
        repaired = []
        for region in regions:
            clip = fitz.Rect(region.rect)
            clip.x0 = max(0, clip.x0 - pad)
            clip.y0 = max(0, clip.y0 - pad)
            clip.x1 = min(src_page.rect.width, clip.x1 + pad)
            clip.y1 = min(src_page.rect.height, clip.y1 + pad)
            dest = fitz.Rect(clip)
            dest.x0 += src_width
            dest.x1 += src_width
            # Cover damaged translated text before painting the original region.
            dual_page.draw_rect(dest, fill=(1, 1, 1), color=None, overlay=True)
            dual_page.show_pdf_page(dest, source, index, clip=clip, overlay=True)
            repaired.append({
                "rect": [round(clip.x0, 2), round(clip.y0, 2), round(clip.x1, 2), round(clip.y1, 2)],
                "reasons": sorted(region.reasons),
            })
        if repaired:
            page_entries.append({"page": page_no, "regions": repaired})

    stats["pages"] = page_entries
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    dual.save(output_pdf, garbage=4, deflate=True)
    dual.close()
    source.close()
    return stats


def parse_pages(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(part))
    return pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dual", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--pad", type=float, default=2.0)
    parser.add_argument(
        "--merge-pad",
        type=float,
        default=None,
        help="Distance used to merge neighboring source structure rectangles. Defaults to --pad.",
    )
    parser.add_argument("--pages")
    args = parser.parse_args()

    stats = repair(
        args.source,
        args.dual,
        args.output,
        args.pad,
        args.merge_pad if args.merge_pad is not None else args.pad,
        parse_pages(args.pages),
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"repaired pages: {len(stats['pages'])}")


if __name__ == "__main__":
    main()
