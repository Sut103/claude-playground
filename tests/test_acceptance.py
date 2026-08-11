"""End-to-end acceptance tests for the three PRD user stories.

Every other test module in this suite exercises one module in isolation. This
one is the only place the assembled pipeline runs against real files on disk:
argv in, parsing, slugging, rendering, splicing, and writing out.

Each test names the PRD acceptance criterion it stands for rather than an
implementation detail, so the suite doubles as the epic's evidence. Fixtures
live in `tests/fixtures/` and are copied into a per-test temporary directory
before any mutating run, so the committed corpus stays pristine and the suite
is re-runnable without a `git checkout` in between.

Byte-level assertions use `Path.read_bytes()` rather than `read_text()`, so a
line-ending or trailing-newline regression is caught rather than normalized
away by the comparison itself.

Standard library only.
"""

import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from md_toc.cli import main
from md_toc.splice import TOC_END, TOC_START
from md_toc.types import EXIT_ERROR, EXIT_OK, EXIT_STALE

#: Directory holding the committed Markdown corpus. Never written to.
FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Repository root, so a subprocess run can import the package from source.
REPO_ROOT = FIXTURES.parent.parent

#: The TOC `basic.md` must produce: one entry per heading, two spaces of
#: indentation per level below the shallowest, each linking to its anchor.
BASIC_TOC = """\
- [md-toc Demo Document](#md-toc-demo-document)
  - [Installation](#installation)
    - [Requirements](#requirements)
    - [From Source](#from-source)
  - [Usage](#usage)
    - [Generating a TOC](#generating-a-toc)
      - [Flags](#flags)
  - [What's New?](#whats-new)"""


class AcceptanceTestCase(unittest.TestCase):
    """Shared fixture copying and CLI invocation for the acceptance suite."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workdir = Path(self._tmp.name)

    def copy_fixture(self, name: str) -> Path:
        """Copy fixture `name` into this test's temp dir and return the copy.

        Mutating runs therefore never reach the committed corpus. The copy is
        made with `shutil.copy`, so its bytes match the fixture exactly.
        """
        source = FIXTURES / name
        self.assertTrue(source.is_file(), f"missing fixture: {source}")
        destination = self.workdir / name
        shutil.copy(source, destination)
        self.assertEqual(destination.read_bytes(), source.read_bytes())
        return destination

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        """Run `md_toc.cli.main` with `argv`, returning (code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def assertUnchanged(self, path: Path, before: bytes, message: str) -> None:
        """Assert `path` still holds `before`, byte for byte."""
        self.assertEqual(path.read_bytes(), before, message)

    @staticmethod
    def outside_markers(data: bytes) -> tuple[bytes, bytes]:
        """Return the bytes before the opening marker and after the closing one."""
        prefix, _, rest = data.partition(TOC_START.encode("utf-8"))
        _, _, suffix = rest.partition(TOC_END.encode("utf-8"))
        return prefix, suffix


class TestStory1GenerateToStdout(AcceptanceTestCase):
    """Story 1: generate a TOC for an existing document."""

    def test_prints_nested_markdown_list_to_stdout(self) -> None:
        """`md-toc FILE` prints the nested list, two spaces per level."""
        path = self.copy_fixture("basic.md")

        code, out, err = self.run_cli(str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertEqual(out, BASIC_TOC + "\n")

    def test_nesting_depth_reflects_heading_level(self) -> None:
        """Indentation is two spaces per level below the shallowest heading."""
        path = self.copy_fixture("basic.md")

        _, out, _ = self.run_cli(str(path))
        indents = {
            line.lstrip("- ["): len(line) - len(line.lstrip(" "))
            for line in out.splitlines()
        }

        self.assertEqual(indents["md-toc Demo Document](#md-toc-demo-document)"], 0)
        self.assertEqual(indents["Installation](#installation)"], 2)
        self.assertEqual(indents["Requirements](#requirements)"], 4)
        self.assertEqual(indents["Flags](#flags)"], 6)

    def test_every_entry_links_to_the_heading_anchor(self) -> None:
        """Each line is `- [Title](#slug)` with the slugified anchor."""
        path = self.copy_fixture("basic.md")

        _, out, _ = self.run_cli(str(path))

        for line in out.splitlines():
            entry = line.lstrip()
            self.assertTrue(entry.startswith("- ["), entry)
            title = entry[3 : entry.index("](#")]
            anchor = entry[entry.index("](#") + 3 : -1]
            self.assertTrue(anchor, f"empty anchor for {title!r}")
            self.assertNotIn(" ", anchor, f"unslugified anchor for {title!r}")

    def test_shallowest_heading_h2_renders_flush_left(self) -> None:
        """A document reserving `#` for nothing still starts at column zero."""
        path = self.copy_fixture("h2_only.md")

        code, out, _ = self.run_cli(str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(
            out,
            "- [Alpha](#alpha)\n"
            "  - [Alpha Detail](#alpha-detail)\n"
            "    - [Alpha Detail Detail](#alpha-detail-detail)\n"
            "- [Beta](#beta)\n"
            "  - [Beta Detail](#beta-detail)\n",
        )

    def test_source_file_is_not_modified(self) -> None:
        """Default mode leaves the file byte-for-byte identical."""
        path = self.copy_fixture("basic.md")
        before = path.read_bytes()

        code, _, _ = self.run_cli(str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertUnchanged(path, before, "default mode must not write")

    def test_marker_less_document_still_prints_to_stdout(self) -> None:
        """Markers are only required by the writing modes, not by generation."""
        path = self.copy_fixture("no_markers.md")
        before = path.read_bytes()

        code, out, err = self.run_cli(str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        self.assertIn("- [Document Without Markers](#document-without-markers)", out)
        self.assertUnchanged(path, before, "default mode must not write")


class TestStory2InPlace(AcceptanceTestCase):
    """Story 2: keep a TOC in sync in place."""

    def test_replaces_content_between_the_markers(self) -> None:
        """`--in-place` writes the generated TOC into the marker region."""
        path = self.copy_fixture("stale.md")

        code, out, err = self.run_cli("--in-place", str(path))
        text = path.read_text(encoding="utf-8")
        region = text.split(TOC_START)[1].split(TOC_END)[0]

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out, "")
        self.assertEqual(err, "")
        self.assertEqual(region, "\n- [md-toc Demo Document](#md-toc-demo-document)\n"
                                 "  - [Installation](#installation)\n"
                                 "    - [Requirements](#requirements)\n"
                                 "    - [From Source](#from-source)\n"
                                 "  - [Usage and Examples](#usage-and-examples)\n"
                                 "    - [Generating a TOC](#generating-a-toc)\n"
                                 "      - [Flags](#flags)\n"
                                 "  - [What's New?](#whats-new)\n")

    def test_bytes_outside_the_markers_are_unchanged(self) -> None:
        """Everything before `<!-- toc -->` and after `<!-- /toc -->` survives."""
        path = self.copy_fixture("stale.md")
        before = path.read_bytes()

        code, _, _ = self.run_cli("--in-place", str(path))
        after = path.read_bytes()

        self.assertEqual(code, EXIT_OK)
        self.assertNotEqual(after, before, "the stale fixture should have changed")
        self.assertEqual(self.outside_markers(after), self.outside_markers(before))

    def test_second_run_produces_no_change(self) -> None:
        """Running `--in-place` twice is idempotent."""
        path = self.copy_fixture("stale.md")

        self.assertEqual(self.run_cli("--in-place", str(path))[0], EXIT_OK)
        after_first = path.read_bytes()
        self.assertEqual(self.run_cli("--in-place", str(path))[0], EXIT_OK)

        self.assertUnchanged(path, after_first, "second run must be a no-op")

    def test_already_current_document_is_untouched(self) -> None:
        """`--in-place` on a fresh document rewrites the same bytes."""
        path = self.copy_fixture("basic.md")
        before = path.read_bytes()

        code, _, _ = self.run_cli("--in-place", str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertUnchanged(path, before, "a current TOC must round-trip exactly")

    def test_missing_markers_exit_non_zero_and_do_not_write(self) -> None:
        """The marker-less fixture exits 2, names both markers, stays intact."""
        path = self.copy_fixture("no_markers.md")
        before = path.read_bytes()

        code, out, err = self.run_cli("--in-place", str(path))

        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn(TOC_START, err)
        self.assertIn(TOC_END, err)
        self.assertIn("no_markers.md", err)
        self.assertUnchanged(path, before, "a marker error must not write")

    def test_in_place_then_check_agree(self) -> None:
        """After `--in-place`, `--check` on the same file reports fresh."""
        path = self.copy_fixture("stale.md")

        self.assertEqual(self.run_cli("--in-place", str(path))[0], EXIT_OK)

        self.assertEqual(self.run_cli("--check", str(path))[0], EXIT_OK)

    def test_in_place_and_check_are_mutually_exclusive(self) -> None:
        """argparse rejects the combination with the usage exit code."""
        path = self.copy_fixture("basic.md")
        before = path.read_bytes()

        with self.assertRaises(SystemExit) as raised:
            self.run_cli("--in-place", "--check", str(path))

        self.assertEqual(raised.exception.code, EXIT_ERROR)
        self.assertUnchanged(path, before, "a usage error must not write")


class TestStory3Check(AcceptanceTestCase):
    """Story 3: enforce TOC freshness in CI."""

    def test_fresh_document_exits_zero(self) -> None:
        """`--check` on a current TOC exits 0."""
        path = self.copy_fixture("basic.md")

        code, out, err = self.run_cli("--check", str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_stale_document_exits_one_and_names_the_file(self) -> None:
        """A heading renamed after the TOC was written is detected."""
        path = self.copy_fixture("stale.md")

        code, out, err = self.run_cli("--check", str(path))

        self.assertEqual(code, EXIT_STALE)
        self.assertIn("stale.md", out + err)
        self.assertIn("stale", (out + err).lower())

    def test_check_never_modifies_the_file(self) -> None:
        """Neither the fresh nor the stale path writes."""
        for name, expected in (("basic.md", EXIT_OK), ("stale.md", EXIT_STALE)):
            with self.subTest(fixture=name):
                path = self.copy_fixture(name)
                before = path.read_bytes()

                code, _, _ = self.run_cli("--check", str(path))

                self.assertEqual(code, expected)
                self.assertUnchanged(path, before, "check mode must never write")

    def test_check_on_marker_less_document_errors_without_writing(self) -> None:
        """No markers means no embedded TOC to compare: usage error, no write."""
        path = self.copy_fixture("no_markers.md")
        before = path.read_bytes()

        code, _, err = self.run_cli("--check", str(path))

        self.assertEqual(code, EXIT_ERROR)
        self.assertIn(TOC_START, err)
        self.assertUnchanged(path, before, "check mode must never write")

    def test_every_marked_fixture_is_committed_fresh(self) -> None:
        """The corpus itself is current, so the suite starts from a known state."""
        for name in ("basic.md", "fenced.md", "h2_only.md", "duplicates.md"):
            with self.subTest(fixture=name):
                path = self.copy_fixture(name)

                self.assertEqual(self.run_cli("--check", str(path))[0], EXIT_OK)


class TestFencedCodeBlocks(AcceptanceTestCase):
    """Heading-like lines inside fences never reach the TOC."""

    def test_ghost_headings_are_absent_from_stdout(self) -> None:
        """Neither ``` nor ~~~ fenced content contributes entries."""
        path = self.copy_fixture("fenced.md")

        code, out, _ = self.run_cli(str(path))

        self.assertEqual(code, EXIT_OK)
        for ghost in (
            "Backtick Ghost One",
            "Backtick Ghost Two",
            "Backtick Ghost Six",
            "Tilde Ghost One",
            "Tilde Ghost Three",
            "Nested Tilde Ghost",
            "Nested Backtick Ghost",
        ):
            self.assertNotIn(ghost, out)

    def test_real_headings_around_the_fences_survive(self) -> None:
        """Suppression is scoped to the fence, not the rest of the document."""
        path = self.copy_fixture("fenced.md")

        _, out, _ = self.run_cli(str(path))

        self.assertEqual(out.count("- [Real Heading]"), 3)
        self.assertIn("- [Ending](#ending)", out)

    def test_ghost_headings_are_absent_after_in_place(self) -> None:
        """Suppression survives the whole pipeline, not only the scanner."""
        path = self.copy_fixture("fenced.md")

        code, _, _ = self.run_cli("--in-place", str(path))
        region = path.read_text(encoding="utf-8").split(TOC_START)[1].split(TOC_END)[0]

        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("Ghost", region)


class TestDuplicateAnchors(AcceptanceTestCase):
    """Duplicate heading text yields distinct, numerically suffixed anchors."""

    def test_duplicates_get_numeric_suffixes_end_to_end(self) -> None:
        """Three identical `## Overview` headings produce three anchors."""
        path = self.copy_fixture("duplicates.md")

        code, out, _ = self.run_cli(str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertIn("- [Overview](#overview)", out)
        self.assertIn("- [Overview](#overview-1)", out)
        self.assertIn("- [Overview](#overview-2)", out)

    def test_all_anchors_in_a_document_are_unique(self) -> None:
        """No two entries in a rendered TOC share a fragment identifier."""
        for name in ("duplicates.md", "fenced.md", "basic.md"):
            with self.subTest(fixture=name):
                path = self.copy_fixture(name)

                _, out, _ = self.run_cli(str(path))
                anchors = [
                    line[line.index("](#") + 3 : -1]
                    for line in (raw.strip() for raw in out.splitlines())
                    if line
                ]

                self.assertEqual(len(anchors), len(set(anchors)), anchors)


class TestLevelBounds(AcceptanceTestCase):
    """`--min-level` and `--max-level` bound which headings are included."""

    def test_max_level_drops_deeper_headings(self) -> None:
        """`--max-level 2` keeps the h1 and the h2s only."""
        path = self.copy_fixture("basic.md")

        code, out, _ = self.run_cli("--max-level", "2", str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(
            out,
            "- [md-toc Demo Document](#md-toc-demo-document)\n"
            "  - [Installation](#installation)\n"
            "  - [Usage](#usage)\n"
            "  - [What's New?](#whats-new)\n",
        )

    def test_min_level_drops_shallower_headings_and_rebases_indent(self) -> None:
        """`--min-level 2` drops the h1 and renders the h2s flush left."""
        path = self.copy_fixture("basic.md")

        code, out, _ = self.run_cli("--min-level", "2", "--max-level", "3", str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(
            out,
            "- [Installation](#installation)\n"
            "  - [Requirements](#requirements)\n"
            "  - [From Source](#from-source)\n"
            "- [Usage](#usage)\n"
            "  - [Generating a TOC](#generating-a-toc)\n"
            "- [What's New?](#whats-new)\n",
        )

    def test_empty_bound_renders_nothing_without_error(self) -> None:
        """A range matching no heading is empty output, not a failure."""
        path = self.copy_fixture("basic.md")
        before = path.read_bytes()

        code, out, _ = self.run_cli("--min-level", "5", str(path))

        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out, "\n")
        self.assertUnchanged(path, before, "default mode must not write")

    def test_bounds_apply_to_in_place_writes(self) -> None:
        """The bounded TOC is what lands between the markers."""
        path = self.copy_fixture("basic.md")

        code, _, _ = self.run_cli("--in-place", "--max-level", "2", str(path))
        region = path.read_text(encoding="utf-8").split(TOC_START)[1].split(TOC_END)[0]

        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("Requirements", region)
        self.assertIn("- [Installation](#installation)", region)


class TestInstalledEntryPoint(AcceptanceTestCase):
    """A handful of real `python3 -m md_toc` runs, not just in-process calls."""

    def module_run(self, *argv: str) -> subprocess.CompletedProcess:
        """Run `python3 -m md_toc` with `argv` from the repository root."""
        return subprocess.run(
            [sys.executable, "-m", "md_toc", *argv],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def test_module_run_prints_toc_and_exits_zero(self) -> None:
        """Story 1 through the real entry point."""
        path = self.copy_fixture("basic.md")
        before = path.read_bytes()

        result = self.module_run(str(path))

        self.assertEqual(result.returncode, EXIT_OK, result.stderr)
        self.assertEqual(result.stdout, BASIC_TOC + "\n")
        self.assertUnchanged(path, before, "default mode must not write")

    def test_module_run_check_exits_one_on_stale(self) -> None:
        """Story 3's CI contract holds for a real process exit status."""
        fresh = self.copy_fixture("basic.md")
        stale = self.copy_fixture("stale.md")

        self.assertEqual(self.module_run("--check", str(fresh)).returncode, EXIT_OK)
        stale_result = self.module_run("--check", str(stale))

        self.assertEqual(stale_result.returncode, EXIT_STALE)
        self.assertIn("stale.md", stale_result.stdout + stale_result.stderr)

    def test_module_run_in_place_is_idempotent(self) -> None:
        """Story 2's idempotency holds across two separate processes."""
        path = self.copy_fixture("stale.md")

        self.assertEqual(self.module_run("--in-place", str(path)).returncode, EXIT_OK)
        after_first = path.read_bytes()
        self.assertEqual(self.module_run("--in-place", str(path)).returncode, EXIT_OK)

        self.assertUnchanged(path, after_first, "second process run must be a no-op")

    def test_module_run_missing_markers_exits_two(self) -> None:
        """The marker error reaches the shell as exit status 2 on stderr."""
        path = self.copy_fixture("no_markers.md")
        before = path.read_bytes()

        result = self.module_run("--in-place", str(path))

        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertIn(TOC_START, result.stderr)
        self.assertIn(TOC_END, result.stderr)
        self.assertUnchanged(path, before, "a marker error must not write")

    def test_module_run_missing_file_exits_two(self) -> None:
        """An unreadable path is an I/O error, not a traceback."""
        result = self.module_run(str(self.workdir / "absent.md"))

        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertIn("absent.md", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class TestKnownDefects(AcceptanceTestCase):
    """Reproductions for defects this suite found in the assembled CLI.

    These are recorded rather than fixed: task 17 owns no source module, so the
    repair belongs in a bug issue against the responsible task. They are marked
    `expectedFailure` so `unittest discover` stays green while the reproduction
    stays executable — the day one is fixed it reports as an unexpected success.
    """

    @unittest.expectedFailure
    def test_crlf_document_keeps_its_line_endings_outside_the_markers(self) -> None:
        """DEFECT: `--in-place` rewrites a CRLF document's every line ending.

        `cli.main` reads with `Path.read_text` (universal newlines, so CRLF
        becomes LF) and writes the spliced result back with `Path.write_text`,
        which emits LF on Linux. Story 2 requires the bytes outside the markers
        to be unchanged; on a CRLF file every one of them changes, and the file
        is rewritten wholesale even when its TOC was already current.
        """
        path = self.copy_fixture("crlf.md")
        before = path.read_bytes()
        self.assertIn(b"\r\n", before)

        self.assertEqual(self.run_cli("--in-place", str(path))[0], EXIT_OK)
        after = path.read_bytes()

        self.assertEqual(self.outside_markers(after), self.outside_markers(before))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
