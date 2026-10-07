---
name: doctwin-translate
description: Create layout-first bilingual document translations, especially side-by-side PDFs with original pages on the left and AI-translated pages on the right, using Codex translation memory, terminology control, upstream layout engines such as BabelDOC/PDFMathTranslate when available, and render-based QA for formulas, code, tables, charts, and lecture slides.
---

# DocTwin Translate

Use this skill when the user wants a document translated while preserving layout:
left-original/right-translation bilingual PDFs, translated-only PDFs, lecture slides,
academic papers, course handouts, code-heavy PDFs, formula-heavy PDFs, or documents
where visual fidelity matters.

DocTwin is language-agnostic: translate from any source language Codex can understand
into the requested target language. Default to Simplified Chinese when the user does not
specify a target.

## Positioning

DocTwin is an AI-agent workflow, not a standalone hosted translator. Codex is the
first-class runtime, but the same folder can be used by other coding agents that can
read files, run shell/Python commands, and inspect rendered outputs. It combines:

- upstream PDF layout engines when useful, especially BabelDOC/PDFMathTranslate;
- Codex-generated translation memory and terminology control;
- code/formula/placeholder protection;
- post-processing for merged bullets and damaged structured regions;
- render-based QA before delivery.

## Hard Boundary

Codex model access is not exposed as an `OPENAI_API_KEY` for external programs. Do not
claim that BabelDOC or any external CLI can directly call the current Codex chat model.
The no-API-key route is:

1. Use the layout engine to collect exact paragraph strings.
2. Use Codex itself to translate those strings into a JSON translation memory.
3. Build the translated PDF with the JSON memory translator so the layout engine handles
   page geometry, font mapping, and bilingual output.

If the user provides an OpenAI-compatible API key, direct engine translation may be used,
but still apply DocTwin QA.

## Required Workflow

1. Create a work directory under `tmp/pdfs/<doc-stem>/` and final output under
   `output/pdf/`.
2. Bootstrap upstream engines with `scripts/bootstrap_upstreams.py` if needed.
3. Collect translation units with `scripts/run_babeldoc_tm.py --mode collect`.
4. Build a glossary before translating. Keep technical terms, code identifiers, symbols,
   and professional vocabulary consistent.
5. Batch missing memory entries with `scripts/make_babeldoc_tm_batches.py`.
6. Translate by memory id, not by visual guesswork.
7. Normalize list targets with `scripts/normalize_list_targets.py`.
8. Check memory with `scripts/check_translation_memory.py`; fix missing targets,
   placeholder damage, no-CJK targets when Chinese is requested, suspicious length, and
   merged-list warnings.
9. Build with `scripts/run_babeldoc_tm.py --mode build --strict`.
10. Patch merged list blocks with `scripts/patch_merged_list_blocks.py` when needed.
11. Repair code/formula/table/diagram regions with `scripts/repair_structured_regions.py`
    when rendered QA shows code damage, formula deformation, table drift, or chart
    overlap.
12. Stamp the final PDF with the DocTwin watermark using
    `scripts/stamp_doctwin_watermark.py`, unless the user explicitly asks for no
    watermark.
13. Render representative pages with `scripts/render_pdf_pages.py`.
14. Inspect rendered PNGs. Do not deliver until the latest render is free of obvious
    missing translations, broken glyphs, overlapped text, damaged code, or severe layout
    drift.

## Translation Rules

- Preserve code, commands, paths, filenames, APIs, package names, variables, placeholders,
  formulas, and labels unless the user explicitly asks to translate them.
- Preserve BabelDOC placeholders exactly, including `{v1}`, `<b1>`, `</b1>`,
  `<style id='1'>`, and `</style>`.
- For lecture/course PDFs, prefer concise, readable academic translation. Add English
  annotations for key technical terms when helpful, e.g. 栈 (stack), 堆 (heap), 指针
  (pointer), 链接器 (linker).
- Keep list structure. If one collected segment contains several bullets, place each
  translated bullet on its own line.
- Use `__DELETE__` only for duplicate fragments already covered by adjacent text.
- If the user says front matter should not be translated, set the page range accordingly.

## Commands

Use the Python environment created during installation:

```bash
SKILL="${CODEX_HOME:-$HOME/.codex}/skills/doctwin-translate"
PY="$SKILL/.venv/bin/python"
```

Replace `--lang-in de` in the examples with the actual source language code when needed,
for example `en`, `fr`, `es`, `ja`, or `ko`. Keep `--lang-out zh-CN` for Simplified
Chinese, or change it to the requested target language.

Prepare:

```bash
$PY "$SKILL/scripts/bootstrap_upstreams.py" --install babeldoc
```

Collect translation units:

```bash
$PY "$SKILL/scripts/run_babeldoc_tm.py" \
  --input "/path/to/source.pdf" \
  --workdir "tmp/pdfs/source-stem/babeldoc-work-collect" \
  --output-dir "tmp/pdfs/source-stem/babeldoc-collect-output" \
  --memory "tmp/pdfs/source-stem/translation_memory.json" \
  --mode collect \
  --pages "1-" \
  --lang-in de \
  --lang-out zh-CN
```

Create batches and validate memory:

```bash
$PY "$SKILL/scripts/make_babeldoc_tm_batches.py" \
  --memory "tmp/pdfs/source-stem/translation_memory.json" \
  --output-dir "tmp/pdfs/source-stem/batches" \
  --batch-size 50

$PY "$SKILL/scripts/normalize_list_targets.py" \
  --memory "tmp/pdfs/source-stem/translation_memory.json"

$PY "$SKILL/scripts/check_translation_memory.py" \
  --memory "tmp/pdfs/source-stem/translation_memory.json"
```

Build:

```bash
$PY "$SKILL/scripts/run_babeldoc_tm.py" \
  --input "/path/to/source.pdf" \
  --workdir "tmp/pdfs/source-stem/babeldoc-work-build" \
  --output-dir "output/pdf/source-stem-doctwin" \
  --memory "tmp/pdfs/source-stem/translation_memory.json" \
  --mode build \
  --strict \
  --pages "1-" \
  --lang-in de \
  --lang-out zh-CN
```

Repair structured regions when code, formulas, tables, charts, or diagrams are damaged:

```bash
$PY "$SKILL/scripts/repair_structured_regions.py" \
  --source "/path/to/source.pdf" \
  --dual "output/pdf/source-stem-doctwin/source.no_watermark.zh-CN.dual.pdf" \
  --output "output/pdf/source-stem-doctwin/source.doctwin.final.pdf" \
  --report "tmp/pdfs/source-stem/structured-region-report.json" \
  --pad 14 \
  --merge-pad 60
```

Stamp DocTwin watermark:

```bash
$PY "$SKILL/scripts/stamp_doctwin_watermark.py" \
  --input "output/pdf/source-stem-doctwin/source.doctwin.final.pdf" \
  --output "output/pdf/source-stem-doctwin/source.doctwin.final.watermarked.pdf"
```

Render QA:

```bash
$PY "$SKILL/scripts/render_pdf_pages.py" \
  --input "output/pdf/source-stem-doctwin/source.doctwin.final.pdf" \
  --output-dir "tmp/pdfs/source-stem/render" \
  --pages "1,2,5,10,20"
```

## QA Expectations

Check at least these page types when present:

- title/agenda page;
- dense prose page;
- bullet-heavy slide;
- formula-heavy page;
- code or terminal page;
- table/chart page;
- diagram/image page;
- final page.

For large course decks, also generate contact sheets and scan all pages at low resolution.
