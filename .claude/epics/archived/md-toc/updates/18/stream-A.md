---
issue: 18
stream: Renderer and tests
started: 2026-08-11T07:28:51Z
completed: 2026-08-11T07:40:00Z
status: completed
---

## Scope
render_toc producing a nested Markdown list with anchor links.
Files: md_toc/render.py, tests/test_render.py

## Progress
- Read the closed upstream modules before writing code: `md_toc/types.py`
  (`Heading(level, title)`, frozen dataclass), `md_toc/slug.py`
  (`slugify(title, seen)`, mutates `seen` in place), `md_toc/parser.py`.
- Implemented `render_toc(headings) -> str` in `md_toc/render.py`:
  - Returns `""` immediately on an empty list.
  - Computes `base = min(h.level for h in headings)` so the shallowest level
    present renders flush left; indentation is `"  " * (h.level - base)`.
    A document starting at `##` renders identically to one starting at `#`.
  - Emits `- [Title](#slug)` per heading, link text keeping the original
    casing and punctuation while only the anchor is slugified.
  - Creates ONE `seen: dict[str, int] = {}` per call and threads it through
    every `slugify` call, so duplicate headings get `-1` / `-2` anchors.
  - Joins with `"\n"` and appends no trailing newline, leaving surrounding
    blank lines to #13's splice so `--in-place` stays idempotent.
- Wrote `tests/test_render.py`: 43 tests across 10 classes covering entry
  format, link-text preservation, nesting, relative indentation (shallowest
  h2/h3/h6 flush left, baseline is the minimum level not the first), level
  jumps (h1 -> h4, h1 -> h3, jump down and back up), duplicate anchors,
  empty input, output shape (no leading/trailing newline, no blank lines,
  repeat-render stable), a combined realistic fixture exercising nesting +
  duplicates + a non-`#` start together, and one parser integration test.
- Mutation-checked the critical detail: replacing the shared `seen` with a
  fresh `{}` per heading fails 10 tests, confirming the duplicate-anchor
  regression is genuinely covered rather than only asserted in prose.

## Testing
- `python3 -m unittest tests.test_render -v` -> Ran 43 tests, OK.
- `python3 -m unittest discover` -> Ran 157 tests, OK (zero failures).

## Notes
- Standard library only; no files outside this stream's scope were touched.
- One test expectation was corrected during the run: an empty title slugifies
  to `""`, so the entry is `- [](#)` (bare `#` fragment retained), not `- []()`.
- Downstream #13 (splice) and #15 (CLI) are unblocked by this landing.
