---
issue: 15
stream: CLI and tests
started: 2026-08-11T07:32:32Z
completed: 2026-08-11T07:38:00Z
status: completed
---
## Scope
argparse CLI, --in-place / --check, exit-code contract.
Files: md_toc/cli.py, md_toc/__main__.py, tests/test_cli.py

## Progress
- `md_toc/cli.py`: `build_parser()` and `main(argv=None) -> int`.
  - `md-toc <file> [--in-place] [--check] [--min-level N] [--max-level N]`.
  - `--in-place` / `--check` in an `add_mutually_exclusive_group()`, so argparse
    reports the conflict as its own usage error (status 2) before any file I/O.
  - Default mode renders to stdout and never opens the file for writing.
  - `--in-place` and `--check` share one `splice_toc(text, toc)` call, so check
    mode cannot disagree with what in-place would have written.
  - Exit codes from `md_toc.types`: EXIT_OK / EXIT_STALE / EXIT_ERROR. `OSError`
    on read or write and `MarkerError` map to EXIT_ERROR with a stderr message
    naming the file (and, for MarkerError, both expected markers).
  - The only module in the package that touches the filesystem.
- `md_toc/__main__.py`: `sys.exit(main())` shim for `python3 -m md_toc`.
- `tests/test_cli.py`: 40 tests over real files in `tempfile.TemporaryDirectory`,
  asserting return codes and on-disk bytes — stdout mode leaves the file
  byte-identical, in-place preserves everything outside the markers and is
  idempotent across two runs, check returns 0/1 and never writes on either
  outcome, level bounds apply in all three modes, and the module entry point
  propagates each exit code.

## Verification
- `python3 -m unittest tests.test_cli -v` — 40 tests, OK.
- `python3 -m unittest discover` — 234 tests, OK (whole package green,
  including issue #13's tests/test_splice.py).

## Notes
- Depended on `md_toc.splice` (issue #13, concurrent). It was already on disk
  when the CLI was ready to run, so no wait time was spent polling; the code was
  written against the agreed contract regardless.
