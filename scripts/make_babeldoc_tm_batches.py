#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    if isinstance(data, list):
        return data
    raise ValueError("translation memory must contain an entries list")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--include-completed", action="store_true")
    parser.add_argument("--glossary")
    args = parser.parse_args()

    entries = load_entries(Path(args.memory))
    todo = [
        {
            "id": item["id"],
            "source": item["source"],
            "target": str(item.get("target", "")).strip(),
        }
        for item in entries
        if args.include_completed or not str(item.get("target", "")).strip()
    ]
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    batch_count = math.ceil(len(todo) / args.batch_size) if todo else 0
    glossary_text = ""
    if args.glossary:
        glossary_text = Path(args.glossary).read_text(encoding="utf-8")

    for index in range(batch_count):
        chunk = todo[index * args.batch_size : (index + 1) * args.batch_size]
        path = outdir / f"babeldoc_tm_batch_{index + 1:03d}.json"
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
        prompt = outdir / f"babeldoc_tm_batch_{index + 1:03d}_prompt.md"
        prompt.write_text(
            "Translate each BabelDOC segment from German into Simplified Chinese.\n"
            "Return JSON only: a list of objects with id and target.\n"
            "Keep placeholders exactly unchanged, including {v1}, {v2}, <b1>, </b1>, "
            "<style id='1'>, </style>, code, variables, formulas, units, and filenames.\n"
            "If one source segment contains several list items such as '– item – item – item', "
            "keep the same list structure in the target with literal newline characters between "
            "items. Do not compress several slide bullets into one Chinese sentence.\n"
            "Use precise academic Chinese that is easy for students to understand. "
            "Keep useful English annotations for technical terms when helpful.\n"
            "If a source item is only a broken leftover fragment that is already covered "
            "by the surrounding translation, set target to __DELETE__.\n"
            "Do not add explanations outside the target field.\n\n"
            + (f"Glossary:\n{glossary_text}\n\n" if glossary_text else "")
            + json.dumps(chunk, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"wrote {batch_count} BabelDOC translation-memory batches to {outdir}")


if __name__ == "__main__":
    main()
