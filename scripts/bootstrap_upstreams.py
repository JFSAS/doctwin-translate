#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_CACHE = Path.home() / ".cache" / "doctwin-translate" / "upstreams"
REPOS = {
    "BabelDOC": "https://github.com/funstory-ai/BabelDOC.git",
    "PDFMathTranslate": "https://github.com/PDFMathTranslate/PDFMathTranslate.git",
}


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def git_head(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            text=True,
        ).strip()
    except Exception:
        return ""


def ensure_repo(name: str, url: str, target: Path, refresh: bool) -> None:
    if target.exists():
        if refresh:
            run(["git", "fetch", "--depth", "1", "origin"], cwd=target)
            run(["git", "pull", "--ff-only"], cwd=target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", url, str(target)])


def install_editable(repo: Path) -> None:
    run([sys.executable, "-m", "pip", "install", "-e", str(repo)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--install",
        choices=["none", "babeldoc", "pdfmathtranslate", "all"],
        default="none",
        help="Optionally pip-install upstream engines into the current Python.",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    for name, url in REPOS.items():
        ensure_repo(name, url, cache_dir / name, args.refresh)

    if args.install in {"babeldoc", "all"}:
        install_editable(cache_dir / "BabelDOC")
    if args.install in {"pdfmathtranslate", "all"}:
        install_editable(cache_dir / "PDFMathTranslate")

    manifest = {
        name: {
            "url": url,
            "path": str((cache_dir / name).resolve()),
            "commit": git_head(cache_dir / name),
        }
        for name, url in REPOS.items()
    }
    manifest_path = cache_dir / "upstreams.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
