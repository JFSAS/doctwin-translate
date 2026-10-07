# Upstream Engine Integration

Use upstream engines for polished output. The local PyMuPDF overlay scripts are a fallback for drafts or for files that upstream engines cannot process.

## BabelDOC

Preferred engine for high-quality course PDFs.

- Source: `https://github.com/funstory-ai/BabelDOC`
- Entry point: `babeldoc.main:cli`
- Programmatic route: `babeldoc.format.pdf.high_level.translate` for robust synchronous jobs; `async_translate` is available for UI progress streaming.
- Configuration: `babeldoc.format.pdf.translation_config.TranslationConfig`
- Translator seam: `babeldoc.translator.translator.BaseTranslator`
- Core pipeline: PDF clean/fix, IL creation, layout parser, table parser, paragraph finder, styles/formulas, term extraction, `ILTranslator`, `Typesetting`, `FontMapper`, `PDFCreater`
- Dual output: `PDFCreater.create_side_by_side_dual_pdf`

For users without an API key, do not pretend BabelDOC can call the current Codex chat model. Instead:

1. Run `run_babeldoc_tm.py --mode collect` so BabelDOC itself emits the paragraph strings it wants translated.
2. Translate `babeldoc_translation_memory.json` entries in Codex batches.
3. Run `check_translation_memory.py`.
4. Run `run_babeldoc_tm.py --mode build --strict` so BabelDOC performs its own layout and PDF generation using the completed JSON memory.

This keeps BabelDOC's mature layout machinery while keeping translation quality inside Codex.

## PDFMathTranslate

Useful as a secondary engine and compatibility reference.

- Source: `https://github.com/PDFMathTranslate/PDFMathTranslate`
- Legacy translator seam: `pdf2zh.translator.BaseTranslator.do_translate(text)`
- Legacy converter instantiates translator classes by service name.
- CLI includes BabelDOC bridge modes. Prefer BabelDOC direct for this skill unless BabelDOC fails on the file.

## What Not To Do

- Do not paste entire upstream repositories into `SKILL.md`.
- Do not rely on a one-pass overlay PDF as final output for a user asking for BabelDOC-like quality.
- Do not translate from raw PyMuPDF blocks when BabelDOC collection is available; those blocks do not match the final typesetting units.
