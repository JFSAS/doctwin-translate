#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def load_translations(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            if isinstance(value, dict):
                out[key] = str(value.get("target", "")).strip()
            else:
                out[key] = str(value).strip()
        return out
    if isinstance(data, list):
        return {item["id"]: str(item.get("target", "")).strip() for item in data}
    raise ValueError("translations must be a dict or list")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--units", required=True)
    parser.add_argument("--translations", required=True)
    parser.add_argument("--max-ratio", type=float, default=2.2)
    args = parser.parse_args()

    units = json.loads(Path(args.units).read_text(encoding="utf-8"))
    translations = load_translations(Path(args.translations))

    missing = []
    no_cjk = []
    identical = []
    long = []
    for unit in units:
        uid = unit["id"]
        src = unit["text"].strip()
        tgt = translations.get(uid, "").strip()
        if not tgt:
            missing.append(uid)
            continue
        if tgt == src:
            identical.append(uid)
        if not CJK_RE.search(tgt) and re.search(r"[A-Za-zÄÖÜäöüß]{3,}", src):
            no_cjk.append(uid)
        if len(tgt) > max(30, len(src) * args.max_ratio):
            long.append(uid)

    report = {
        "total_units": len(units),
        "translated": len(units) - len(missing),
        "missing": missing[:50],
        "missing_count": len(missing),
        "identical": identical[:50],
        "identical_count": len(identical),
        "no_cjk": no_cjk[:50],
        "no_cjk_count": len(no_cjk),
        "long": long[:50],
        "long_count": len(long),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if missing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
