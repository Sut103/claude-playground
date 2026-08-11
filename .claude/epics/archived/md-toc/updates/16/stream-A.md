---
issue: 16
stream: Slug generation and tests
started: 2026-08-11T07:20:32Z
status: completed
---
## Scope
slugify implementing GitHub's anchor dialect with duplicate disambiguation.
Files: md_toc/slug.py, tests/test_slug.py

## Progress
- Implemented `slugify(title, seen) -> str` in `md_toc/slug.py`:
  - `str.lower()`, then a module-scope compiled `[^\w\s-]` pattern strips
    punctuation (word chars, whitespace and hyphens survive), then `.strip()`,
    then a compiled `\s+` pattern collapses whitespace runs to single hyphens.
  - Python 3's default Unicode `\w` keeps accented, Cyrillic and CJK letters;
    Unicode punctuation, smart quotes, em dashes and emoji are stripped.
  - Duplicate handling: base slug absent from `seen` -> store `0`, return base;
    present -> increment and return `f"{base}-{count}"`, giving `-1` for the
    second occurrence and `-2` for the third. `seen` is mutated in place and is
    owned by the caller, one dict per document.
  - Standard library only (`re`); imports nothing from the rest of the package,
    so it stays independent of #14's parser work.
- Wrote 38 unittest tests in `tests/test_slug.py` across six classes:
  TestCasing, TestWhitespace, TestPunctuation, TestUnicode, TestDuplicates,
  TestDocumentOrder. Covers every acceptance criterion as a distinct test
  method, including an explicit three-way duplicate case, a five-way sequence,
  fresh-`seen` reset / no cross-document leakage, two different titles
  normalizing to the same slug, an empty/punctuation-only title, and the
  "Setup" vs literal "Setup 1" collision case.

## Verification
- `python3 -m unittest tests.test_slug -v` -> Ran 38 tests, OK.
- `python3 -m unittest discover` -> Ran 111 tests, OK (includes #14's
  test_parser.py, which was passing at the time of this run).

## Out of scope
Nothing outside `md_toc/slug.py`, `tests/test_slug.py` and this progress file
was created or modified. `md_toc/parser.py` and `tests/test_parser.py` belong to
the concurrent #14 stream and were left untouched.
