#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SOURCE_LIST_MARKER_RE = re.compile(r"(^|\s)[–-]\s+\S")
TARGET_LIST_MARKER_RE = re.compile(r"(?<![A-Za-z0-9])[-–‑]\s+")


def load_memory(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data
    if isinstance(data, list):
        return {"entries": data}
    raise ValueError("translation memory must contain an entries list")


def source_has_merged_list(text: str) -> bool:
    return len(SOURCE_LIST_MARKER_RE.findall(text or "")) >= 2


def split_target_list(text: str) -> str | None:
    text = str(text or "").strip()
    if not text or "\n" in text or text == "__DELETE__":
        return None

    matches = list(TARGET_LIST_MARKER_RE.finditer(text))
    if not matches:
        return None

    prefix = text[: matches[0].start()].strip()
    items: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item = text[match.end() : end].strip()
        if item:
            items.append(f"- {item}")

    if len(items) < 2:
        return None

    lines = []
    if prefix:
        lines.append(prefix)
    lines.extend(items)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", required=True)
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = Path(args.memory)
    data = load_memory(path)
    changes: list[dict[str, str]] = []

    for item in data["entries"]:
        source = str(item.get("source", ""))
        target = str(item.get("target", ""))
        if not source_has_merged_list(source):
            continue
        normalized = split_target_list(target)
        if not normalized or normalized == target:
            continue
        item["target"] = normalized
        changes.append(
            {
                "id": str(item.get("id", "")),
                "source": source,
                "old_target": target,
                "new_target": normalized,
            }
        )

    output = Path(args.output) if args.output else path
    if not args.dry_run:
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "memory": str(path),
                "output": str(output),
                "changed_count": len(changes),
                "changed": changes[:80],
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
