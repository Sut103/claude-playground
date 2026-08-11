---
issue: 17
stream: Fixtures and acceptance tests
agent: general-purpose
started: 2026-08-11T07:40:00Z
completed: 2026-08-11T08:05:00Z
status: completed
---

# Stream A: Fixtures and acceptance tests

## Scope

Owned exactly two paths, plus this progress file:

- `tests/fixtures/`
- `tests/test_acceptance.py`

No source module was modified. Defects found in the assembled CLI are recorded
below and left unfixed, for a linked bug issue against the responsible task.

## Fixture corpus

| File | Role |
| --- | --- |
| `basic.md` | Six headings across four levels, markers present, embedded TOC current. Story 1 and Story 3-fresh fixture. `What's New?` exercises punctuation slugging. |
| `stale.md` | `basic.md` with `## Usage` renamed to `## Usage and Examples` after the TOC block was written. Story 3-stale and Story 2 rewrite fixture. |
| `no_markers.md` | Headings, no marker comments. Error-path fixture. |
| `fenced.md` | Heading-like lines inside ``` and ~~~ fences, including a tilde run nested in a backtick fence and vice versa, plus three identical `## Real Heading` titles for the anchor-suffix check. |
| `h2_only.md` | Shallowest heading is `##`, for the relative-indentation rule. |
| `duplicates.md` | Three identical `## Overview` headings plus a unique one. |
| `crlf.md` | `basic.md` with CRLF line endings. Reproduction for the defect below. |

Every marked fixture is committed with a current TOC, and
`TestStory3Check.test_every_marked_fixture_is_committed_fresh` asserts that, so
the corpus cannot silently rot.

## Tests

`tests/test_acceptance.py` — 33 tests in 8 `TestCase` classes. Each copies the
fixture it needs into a per-test `tempfile.TemporaryDirectory` with
`shutil.copy`, so the committed corpus is never mutated; the copy is asserted
byte-equal to its source before use. All file assertions use `read_bytes()`.

- `TestStory1GenerateToStdout` (6) — nested list on stdout, two spaces per
  level, every entry linking to a slugified anchor, h2-shallowest rebasing,
  source file byte-identical after the run.
- `TestStory2InPlace` (7) — marker region replaced, bytes outside the markers
  identical before and after, second run a no-op, an already-current document
  round-tripping unchanged, missing markers exiting 2 with both marker strings
  and the filename in the message and no write, in-place and check agreeing,
  `--in-place --check` rejected by argparse without writing.
- `TestStory3Check` (5) — 0 on fresh, 1 on stale with the filename in the
  output, no write in either case, marker-less document erroring without a
  write, corpus freshness.
- `TestFencedCodeBlocks` (3) — seven ghost headings absent from stdout and
  from the spliced region; real headings around the fences survive.
- `TestDuplicateAnchors` (2) — `#overview` / `#overview-1` / `#overview-2` end
  to end; all anchors unique across three fixtures.
- `TestLevelBounds` (4) — `--max-level`, `--min-level` with rebased indent, an
  empty range, and bounds applied through `--in-place`.
- `TestInstalledEntryPoint` (5) — real `python3 -m md_toc` subprocess runs for
  Story 1, Story 3 exit statuses, two-process idempotency, the marker error on
  stderr with status 2, and a missing file erroring without a traceback.
- `TestKnownDefects` (1, `expectedFailure`) — the CRLF reproduction below.

## Verification

```
$ python3 -m unittest tests.test_acceptance -v
Ran 33 tests in 0.342s

OK (expected failures=1)

$ python3 -m unittest discover
Ran 267 tests in 0.590s

OK (expected failures=1)
```

Suite total went from 234 to 267.

## Defects found — NOT fixed here

This task owns no source module, so all three are reported for linked bug
issues rather than repaired.

### A. `--in-place` destroys CRLF line endings (Story 2 criterion violated)

Responsible task: #15 (`md_toc/cli.py` file I/O).

`cli.main` reads with `Path.read_text(encoding="utf-8")` — universal newlines,
so every `\r\n` becomes `\n` — and writes the spliced result back with
`Path.write_text`, which emits `\n` on Linux. On a CRLF document every line
ending in the file changes, including all bytes outside the markers, which
directly violates "Content outside the markers is byte-for-byte unchanged".
The whole file is rewritten even when the TOC was already current.

Minimal reproduction:

```
$ python3 -c "open('crlf.md','wb').write(b'# A\r\n\r\n<!-- toc -->\r\n- [A](#a)\r\n<!-- /toc -->\r\n')"
$ python3 -m md_toc --in-place crlf.md
$ python3 -c "print(open('crlf.md','rb').read())"
b'# A\n\n<!-- toc -->\n- [A](#a)\n<!-- /toc -->\n'
```

Recorded as `TestKnownDefects.test_crlf_document_keeps_its_line_endings_outside_the_markers`,
marked `expectedFailure` so `discover` stays green and the day it is fixed the
suite reports an unexpected success. `--check` is unaffected: it compares two
already-normalized strings, so it neither false-positives nor false-negatives.
Likely fix: `read_text(newline="")` plus `write_text(newline="")`.

### B. A UTF-8 BOM swallows the first heading

Responsible task: #15 (`md_toc/cli.py` decoding) or #14 (parser).

`read_text(encoding="utf-8")` leaves `﻿` on the first character, so
`_ATX_RE`'s `^#` no longer matches and the document's first heading silently
disappears. The PRD assumes UTF-8 input and a BOM is valid UTF-8.

```
$ printf '\xef\xbb\xbf# Title\n\n## Alpha\n' > bom.md
$ python3 -m md_toc bom.md
- [Alpha](#alpha)
```

Likely fix: `encoding="utf-8-sig"` on read.

### C. An ATX heading inside the marker region breaks idempotency

Responsible task: #15 (headings are extracted from the whole document,
including the region that is about to be overwritten).

`extract_headings` runs over the entire file, so a heading living between the
markers is counted, written into the generated TOC, and then destroyed by the
splice that replaces the region. Run two therefore produces a different TOC.

```
$ printf '# A\n\n<!-- toc -->\n# Ghost\n<!-- /toc -->\n\n## B\n' > inside.md
$ python3 -m md_toc --in-place inside.md   # region becomes: - [A](#a) / - [Ghost](#ghost) /   - [B](#b)
$ python3 -m md_toc --in-place inside.md   # region becomes: - [A](#a) /   - [B](#b)
```

Lowest severity of the three — the input is unusual, and the file converges
after the second run. Noted for completeness.

## Acceptance criteria

All twelve criteria in `17.md` are covered by a passing test. Criterion 4
("bytes before and after the markers identical") passes for the LF corpus and
fails for CRLF input; see defect A.
