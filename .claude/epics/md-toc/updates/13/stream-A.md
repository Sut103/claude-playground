---
issue: 13
stream: Splice and tests
started: 2026-08-11T07:32:32Z
completed: 2026-08-11T07:40:00Z
status: completed
---
## Scope
splice_toc replacing content between marker comments, byte-preserving and idempotent.
Files: md_toc/splice.py, tests/test_splice.py

## Progress
- Read 13.md, plus render.py / types.py / parser.py (all closed) before writing anything.
- Implemented `md_toc/splice.py` with the agreed public surface: `TOC_START`,
  `TOC_END`, `MarkerError`, `splice_toc(text, toc) -> str`. Committed immediately
  (8c3d872) so the concurrent CLI stream on issue #15 was unblocked before test polish.
- Implementation is a plain `str.find` for each marker — no regex over the document.
  The result is `prefix + "\n" + toc + "\n" + suffix`, where `prefix` is
  `text[:start + len(TOC_START)]` and `suffix` is `text[end:]`. Both are untouched
  slices of the input, so preservation outside the markers is structural rather than
  a property the tests have to police, and the marker lines survive by construction.
- Idempotency falls out of that shape: the previous splice wrote exactly
  `\n + toc + \n` into the region, so re-splicing a current document rebuilds the
  identical bytes and `--check` sees no diff. Verified over three consecutive splices
  driven by real `extract_headings` + `render_toc` output, not a hand-written fixture.
- `MarkerError` covers missing opening, missing closing, both missing, and a closing
  marker that precedes the opening one. One message names both markers:
  "document must contain <!-- toc --> followed by <!-- /toc -->". The CLI maps this
  onto exit code 2.
- Only the first marker pair is the TOC region; a later `<!-- toc -->` / `<!-- /toc -->`
  pair in the body is untouched.
- 37 tests in `tests/test_splice.py` across 8 classes: replacement, empty region,
  preservation (trailing whitespace, blank runs, CRLF, present/absent final newline,
  explicit slice-equality of prefix and suffix), marker survival, idempotency,
  first-pair-only, marker errors, and the constant values.

## Verification
- `python3 -m unittest tests.test_splice -v` -> Ran 37 tests, OK.
- `python3 -m unittest discover` -> Ran 194 tests, OK. `tests/test_cli.py` from the
  concurrent #15 stream had not landed at the time of that run.
- Re-ran after #15's tests appeared: `python3 -m unittest discover` -> Ran 234 tests,
  OK. The CLI stream is green against this module's contract; `md_toc/cli.py`,
  `md_toc/__main__.py` and `tests/test_cli.py` were left untouched and unstaged by me.

## Status
All acceptance criteria in 13.md met. Standard library only, no filesystem access.
