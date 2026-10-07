#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--units", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=60)
    args = parser.parse_args()

    units = json.loads(Path(args.units).read_text(encoding="utf-8"))
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    total = len(units)
    batch_count = math.ceil(total / args.batch_size) if total else 0

    for index in range(batch_count):
        chunk = units[index * args.batch_size : (index + 1) * args.batch_size]
        data = [
            {
                "id": unit["id"],
                "page": unit["page"],
                "source": unit["text"],
                "target": "",
            }
            for unit in chunk
        ]
        path = outdir / f"batch_{index + 1:03d}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        prompt = outdir / f"batch_{index + 1:03d}_prompt.md"
        prompt.write_text(
            "Translate every item into Simplified Chinese. Keep ids unchanged. "
            "Preserve code, commands, variables, format strings, file names, and symbols. "
            "Return JSON only, with id and target fields.\n\n"
            + json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"wrote {batch_count} batches to {outdir}")


if __name__ == "__main__":
    main()
