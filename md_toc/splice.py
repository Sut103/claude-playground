"""Injection of a rendered TOC between the marker comments in a document.

A pure string-to-string transformation: no filesystem access, no mutation of
its arguments. That is what lets `--in-place` and `--check` share one routine —
one writes the return value, the other compares it against the original.

The result is assembled as `prefix + "\\n" + toc + "\\n" + suffix`, where the
prefix ends with the opening marker and the suffix begins with the closing
marker. Everything outside the markers is carried over as an untouched slice of
the input, so byte-for-byte preservation is structural rather than something
the tests have to police afterwards. Idempotency follows: the renderer is
deterministic, so re-splicing an already-current document reassembles the exact
same bytes and `--check` sees no diff.

Standard library only.
"""

__all__ = ["TOC_START", "TOC_END", "MarkerError", "splice_toc"]

#: Opening marker comment; the prefix handed back to the caller ends here.
TOC_START = "<!-- toc -->"
#: Closing marker comment; the preserved suffix begins here.
TOC_END = "<!-- /toc -->"


class MarkerError(Exception):
    """Raised when the TOC markers are absent or out of order."""


def splice_toc(text: str, toc: str) -> str:
    """Return `text` with the region between the TOC markers replaced by `toc`.

    Only the first marker pair is treated as the TOC region; marker-looking
    text after the closing marker is body content and is left alone. The marker
    lines themselves survive in the output, so the document can be spliced
    again, and the rebuilt region is `toc` surrounded by one newline on each
    side — which is exactly what the previous splice wrote, making a second run
    on unchanged headings a no-op.

    Raises `MarkerError` if either marker is missing or if the closing marker
    appears before the opening one; the document is never partially rewritten.
    """
    start = text.find(TOC_START)
    end = text.find(TOC_END)

    if start == -1 or end == -1 or end < start:
        raise MarkerError(
            f"document must contain {TOC_START} followed by {TOC_END}"
        )

    prefix = text[: start + len(TOC_START)]
    suffix = text[end:]

    return f"{prefix}\n{toc}\n{suffix}"
