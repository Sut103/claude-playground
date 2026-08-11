"""Shared vocabulary for the md_toc package.

Defines the `Heading` value type produced by the parser and consumed by the
renderer, plus the exit-code constants that define the CLI's contract with CI.

Standard library only.
"""

from dataclasses import dataclass

__all__ = ["Heading", "EXIT_OK", "EXIT_STALE", "EXIT_ERROR"]


@dataclass(frozen=True)
class Heading:
    """A single ATX heading.

    `level` is the heading depth, 1 through 6. `title` is the heading's raw
    text with the leading `#` run and surrounding whitespace already stripped;
    normalization is the parser's responsibility, not this type's.
    """

    level: int
    title: str


#: Success.
EXIT_OK = 0
#: Stale TOC detected in check mode.
EXIT_STALE = 1
#: Usage or I/O error.
EXIT_ERROR = 2
