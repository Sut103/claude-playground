"""Command-line shell for md-toc.

This is the only module in the package that touches the filesystem. It reads
the target file, runs the pure core (parser -> renderer -> splicer), and then
prints, writes, or compares depending on the flags.

`--in-place` and `--check` are the same computation with different endings:
both splice a freshly rendered TOC into the file's text. One writes the result,
the other compares it against what was read. Sharing the splice call is what
makes check-mode agreement with in-place mode structural — check can never
disagree with what in-place would have produced, because it asks the same
question.

Exit codes are centralized here: `EXIT_OK` on success, `EXIT_STALE` for a stale
TOC under `--check`, `EXIT_ERROR` for usage and I/O errors and for a document
missing its marker comments.

Standard library only.
"""

import argparse
import sys
from pathlib import Path

from md_toc.parser import extract_headings
from md_toc.render import render_toc
from md_toc.splice import TOC_END, TOC_START, MarkerError, splice_toc
from md_toc.types import EXIT_ERROR, EXIT_OK, EXIT_STALE

__all__ = ["build_parser", "main"]

#: Prefix on every diagnostic, so stderr identifies the tool in CI logs.
_PROG = "md-toc"


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the `md-toc` command.

    `--in-place` and `--check` live in a mutually exclusive group, so argparse
    itself rejects the combination with its own exit status 2 — matching the
    required usage-error code without a special case in `main`.
    """
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="Generate or verify a Markdown table of contents.",
    )
    parser.add_argument("file", help="Markdown file to read")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--in-place",
        action="store_true",
        help=f"rewrite the region between {TOC_START} and {TOC_END} in FILE",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the embedded table of contents is stale; never write",
    )

    parser.add_argument(
        "--min-level", type=int, default=1, help="shallowest heading level (default 1)"
    )
    parser.add_argument(
        "--max-level", type=int, default=6, help="deepest heading level (default 6)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its exit code.

    Returning the code rather than calling `sys.exit` lets tests assert on the
    integer directly; `md_toc.__main__` supplies the `sys.exit` at the edge.
    """
    args = build_parser().parse_args(argv)
    path = Path(args.file)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _error(f"cannot read {args.file}: {exc}")

    toc = render_toc(extract_headings(text, args.min_level, args.max_level))

    if not (args.in_place or args.check):
        print(toc)
        return EXIT_OK

    try:
        updated = splice_toc(text, toc)
    except MarkerError as exc:
        return _error(
            f"{args.file}: {exc} "
            f"(expected the markers {TOC_START} and {TOC_END}, in that order)"
        )

    if args.check:
        if updated == text:
            return EXIT_OK
        print(f"{_PROG}: {args.file}: table of contents is stale")
        return EXIT_STALE

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return _error(f"cannot write {args.file}: {exc}")
    return EXIT_OK


def _error(message: str) -> int:
    """Report `message` on stderr and return the error exit code."""
    print(f"{_PROG}: {message}", file=sys.stderr)
    return EXIT_ERROR
