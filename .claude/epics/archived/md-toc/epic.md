---
name: md-toc
status: completed
created: 2026-08-11T06:35:52Z
updated: 2026-08-11T07:54:54Z
progress: 90%
prd: .claude/prds/md-toc.md
github: https://github.com/Sut103/claude-playground/issues/11
---

# Epic: md-toc

## Overview

Implement `md-toc` as a small Python 3 package with a stdlib-only `unittest` suite. The tool reads one Markdown file, extracts its ATX headings while skipping fenced code blocks, renders a nested Markdown list with GitHub-compatible anchors, and either prints it, injects it between marker comments, or checks the embedded copy for staleness.

## Architecture Decisions

- **Language: Python 3.11, standard library only.** The PRD forbids third-party runtime dependencies; `argparse`, `re`, and `pathlib` cover everything needed. `pytest` is absent from the environment, so tests use `unittest`, which is also stdlib — the constraint and the environment agree.
- **Line-based parser rather than a Markdown AST.** Only ATX headings and fenced-code state are in scope. A scanner tracking a single "inside fence" boolean is sufficient and avoids pulling in a parser dependency.
- **Pure core, thin I/O shell.** Heading extraction, slug generation, and TOC rendering are pure functions over strings; file reading and writing live only in the CLI entry point. This makes every acceptance criterion testable without touching the filesystem, and makes `--check` a string comparison rather than a separate code path.
- **One module per unit, not one file.** The core units live in separate modules under a `md_toc/` package rather than a single `md_toc.py`. A single file would put every task in conflict on the same path, which would make the `conflicts_with` metadata vacuous and the parallel pairs unrunnable. File-level separation is what makes concurrent streams possible.
- **`--check` and `--in-place` share one "render and splice" routine.** Both need the file's content with a freshly generated TOC spliced between the markers; one writes the result, the other compares it. A single implementation makes idempotency and check-mode agreement structural rather than something to keep in sync by hand.
- **Fence tracking wins over heading detection.** A `#` inside a fenced block is never a heading, so the fence state is evaluated first on every line.

## Technical Approach

### Frontend Components

No UI. The command-line surface is the interface:

```
md-toc <file> [--in-place] [--check] [--min-level N] [--max-level N]
```

`argparse` handles parsing and usage errors. `--in-place` and `--check` are mutually exclusive. Exit codes are centralized in the entry point: 0 success, 1 stale TOC under `--check`, 2 usage or I/O error.

### Backend Services

An `md_toc/` package, one module per unit so tasks can proceed without path conflicts:

- `md_toc/parser.py` — `extract_headings(text, min_level, max_level) -> list[Heading]`, a line scanner with fenced-code suppression, returning level and title text.
- `md_toc/slug.py` — `slugify(title, seen) -> str`, the GitHub anchor dialect: lowercase, strip punctuation, spaces to hyphens, `-1`/`-2` suffixes for duplicates, with `seen` carrying occurrence counts.
- `md_toc/render.py` — `render_toc(headings) -> str`, a nested list with two spaces of indent per level below the shallowest heading present.
- `md_toc/splice.py` — `splice_toc(text, toc) -> str`, replacing content between `<!-- toc -->` and `<!-- /toc -->` and raising a marker-specific error when they are absent.
- `md_toc/cli.py` — `argparse` wiring, file I/O, and the exit-code contract; the only module that touches the filesystem.

### Infrastructure

No services, no deployment. `tests/` holds the `unittest` suite plus Markdown fixtures, one test module per source module so test files do not collide either. The suite runs via `python3 -m unittest discover`. `md_toc/__main__.py` makes `python3 -m md_toc` the entry point.

## Implementation Strategy

Land the pure core before the I/O shell, so the CLI is assembled from pieces that are already covered by tests. The parser and the slug generator have no dependency on each other and are the natural parallel pair; the renderer joins them; the two file-mutating modes then sit on top of the shared splice routine. Acceptance tests come last because they exercise the assembled CLI.

Risk is concentrated in two places: the anchor dialect (duplicate-heading disambiguation is the part most likely to diverge from GitHub) and idempotency of `--in-place`. Both get dedicated tests rather than being folded into the end-to-end pass.

## Task Breakdown Preview

| # | Task | Owns | Depends on | Parallel |
|---|---|---|---|---|
| 001 | Package scaffold, `Heading` type, exit-code constants | `md_toc/__init__.py`, `md_toc/types.py` | — | no |
| 002 | `extract_headings` with fenced-code-block suppression and level bounds | `md_toc/parser.py` | 001 | yes |
| 003 | `slugify` implementing the GitHub anchor dialect with duplicate disambiguation | `md_toc/slug.py` | 001 | yes |
| 004 | `render_toc` nested-list rendering with correct indentation and links | `md_toc/render.py` | 002, 003 | no |
| 005 | `splice_toc` with marker handling and idempotency | `md_toc/splice.py` | 004 | yes |
| 006 | CLI wiring: flags, `--in-place`, `--check`, exit codes | `md_toc/cli.py`, `md_toc/__main__.py` | 004 | yes |
| 007 | Fixtures and end-to-end acceptance tests for all three user stories | `tests/fixtures/`, `tests/test_acceptance.py` | 005, 006 | no |

Seven tasks, within the ≤10 ceiling. Each task owns a disjoint set of paths, so no `conflicts_with` entries are needed. Tasks 002/003 form the first parallel pair, 005/006 the second.

## Dependencies

- Python 3.11 with `argparse`, `re`, `pathlib`, `unittest` — all present in the environment.
- Git, for the `epic/md-toc` branch and the `../epic-md-toc/` worktree the Execute phase creates.
- GitHub API access for the Sync phase, to turn this epic and its tasks into issues.

No dependency on other epics or on external teams.

## Success Criteria (Technical)

- Every acceptance criterion in the three PRD user stories is covered by at least one automated test.
- `python3 -m unittest discover` passes with zero failures.
- A file processed twice with `--in-place` is byte-identical after the second run.
- `--check` returns 0 on a fresh fixture and 1 on a deliberately staled one.
- Content outside the TOC markers is byte-for-byte preserved by `--in-place`.
- No `import` of any non-stdlib module anywhere in the `md_toc/` package.
- A 10,000-line document processes in under one second.

## Estimated Effort

Roughly one focused implementation session. Tasks 001–004 are the bulk of the logic; 005–007 are mechanical once the core is in place. The two parallel pairs mean the critical path is about four sequential steps rather than seven.

## Tasks Created
- [x] #12 - Package scaffold, Heading type, and exit-code constants (parallel: false)
- [x] #14 - Heading extraction with fenced-code suppression (parallel: true)
- [x] #16 - GitHub anchor slug generation (parallel: true)
- [x] #18 - Nested TOC rendering (parallel: false)
- [x] #13 - TOC splicing between marker comments (parallel: true)
- [x] #15 - CLI wiring, flags, and exit-code contract (parallel: true)
- [x] #17 - Fixtures and end-to-end acceptance tests (parallel: false)

Total tasks: 7
Parallel tasks: 4
Sequential tasks: 3
Estimated total effort: 23 hours
