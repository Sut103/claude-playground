---
issue: 20
stream: Encoding fixes
started: 2026-08-11T07:45:45Z
status: completed
---
## Scope
Fix CRLF preservation (#20) and UTF-8 BOM handling (#21) in the CLI I/O layer.
Files: md_toc/cli.py, tests/test_acceptance.py, tests/test_cli.py

## Progress
- Reproduced both defects against the committed CLI.
- `md_toc/cli.py`: replaced the `read_text` / `write_text` convenience wrappers
  with `_read` / `_write` helpers built on `open()`.
  - `newline=""` on both handles, so no universal-newline translation happens in
    either direction and a CRLF document's `\r\n` survives the round trip (#20).
  - Read as `utf-8-sig`, so a byte-order mark is consumed instead of arriving as
    a literal `U+FEFF` in front of the first `#` and hiding that heading (#21).
  - A three-byte binary peek records whether the source carried a BOM; the write
    encodes as `utf-8-sig` when it did, so `--in-place` puts the mark back. The
    two fixes therefore compose: a CRLF file *with* a BOM round-trips both.
- No module below the CLI was touched; parser, slug, render, splice and types
  are unchanged, as they only ever see already-decoded strings.

## Tests
- `tests/test_acceptance.py`: the `expectedFailure` CRLF reproduction now passes
  as an ordinary test. Its class is renamed `TestKnownDefects` -> `TestFixedDefects`
  and its docstring updated, since it no longer records unfixed defects. Added an
  acceptance-level BOM reproduction alongside it.
- `tests/test_cli.py`: new `TestEncodingAndLineEndings` (12 tests) covering CRLF
  preservation and non-normalization, LF documents unaffected, CRLF idempotency
  and check-mode agreement, BOM documents listing every heading, the BOM not
  leaking into the rendered title, BOM preserved (exactly once) under
  `--in-place`, no BOM invented for a file that lacked one, CRLF+BOM round-tripping
  both, and non-ASCII bodies surviving the `utf-8-sig` decode.
- Confirmed the new tests have teeth: 7 of them fail against the pre-fix `cli.py`.
- Suite: 267 tests with 1 expected failure -> **280 tests, 0 failures, 0 expected
  failures**.

## Known limitation (not in scope of #20/#21)
`splice.py` rebuilds the marker region as `f"{prefix}\n{toc}\n{suffix}"`, with
hard-coded LF. Bytes *outside* the markers are now preserved exactly — which is
what both issues' acceptance criteria require — but the region *between* the
markers is emitted with LF even in a CRLF document. Two consequences:

- After `--in-place`, a CRLF file has CRLF outside the markers and LF inside.
- `--check` on a hand-written CRLF file whose TOC region still uses CRLF reports
  stale once, because in-place would rewrite those endings. Issue #20's prose
  says check mode was previously unaffected; that was true only because it
  compared two normalized strings, i.e. it was blind to the corruption the same
  read caused. Once the file has been through `--in-place` once, check and
  in-place agree and both are byte-idempotent (pinned by
  `test_crlf_document_is_idempotent_after_the_first_run`).

Making the marker region itself honour the document's line ending means changing
`splice.py`, which this stream does not own. Worth a follow-up issue if full
CRLF fidelity inside the region is wanted.
