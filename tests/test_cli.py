"""Tests for md_toc.cli — flags, mode dispatch, and the exit-code contract.

Every test drives `main(argv)` against a real file in a `TemporaryDirectory`
and asserts on both the returned integer and the on-disk bytes. Reading the
bytes back is the point: the PRD's safety guarantee is that no invocation
modifies a file unless `--in-place` was passed, and only the file itself can
witness that.

The rendered TOC text is not hand-written into the assertions for the splice
modes; those compare against what the core actually emits, so the tests pin the
CLI's wiring rather than restating the renderer's format.
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from md_toc.cli import build_parser, main
from md_toc.parser import extract_headings
from md_toc.render import render_toc
from md_toc.splice import TOC_END, TOC_START
from md_toc.types import EXIT_ERROR, EXIT_OK, EXIT_STALE

#: A document with an empty marker region awaiting its first splice.
DOC = f"""# Title

{TOC_START}
{TOC_END}

## Alpha

Body text.

### Beta

## Gamma
"""

#: The same headings with no marker comments anywhere.
DOC_WITHOUT_MARKERS = """# Title

## Alpha

### Beta
"""


class CLITestCase(unittest.TestCase):
    """Base fixture: a temporary directory plus helpers to run the CLI."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, text=DOC, name="doc.md"):
        """Write `text` to a file in the temp dir and return its path."""
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_cli(self, *argv):
        """Run `main` with `argv`, returning (code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def expected_toc(self, text=DOC, **bounds):
        """The TOC the core produces for `text`, as the CLI would render it."""
        return render_toc(extract_headings(text, **bounds))


class TestStdoutMode(CLITestCase):
    def test_prints_the_rendered_toc(self):
        path = self.write()
        code, out, err = self.run_cli(str(path))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(out, self.expected_toc() + "\n")
        self.assertEqual(err, "")

    def test_output_is_a_nested_markdown_list(self):
        path = self.write()
        _, out, _ = self.run_cli(str(path))
        self.assertEqual(
            out.splitlines(),
            [
                "- [Title](#title)",
                "  - [Alpha](#alpha)",
                "    - [Beta](#beta)",
                "  - [Gamma](#gamma)",
            ],
        )

    def test_leaves_the_file_byte_for_byte_unmodified(self):
        path = self.write()
        before = path.read_bytes()
        self.run_cli(str(path))
        self.assertEqual(path.read_bytes(), before)

    def test_does_not_require_markers(self):
        path = self.write(DOC_WITHOUT_MARKERS)
        before = path.read_bytes()
        code, out, err = self.run_cli(str(path))
        self.assertEqual(code, EXIT_OK)
        self.assertIn("- [Title](#title)", out)
        self.assertEqual(err, "")
        self.assertEqual(path.read_bytes(), before)


class TestInPlaceMode(CLITestCase):
    def test_writes_the_toc_between_the_markers(self):
        path = self.write()
        code, out, err = self.run_cli(str(path), "--in-place")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")
        written = path.read_text(encoding="utf-8")
        region = written.split(TOC_START, 1)[1].split(TOC_END, 1)[0]
        self.assertIn("- [Title](#title)", region)
        self.assertIn("  - [Gamma](#gamma)", region)

    def test_preserves_everything_outside_the_markers(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        written = path.read_text(encoding="utf-8")
        self.assertTrue(written.startswith("# Title\n\n" + TOC_START))
        self.assertTrue(written.endswith(DOC.split(TOC_END, 1)[1]))
        self.assertIn("Body text.", written)

    def test_markers_survive_so_the_file_can_be_spliced_again(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        written = path.read_text(encoding="utf-8")
        self.assertIn(TOC_START, written)
        self.assertIn(TOC_END, written)

    def test_second_run_is_byte_identical(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        after_first = path.read_bytes()
        code, _, _ = self.run_cli(str(path), "--in-place")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(path.read_bytes(), after_first)

    def test_prints_nothing_to_stdout(self):
        path = self.write()
        _, out, _ = self.run_cli(str(path), "--in-place")
        self.assertEqual(out, "")

    def test_refreshes_a_stale_toc(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        path.write_text(
            path.read_text(encoding="utf-8") + "\n## Delta\n", encoding="utf-8"
        )
        self.run_cli(str(path), "--in-place")
        self.assertIn("- [Delta](#delta)", path.read_text(encoding="utf-8"))


class TestCheckMode(CLITestCase):
    def test_fresh_file_exits_ok(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        code, _, err = self.run_cli(str(path), "--check")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(err, "")

    def test_stale_file_exits_stale(self):
        path = self.write()
        code, _, _ = self.run_cli(str(path), "--check")
        self.assertEqual(code, EXIT_STALE)

    def test_stale_message_names_the_file(self):
        path = self.write()
        _, out, _ = self.run_cli(str(path), "--check")
        self.assertIn(str(path), out)

    def test_never_writes_when_stale(self):
        path = self.write()
        before = path.read_bytes()
        code, _, _ = self.run_cli(str(path), "--check")
        self.assertEqual(code, EXIT_STALE)
        self.assertEqual(path.read_bytes(), before)

    def test_never_writes_when_fresh(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        before = path.read_bytes()
        self.run_cli(str(path), "--check")
        self.assertEqual(path.read_bytes(), before)

    def test_goes_stale_when_a_heading_is_added(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        path.write_text(
            path.read_text(encoding="utf-8") + "\n## Delta\n", encoding="utf-8"
        )
        code, _, _ = self.run_cli(str(path), "--check")
        self.assertEqual(code, EXIT_STALE)

    def test_agrees_with_in_place_after_it_runs(self):
        path = self.write()
        self.run_cli(str(path), "--in-place")
        self.assertEqual(self.run_cli(str(path), "--check")[0], EXIT_OK)


class TestLevelBounds(CLITestCase):
    def test_min_level_drops_shallower_headings(self):
        path = self.write()
        _, out, _ = self.run_cli(str(path), "--min-level", "2")
        self.assertNotIn("[Title]", out)
        self.assertIn("- [Alpha](#alpha)", out)

    def test_max_level_drops_deeper_headings(self):
        path = self.write()
        _, out, _ = self.run_cli(str(path), "--max-level", "2")
        self.assertNotIn("[Beta]", out)
        self.assertIn("  - [Alpha](#alpha)", out)

    def test_bounds_can_select_a_single_level(self):
        path = self.write()
        _, out, _ = self.run_cli(str(path), "--min-level", "2", "--max-level", "2")
        self.assertEqual(out.splitlines(), ["- [Alpha](#alpha)", "- [Gamma](#gamma)"])

    def test_bounds_apply_in_place(self):
        path = self.write()
        self.run_cli(str(path), "--in-place", "--max-level", "2")
        written = path.read_text(encoding="utf-8")
        self.assertNotIn("[Beta]", written)
        self.assertIn("- [Alpha](#alpha)", written)

    def test_bounds_apply_in_check(self):
        path = self.write()
        self.run_cli(str(path), "--in-place", "--max-level", "2")
        self.assertEqual(
            self.run_cli(str(path), "--check", "--max-level", "2")[0], EXIT_OK
        )
        self.assertEqual(self.run_cli(str(path), "--check")[0], EXIT_STALE)


class TestUsageErrors(CLITestCase):
    def test_in_place_and_check_together_are_rejected(self):
        path = self.write()
        before = path.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main([str(path), "--in-place", "--check"])
        self.assertEqual(caught.exception.code, EXIT_ERROR)
        self.assertEqual(path.read_bytes(), before)

    def test_missing_file_argument_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main([])
        self.assertEqual(caught.exception.code, EXIT_ERROR)

    def test_non_integer_level_is_rejected(self):
        path = self.write()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main([str(path), "--min-level", "deep"])
        self.assertEqual(caught.exception.code, EXIT_ERROR)


class TestIOErrors(CLITestCase):
    def test_nonexistent_path_exits_error(self):
        missing = self.dir / "nope.md"
        code, out, err = self.run_cli(str(missing))
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn(str(missing), err)

    def test_directory_argument_exits_error(self):
        code, out, err = self.run_cli(str(self.dir))
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertNotEqual(err, "")

    def test_nonexistent_path_under_check_exits_error_not_stale(self):
        code, _, _ = self.run_cli(str(self.dir / "nope.md"), "--check")
        self.assertEqual(code, EXIT_ERROR)


class TestMissingMarkers(CLITestCase):
    def test_in_place_exits_error(self):
        path = self.write(DOC_WITHOUT_MARKERS)
        code, out, _ = self.run_cli(str(path), "--in-place")
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")

    def test_in_place_leaves_the_file_unmodified(self):
        path = self.write(DOC_WITHOUT_MARKERS)
        before = path.read_bytes()
        self.run_cli(str(path), "--in-place")
        self.assertEqual(path.read_bytes(), before)

    def test_message_names_both_expected_markers(self):
        path = self.write(DOC_WITHOUT_MARKERS)
        _, _, err = self.run_cli(str(path), "--in-place")
        self.assertIn(TOC_START, err)
        self.assertIn(TOC_END, err)

    def test_check_exits_error_not_stale(self):
        path = self.write(DOC_WITHOUT_MARKERS)
        code, _, _ = self.run_cli(str(path), "--check")
        self.assertEqual(code, EXIT_ERROR)

    def test_closing_marker_only_exits_error(self):
        path = self.write(f"# Title\n\n{TOC_END}\n\n## Alpha\n")
        code, _, err = self.run_cli(str(path), "--in-place")
        self.assertEqual(code, EXIT_ERROR)
        self.assertNotEqual(err, "")

    def test_reversed_markers_exit_error(self):
        path = self.write(f"# Title\n\n{TOC_END}\n{TOC_START}\n\n## Alpha\n")
        before = path.read_bytes()
        code, _, _ = self.run_cli(str(path), "--in-place")
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(path.read_bytes(), before)


class TestParser(unittest.TestCase):
    def test_defaults(self):
        args = build_parser().parse_args(["doc.md"])
        self.assertEqual(
            (args.file, args.in_place, args.check, args.min_level, args.max_level),
            ("doc.md", False, False, 1, 6),
        )

    def test_flags_parse(self):
        args = build_parser().parse_args(
            ["doc.md", "--in-place", "--min-level", "2", "--max-level", "4"]
        )
        self.assertTrue(args.in_place)
        self.assertEqual((args.min_level, args.max_level), (2, 4))


class TestModuleEntryPoint(CLITestCase):
    """`python3 -m md_toc FILE` must behave like the console invocation."""

    ROOT = Path(__file__).resolve().parents[1]

    def run_module(self, *argv):
        return subprocess.run(
            [sys.executable, "-m", "md_toc", *argv],
            cwd=self.ROOT,
            capture_output=True,
            text=True,
        )

    def test_stdout_matches_main(self):
        path = self.write()
        result = self.run_module(str(path))
        self.assertEqual(result.returncode, EXIT_OK)
        self.assertEqual(result.stdout, self.run_cli(str(path))[1])

    def test_propagates_the_stale_exit_code(self):
        path = self.write()
        self.assertEqual(self.run_module(str(path), "--check").returncode, EXIT_STALE)

    def test_propagates_the_error_exit_code(self):
        result = self.run_module(str(self.dir / "nope.md"))
        self.assertEqual(result.returncode, EXIT_ERROR)
        self.assertEqual(result.stdout, "")

    def test_in_place_writes_the_file(self):
        path = self.write()
        self.assertEqual(self.run_module(str(path), "--in-place").returncode, EXIT_OK)
        self.assertEqual(self.run_cli(str(path), "--check")[0], EXIT_OK)


if __name__ == "__main__":
    unittest.main()
