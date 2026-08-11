"""Line scanner that extracts ATX headings from Markdown source text.

This is deliberately not a Markdown AST walk. Only ATX headings (`#` through
`######`) and fenced-code state are in scope, so a single pass carrying one
"inside fence" flag is sufficient and avoids a parser dependency.

Fence state is evaluated before heading detection on every line, because a `#`
inside a fenced block is never a heading.

Standard library only.
"""

import re

from md_toc.types import Heading

__all__ = ["extract_headings"]

#: A fenced-code delimiter: three or more backticks or three or more tildes at
#: the start of the (leading-whitespace-stripped) line. The captured group is
#: the run itself, whose first character identifies the fence kind — a fence
#: opened with one delimiter is never closed by the other.
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")

#: An ATX heading: one to six `#` characters followed by at least one space or
#: tab, then the title. Requiring the space is what keeps `#hashtag` from being
#: read as a heading.
_ATX_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$")

#: A closing `#` run, as in `## Title ##`. It must be preceded by whitespace (or
#: be the whole title) to count, so `## foo#` keeps its trailing `#`.
_CLOSING_HASHES_RE = re.compile(r"(?:^|\s)#+$")


def extract_headings(
    text: str, min_level: int = 1, max_level: int = 6
) -> list[Heading]:
    """Return the ATX headings in `text`, in document order.

    Lines inside fenced code blocks are skipped, including when the fence is
    never closed — an unterminated fence suppresses the rest of the document
    rather than raising. Headings outside the inclusive `min_level` /
    `max_level` bounds are omitted.
    """
    headings: list[Heading] = []
    fence_char = ""

    for line in text.splitlines():
        fence = _FENCE_RE.match(line)
        if fence:
            run = fence.group(1)
            if not fence_char:
                fence_char = run[0]
                continue
            if run[0] == fence_char:
                fence_char = ""
            continue

        if fence_char:
            continue

        match = _ATX_RE.match(line)
        if not match:
            continue

        level = len(match.group(1))
        if not min_level <= level <= max_level:
            continue

        title = match.group(2).strip()
        title = _CLOSING_HASHES_RE.sub("", title).strip()
        headings.append(Heading(level, title))

    return headings
