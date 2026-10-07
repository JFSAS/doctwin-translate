#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def parse_pages(spec: str, total: int) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) if a else 1
            end = int(b) if b else total
            pages.extend(range(max(1, start), min(total, end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(p for p in pages if 1 <= p <= total))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--zoom", type=float, default=0.55)
    args = parser.parse_args()

    pdf = Path(args.input)
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    print(f"pages {doc.page_count} size {doc[0].rect if doc.page_count else 'n/a'}")
    for page_no in parse_pages(args.pages, doc.page_count):
        pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(args.zoom, args.zoom), alpha=False)
        path = outdir / f"page-{page_no:03d}.png"
        pix.save(path)
        print(path)


if __name__ == "__main__":
    main()
