---
issue: 12
stream: Package foundation
started: 2026-08-11T07:05:00Z
status: completed
---

## Scope

Files owned by this stream:

- `md_toc/__init__.py`
- `md_toc/types.py`
- `tests/test_types.py`

Plus `tests/__init__.py`, created to make `python3 -m unittest discover` resolve
the `tests` package cleanly from the repo root.

## Progress

- Created `md_toc/types.py` with a frozen dataclass `Heading` carrying exactly
  two fields, `level: int` and `title: str`, and the three exit-code constants
  `EXIT_OK = 0`, `EXIT_STALE = 1`, `EXIT_ERROR = 2`. `frozen=True` gives value
  equality and hashability, so downstream tests can assert
  `extract_headings(...) == [Heading(1, "Intro")]` directly.
- Created `md_toc/__init__.py`, which makes the package importable and
  re-exports `Heading` plus all three exit-code constants, so tasks 14, 16, and
  18 may import from either `md_toc` or `md_toc.types`.
- Created `tests/__init__.py` (empty) and `tests/test_types.py` with 20 unittest
  cases across five test classes: field names and annotations, value equality
  and hashability, frozen-ness (assignment and deletion both raise
  `FrozenInstanceError`), the three constant values and their distinctness, and
  the package re-export identity.
- Standard library only. The sole non-intra-package imports anywhere are
  `dataclasses` and `unittest`.

## Verification

Run from the repo root:

```
$ python3 -c "import md_toc; print(md_toc.Heading(1, 'x'))"
Heading(level=1, title='x')

$ python3 -m unittest discover
....................
----------------------------------------------------------------------
Ran 20 tests in 0.000s

OK
```

Python 3.11.15.

## Acceptance criteria

All seven criteria in `12.md` are met.

## Out-of-scope items noted, not done

- `.claude/epics/md-toc/12-analysis.md` was referenced in the task assignment
  but does not exist in the worktree. Proceeded from `12.md` alone, which fully
  specifies the work.
- The repo has no `.gitignore`, so `__pycache__/` is untracked but unignored and
  will show up as noise in `git status` after any test run. Removed the
  generated `__pycache__` directories before committing and staged files
  explicitly rather than adding a `.gitignore`, which is outside this stream's
  owned paths. Worth adding at the epic level.

## Commits

- `a6e3427` — Issue #12: add md_toc package with frozen Heading dataclass,
  exit-code constants, and unit tests
