#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


def color(value):
    if isinstance(value, str):
        value = value.strip().lstrip("#")
        if len(value) == 6:
            return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(float(x) for x in value)
    raise ValueError(f"invalid color: {value!r}")


def resolve_babeldoc_font(lang_out: str, family: str, bold: bool = False) -> str | None:
    try:
        from babeldoc.assets import assets
    except Exception:
        return None

    try:
        font_family = assets.get_font_family(lang_out)
    except Exception:
        return None

    normal_fonts = font_family.get("normal", [])
    script_fonts = font_family.get("script", [])
    base_fonts = font_family.get("base", [])
    if family == "script":
        candidates = script_fonts + normal_fonts + base_fonts
    elif family == "serif":
        candidates = [
            name
            for name in normal_fonts
            if "SerifCN" in name or "Serif" in name
        ] + normal_fonts + base_fonts
    else:
        candidates = [
            name
            for name in normal_fonts
            if "SansCN" in name or "Sans" in name
        ] + normal_fonts + base_fonts

    if bold:
        preferred = [name for name in candidates if "Bold" in name]
    else:
        preferred = [name for name in candidates if "Regular" in name]
    candidates = preferred + candidates

    seen = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        try:
            path, _meta = assets.get_font_and_metadata(name)
            return str(path)
        except Exception:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--patches", required=True)
    parser.add_argument("--lang-out", default="zh-CN")
    parser.add_argument(
        "--primary-font-family",
        choices=["sans-serif", "serif", "script"],
        default="sans-serif",
    )
    args = parser.parse_args()

    patches = json.loads(Path(args.patches).read_text(encoding="utf-8"))
    if isinstance(patches, dict):
        patches = patches.get("patches", [])
    doc = fitz.open(args.input)

    for patch in patches:
        page = doc[int(patch["page"]) - 1]
        cover = patch.get("cover")
        if cover:
            rect = fitz.Rect(*cover)
            page.draw_rect(rect, color=color(patch.get("fill", "#ffffff")), fill=color(patch.get("fill", "#ffffff")), overlay=True)
        fontfile = patch.get("fontfile") or resolve_babeldoc_font(
            patch.get("lang_out", args.lang_out),
            patch.get("primary_font_family", args.primary_font_family),
            bool(patch.get("bold", False)),
        )
        fontname = patch.get("fontname")
        if not fontname:
            suffix = hashlib.sha1(str(fontfile or "china-s").encode("utf-8")).hexdigest()[:8]
            fontname = f"bdocpatch_{suffix}"
        fontsize = float(patch.get("fontsize", 12))
        text_color = color(patch.get("color", "#000080"))
        for line in patch.get("lines", []):
            line_fontfile = line.get("fontfile", fontfile)
            line_fontname = line.get("fontname", fontname)
            page.insert_text(
                (float(line["x"]), float(line["y"])),
                str(line["text"]),
                fontsize=float(line.get("fontsize", fontsize)),
                fontname=str(line_fontname),
                fontfile=str(line_fontfile) if line_fontfile else None,
                color=color(line.get("color", text_color)),
                overlay=True,
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    print(output)


if __name__ == "__main__":
    main()
