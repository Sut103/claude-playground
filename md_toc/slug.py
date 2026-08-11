"""GitHub anchor slug generation.

Converts a heading's title text into the fragment identifier GitHub would
generate for it, so a TOC entry links to a live anchor rather than a dead one.

Duplicate headings are disambiguated with a numeric suffix (`-1`, `-2`, ...) in
document order. That state cannot live inside the function, so the caller owns a
`seen` dict — one per document — mapping base slug to occurrence count, which
`slugify` mutates in place.

Imports nothing from the rest of the package. Standard library only.
"""

import re

__all__ = ["slugify"]

#: Characters that survive normalization: word characters (Unicode letters,
#: digits, underscore), whitespace, and hyphens. Everything else is stripped
#: rather than replaced, so "What's New?" becomes "whats-new".
_STRIP_RE = re.compile(r"[^\w\s-]")

#: Runs of whitespace collapse to a single hyphen.
_WHITESPACE_RE = re.compile(r"\s+")


def slugify(title: str, seen: dict) -> str:
    """Return the GitHub anchor slug for `title`, disambiguated via `seen`.

    Lowercases the title, strips punctuation, and turns whitespace runs into
    single hyphens. The first occurrence of a base slug is returned unchanged;
    the second gets `-1`, the third `-2`, and so on.

    `seen` maps base slug to occurrence count and is mutated in place. Pass a
    fresh empty dict per document so numbering never leaks between documents.
    """
    base = _WHITESPACE_RE.sub("-", _STRIP_RE.sub("", title.lower()).strip())

    if base not in seen:
        seen[base] = 0
        return base

    seen[base] += 1
    return f"{base}-{seen[base]}"
