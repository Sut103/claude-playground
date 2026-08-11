"""md_toc — generate and check Markdown tables of contents.

Re-exports the shared vocabulary from `md_toc.types` so downstream modules may
import `Heading` and the exit-code constants from either location.

Standard library only.
"""

from md_toc.types import EXIT_ERROR, EXIT_OK, EXIT_STALE, Heading

__all__ = ["Heading", "EXIT_OK", "EXIT_STALE", "EXIT_ERROR"]
