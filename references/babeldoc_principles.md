# BabelDOC Principles To Preserve

These are the parts of BabelDOC worth copying into Codex-native workflows.

1. Build an intermediate representation before translating.
   Work from pages, boxes, paragraphs, styles, fonts, and layout labels instead of raw PDF text strings.

2. Translate paragraph-level units, not random spans.
   Use span-level only for tables or diagrams where one block contains many separate labels.

3. Protect non-language structures with placeholders.
   Code, commands, formulas, file paths, printf placeholders, variables, and rich text markers must survive translation unchanged.

4. Use a glossary before translation.
   Consistency beats clever local wording. Build terms from the document, user preferences, and course domain.

5. Typeset after translation.
   Fit text to the original box by wrapping and scaling, not by allowing overflow. Use smaller CJK font sizes and shrink only as needed.

6. Generate translated pages first, then dual pages.
   A side-by-side PDF should place original and translated pages next to each other. Avoid direct uncontrolled drawing on the combined page unless needed.

7. Treat tables, diagrams, and code differently.
   Tables often need cell/span-level replacement. Code blocks should be preserved. Diagrams may need label-only replacement.

8. Render before delivery.
   Page count and PDF save success are not enough. Inspect representative PNGs.

Common failure signs:

- Colored headers are covered by white rectangles.
- Code is partially translated or erased.
- A diagram label cluster becomes one long line.
- Tiny footer or note text gets enlarged.
- Terminology changes across pages.
- Long Chinese translations overflow original boxes.
