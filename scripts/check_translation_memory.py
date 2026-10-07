#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}")
PLACEHOLDER_RE = re.compile(
    r"\{v\d+\}|<b\d+>|</b\d+>|<style id='\d+'>|</style>",
    re.IGNORECASE,
)
LIST_MARKER_RE = re.compile(r"(^|\s)[–-]\s+\S")


def load_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    if isinstance(data, list):
        return data
    raise ValueError("translation memory must contain an entries list")


def placeholders(text: str) -> list[str]:
    return sorted(PLACEHOLDER_RE.findall(text or ""))


def merged_list_marker_count(text: str) -> int:
    return len(LIST_MARKER_RE.findall(text or ""))


def needs_list_newlines(source: str, target: str) -> bool:
    if "\n" in target:
        return False
    if merged_list_marker_count(source) < 2:
        return False
    return merged_list_marker_count(target) >= 1 or " - " in target or "‑ " in target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory", required=True)
    parser.add_argument("--max-ratio", type=float, default=2.4)
    parser.add_argument("--allow-identical", action="store_true")
    args = parser.parse_args()

    entries = load_entries(Path(args.memory))
    missing: list[str] = []
    no_cjk: list[str] = []
    identical: list[str] = []
    long: list[str] = []
    placeholder_mismatch: list[str] = []
    merged_list_without_newlines: list[str] = []

    for item in entries:
        uid = str(item.get("id", ""))
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        if not target:
            missing.append(uid)
            continue
        if target == "__DELETE__":
            continue
        if target == source and not args.allow_identical:
            identical.append(uid)
        if LATIN_WORD_RE.search(source) and not CJK_RE.search(target):
            no_cjk.append(uid)
        if len(target) > max(40, len(source) * args.max_ratio):
            long.append(uid)
        if placeholders(source) != placeholders(target):
            placeholder_mismatch.append(uid)
        if needs_list_newlines(source, target):
            merged_list_without_newlines.append(uid)

    report = {
        "total_entries": len(entries),
        "translated": len(entries) - len(missing),
        "missing_count": len(missing),
        "missing": missing[:80],
        "identical_count": len(identical),
        "identical": identical[:80],
        "no_cjk_count": len(no_cjk),
        "no_cjk": no_cjk[:80],
        "long_count": len(long),
        "long": long[:80],
        "placeholder_mismatch_count": len(placeholder_mismatch),
        "placeholder_mismatch": placeholder_mismatch[:80],
        "merged_list_without_newlines_count": len(merged_list_without_newlines),
        "merged_list_without_newlines": merged_list_without_newlines[:80],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if missing or placeholder_mismatch:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
