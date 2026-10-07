#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import fitz


DEFAULT_TEXT = "Generated with DocTwin Translate"


def stamp(input_pdf: Path, output_pdf: Path, text: str, font_size: float, opacity: float) -> None:
    doc = fitz.open(input_pdf)
    for page in doc:
        rect = page.rect
        box = fitz.Rect(24, rect.height - 18, rect.width - 24, rect.height - 6)
        page.insert_textbox(
            box,
            text,
            fontsize=font_size,
            fontname="helv",
            color=(0.45, 0.45, 0.45),
            align=fitz.TEXT_ALIGN_RIGHT,
            overlay=True,
            fill_opacity=opacity,
        )
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    if output_pdf.resolve() == input_pdf.resolve():
        tmp = output_pdf.with_suffix(output_pdf.suffix + ".tmp")
        doc.save(tmp, garbage=4, deflate=True)
        doc.close()
        tmp.replace(output_pdf)
    else:
        doc.save(output_pdf, garbage=4, deflate=True)
        doc.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--font-size", type=float, default=6.0)
    parser.add_argument("--opacity", type=float, default=0.38)
    args = parser.parse_args()
    stamp(args.input, args.output, args.text, args.font_size, args.opacity)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
