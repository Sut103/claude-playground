---
issue: 14
stream: Scanner and tests
started: 2026-08-11T07:20:32Z
status: completed
---

## Scope

Files owned by this stream, and no others:

- `md_toc/parser.py`
- `tests/test_parser.py`

## Progress

- Created `md_toc/parser.py` with
  `extract_headings(text, min_level=1, max_level=6) -> list[Heading]`. It is a
  single-pass line scanner over `text.splitlines()`, carrying one fence-state
  variable. `Heading` is imported from `md_toc.types` (task 12, closed and
  frozen); nothing in that module was modified.
- Three `re` patterns are compiled at module scope so the 10,000-line case never
  recompiles per line:
  - `_FENCE_RE` matches a leading run of three or more backticks or three or
    more tildes. The captured run's first character is stored as the fence kind,
    and only the same character can close the fence — a `~~~` line inside a
    backtick block falls through as ordinary fenced content, and vice versa.
  - `_ATX_RE` matches one to six `#` characters followed by at least one space
    or tab. Requiring that whitespace is what makes `#hashtag` and a bare `#`
    non-headings; seven or more `#` also fails to match.
  - `_CLOSING_HASHES_RE` trims a closing `#` run (`## Title ##`) only when it is
    preceded by whitespace or is the entire title, so `## Title#` keeps its
    trailing `#`. This is done here so task 16's slug generator does not have to.
- Order of operations per line is fence toggle, then in-fence skip, then ATX
  match, then the inclusive `min_level`/`max_level` filter, then append. Because
  the fence flag is only ever cleared by a matching closer, an unterminated
  fence simply suppresses the rest of the document instead of raising.
- Created `tests/test_parser.py` with 53 `unittest` cases across ten classes:
  basic extraction and document order, all six levels, non-headings
  (`#hashtag`, bare `#`, seven hashes, indented, mid-line, setext), closing hash
  runs, backtick fence suppression, tilde fence suppression, delimiters not
  crossing, unclosed fences, level bounds, a 10,000-line timing test, and one
  realistic mixed document.

## Verification

- `python3 -m unittest tests.test_parser -v` — Ran 53 tests, OK.
- `python3 -m unittest discover` — Ran 111 tests, OK. That run includes the
  concurrent agent's `tests/test_slug.py` for issue #16; no failures were
  observed there.

## Out of scope

Nothing outside the two owned paths was created, modified, or read-modify-
written. `md_toc/slug.py` and `tests/test_slug.py` belong to issue #16 and were
left untouched; commits stage only this stream's explicit paths.

## Acceptance criteria

All acceptance criteria in `14.md` are met, each covered by at least one
distinct test method.
