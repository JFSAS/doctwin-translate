#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_BABELDOC_REPO = (
    Path.home()
    / ".cache"
    / "doctwin-translate"
    / "upstreams"
    / "BabelDOC"
)


def normalize_source(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"\s+", " ", text.strip())
    return text


def stable_id(source: str) -> str:
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return f"bdoc_{digest}"


class Counter:
    def __init__(self) -> None:
        self.value = 0

    def inc(self, amount: int) -> None:
        self.value += int(amount or 0)


def load_memory(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not path.exists():
        return [], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        entries = data["entries"]
    elif isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = [
            {"id": stable_id(str(source)), "source": str(source), "target": str(target)}
            for source, target in data.items()
        ]
    else:
        raise ValueError("translation memory must be a dict or a list")

    targets: dict[str, str] = {}
    clean_entries: list[dict[str, Any]] = []
    for item in entries:
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        if not source:
            continue
        entry = {
            "id": str(item.get("id") or stable_id(source)),
            "source": source,
            "normalized_source": normalize_source(source),
            "target": target,
        }
        clean_entries.append(entry)
        if target:
            targets[entry["normalized_source"]] = target
    return clean_entries, targets


class TranslationMemoryTranslatorBase:
    """Mixin body injected after BabelDOC's BaseTranslator is imported."""

    name = "codex_tm"

    def _init_tm(self, memory_path: Path, mode: str, strict: bool, lang_in: str, lang_out: str) -> None:
        self.model = "codex-json-memory"
        self.memory_path = memory_path
        self.mode = mode
        self.strict = strict
        self._lock = threading.Lock()
        self._entries, self._targets = load_memory(memory_path)
        self._by_key = {item["normalized_source"]: item for item in self._entries}
        self._missing: list[dict[str, str]] = []
        self.token_count = Counter()
        self.prompt_token_count = Counter()
        self.completion_token_count = Counter()
        self.cache_hit_prompt_token_count = Counter()
        self.lang_in = lang_in
        self.lang_out = lang_out

    def do_llm_translate(self, text: str, rate_limit_params: dict | None = None) -> str:
        raise NotImplementedError

    def get_formular_placeholder(self, placeholder_id: int | str):
        placeholder = "{v" + str(placeholder_id) + "}"
        regex = r"\{\s*v\s*" + str(placeholder_id) + r"\s*\}"
        return placeholder, regex

    def do_translate(self, text: str, rate_limit_params: dict | None = None) -> str:
        source = str(text or "")
        key = normalize_source(source)
        if not key:
            return source
        target = self._targets.get(key, "").strip()
        with self._lock:
            entry = self._by_key.get(key)
            if entry is None:
                entry = {
                    "id": stable_id(source),
                    "source": source,
                    "normalized_source": key,
                    "target": "",
                }
                self._by_key[key] = entry
                self._entries.append(entry)
            if target:
                entry["target"] = target
                if target == "__DELETE__":
                    return ""
                return target
            if not any(item["normalized_source"] == key for item in self._missing):
                self._missing.append(entry)
        return source

    def save_memory(self) -> None:
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "meta": {
                "engine": "BabelDOC",
                "translator": self.name,
                "lang_in": self.lang_in,
                "lang_out": self.lang_out,
                "mode": self.mode,
            },
            "entries": sorted(self._entries, key=lambda item: item["id"]),
        }
        self.memory_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def missing(self) -> list[dict[str, str]]:
        return self._missing


def import_babeldoc(repo: Path | None) -> dict[str, Any]:
    if repo and repo.exists():
        sys.path.insert(0, str(repo))
    try:
        from babeldoc.docvision.doclayout import DocLayoutModel
        from babeldoc.format.pdf.high_level import translate
        from babeldoc.format.pdf.translation_config import TranslationConfig
        from babeldoc.format.pdf.translation_config import WatermarkOutputMode
        from babeldoc.translator.translator import BaseTranslator
        from babeldoc.translator.translator import set_translate_rate_limiter
    except Exception as exc:
        raise SystemExit(
            "Could not import BabelDOC. Run bootstrap_upstreams.py with "
            "--install babeldoc, or pass --babeldoc-repo to a checked-out repo "
            "with dependencies installed. Original error: " + repr(exc)
        ) from exc
    return {
        "DocLayoutModel": DocLayoutModel,
        "translate": translate,
        "TranslationConfig": TranslationConfig,
        "WatermarkOutputMode": WatermarkOutputMode,
        "BaseTranslator": BaseTranslator,
        "set_translate_rate_limiter": set_translate_rate_limiter,
    }


def run_translation(args: argparse.Namespace) -> dict[str, Any]:
    imports = import_babeldoc(Path(args.babeldoc_repo).expanduser() if args.babeldoc_repo else None)
    BaseTranslator = imports["BaseTranslator"]

    class TranslationMemoryTranslator(TranslationMemoryTranslatorBase, BaseTranslator):
        def __init__(self, lang_in: str, lang_out: str, ignore_cache: bool = True) -> None:
            BaseTranslator.__init__(self, lang_in, lang_out, ignore_cache=True)
            self._init_tm(Path(args.memory), args.mode, args.strict, lang_in, lang_out)

    translator = TranslationMemoryTranslator(args.lang_in, args.lang_out, ignore_cache=True)
    imports["set_translate_rate_limiter"](args.qps)

    doc_layout_model = imports["DocLayoutModel"].load_onnx()
    output_dir = Path(args.output_dir).expanduser()
    workdir = Path(args.workdir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)

    config = imports["TranslationConfig"](
        input_file=args.input,
        font=None,
        pages=args.pages,
        output_dir=output_dir,
        translator=translator,
        term_extraction_translator=translator,
        debug=args.debug,
        lang_in=args.lang_in,
        lang_out=args.lang_out,
        no_dual=args.no_dual,
        no_mono=args.no_mono,
        qps=args.qps,
        doc_layout_model=doc_layout_model,
        working_dir=workdir,
        min_text_length=args.min_text_length,
        split_short_lines=args.split_short_lines,
        short_line_split_factor=args.short_line_split_factor,
        watermark_output_mode=imports["WatermarkOutputMode"].NoWatermark,
        auto_extract_glossary=False,
        save_auto_extracted_glossary=False,
        skip_clean=args.skip_clean,
        skip_scanned_detection=args.skip_scanned_detection,
        disable_rich_text_translate=args.disable_rich_text_translate,
        primary_font_family=args.primary_font_family,
        only_include_translated_page=args.only_include_translated_page,
        report_interval=0.2,
        pool_max_workers=args.pool_max_workers or args.qps,
    )

    def nop(_config: Any) -> None:
        return None

    getattr(doc_layout_model, "init_font_mapper", nop)(config)
    result = imports["translate"](config)
    result_payload: dict[str, Any] = {
        "mono_pdf_path": str(getattr(result, "mono_pdf_path", "") or ""),
        "dual_pdf_path": str(getattr(result, "dual_pdf_path", "") or ""),
        "no_watermark_mono_pdf_path": str(getattr(result, "no_watermark_mono_pdf_path", "") or ""),
        "no_watermark_dual_pdf_path": str(getattr(result, "no_watermark_dual_pdf_path", "") or ""),
    }

    translator.save_memory()
    missing_path = Path(args.memory).with_name(Path(args.memory).stem + ".missing.json")
    missing_path.write_text(json.dumps(translator.missing, ensure_ascii=False, indent=2), encoding="utf-8")
    result_payload["memory"] = str(Path(args.memory).resolve())
    result_payload["missing"] = str(missing_path.resolve())
    result_payload["missing_count"] = len(translator.missing)
    if args.strict and translator.missing:
        result_payload["strict_failed"] = True
    return result_payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--memory", required=True)
    parser.add_argument("--mode", choices=["collect", "build"], default="build")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--pages")
    parser.add_argument("--lang-in", default="de")
    parser.add_argument("--lang-out", default="zh-CN")
    parser.add_argument("--babeldoc-repo", default=str(DEFAULT_BABELDOC_REPO))
    parser.add_argument("--qps", type=int, default=20)
    parser.add_argument("--pool-max-workers", type=int)
    parser.add_argument("--min-text-length", type=int, default=5)
    parser.add_argument("--split-short-lines", action="store_true")
    parser.add_argument("--short-line-split-factor", type=float, default=0.8)
    parser.add_argument("--primary-font-family", choices=["serif", "sans-serif", "script"], default="sans-serif")
    parser.add_argument("--disable-rich-text-translate", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-scanned-detection", action="store_true")
    parser.add_argument("--only-include-translated-page", action="store_true")
    parser.add_argument("--no-dual", action="store_true")
    parser.add_argument("--no-mono", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    result = run_translation(args)
    result_path = Path(args.memory).with_name(Path(args.memory).stem + ".result.json")
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("strict_failed"):
        raise SystemExit(3)


if __name__ == "__main__":
    main()
