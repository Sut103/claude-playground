"""Nested Markdown table-of-contents rendering.

Turns the parser's `Heading` list into the artifact users actually see: a
bullet list, one line per heading, each entry linking to the heading's anchor.

Indentation is *relative*. The shallowest level present in the supplied
headings is the baseline and renders flush left, with two spaces added per
level below it. A README that reserves `#` for its title therefore gets a TOC
starting at column zero rather than pre-indented one level too deep.

This module owns the single `seen` dict for the document and threads it through
every `slugify` call, so duplicate headings disambiguate in document order. A
fresh dict per heading would silently point every duplicate at the same anchor.

Standard library only.
"""

from md_toc.slug import slugify
from md_toc.types import Heading

__all__ = ["render_toc"]

#: Indentation added per heading level below the shallowest level present.
_INDENT = "  "


def render_toc(headings: list[Heading]) -> str:
    """Return the nested Markdown TOC for `headings`, in document order.

    Each entry has the form `- [Title](#slug)`, indented by `_INDENT` once per
    level below the shallowest heading present, so the shallowest renders at
    zero indentation regardless of whether the document starts at `#` or `##`.
    A skipped level indents by the full level difference rather than collapsing.

    The link text keeps the heading's original casing and punctuation; only the
    anchor is slugified. Duplicate titles receive `-1` / `-2` suffixed anchors
    because one `seen` dict is shared across the whole render.

    An empty list renders as `""`. The result is newline-joined with no
    trailing newline, leaving surrounding blank lines to the splice routine.
    """
    if not headings:
        return ""

    base = min(heading.level for heading in headings)
    seen: dict[str, int] = {}

    return "\n".join(
        f"{_INDENT * (heading.level - base)}"
        f"- [{heading.title}](#{slugify(heading.title, seen)})"
        for heading in headings
    )
