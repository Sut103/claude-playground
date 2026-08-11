"""Tests for md_toc.splice — TOC injection between the marker comments.

Two properties carry the real risk and get their own test classes. The first is
byte-for-byte preservation of everything outside the markers: trailing spaces,
blank runs, CRLF line endings and a missing final newline all have to come back
untouched, so the tests assert on exact strings rather than on stripped or
normalized comparisons. The second is idempotency, which is what `--check`
decides staleness with — a splice that perturbs so much as one space reports
every document as stale forever. Those tests drive the region with output from
the real parser/renderer pipeline, because a hand-written fixture would only
prove that splicing round-trips its own input, not what the renderer emits.
"""

import unittest

from md_toc.parser import extract_headings
from md_toc.render import render_toc
from md_toc.splice import TOC_END, TOC_START, MarkerError, splice_toc


def rendered(text: str) -> str:
    """Return the TOC the real pipeline produces for `text`."""
    return render_toc(extract_headings(text))


class TestReplacement(unittest.TestCase):
    def test_region_between_markers_is_replaced(self):
        document = f"{TOC_START}\nstale entries\n{TOC_END}"
        self.assertEqual(
            splice_toc(document, "- [New](#new)"),
            f"{TOC_START}\n- [New](#new)\n{TOC_END}",
        )

    def test_multi_line_toc_lands_verbatim(self):
        toc = "- [A](#a)\n  - [B](#b)\n- [C](#c)"
        self.assertEqual(
            splice_toc(f"{TOC_START}\nold\n{TOC_END}", toc),
            f"{TOC_START}\n{toc}\n{TOC_END}",
        )

    def test_multi_line_region_is_fully_replaced(self):
        document = f"{TOC_START}\n- [Old](#old)\n- [Older](#older)\n\n{TOC_END}"
        self.assertEqual(
            splice_toc(document, "- [Only](#only)"),
            f"{TOC_START}\n- [Only](#only)\n{TOC_END}",
        )

    def test_empty_toc_leaves_an_empty_region(self):
        self.assertEqual(
            splice_toc(f"{TOC_START}\nold\n{TOC_END}", ""),
            f"{TOC_START}\n\n{TOC_END}",
        )

    def test_input_document_is_not_mutated(self):
        document = f"intro\n{TOC_START}\nold\n{TOC_END}\nbody"
        splice_toc(document, "- [New](#new)")
        self.assertEqual(document, f"intro\n{TOC_START}\nold\n{TOC_END}\nbody")


class TestEmptyRegion(unittest.TestCase):
    def test_adjacent_markers_are_filled(self):
        self.assertEqual(
            splice_toc(f"{TOC_START}{TOC_END}", "- [A](#a)"),
            f"{TOC_START}\n- [A](#a)\n{TOC_END}",
        )

    def test_markers_on_consecutive_lines_are_filled(self):
        document = f"# Title\n\n{TOC_START}\n{TOC_END}\n\n## A\n"
        self.assertEqual(
            splice_toc(document, "- [A](#a)"),
            f"# Title\n\n{TOC_START}\n- [A](#a)\n{TOC_END}\n\n## A\n",
        )

    def test_filling_an_empty_region_is_stable_on_the_second_splice(self):
        once = splice_toc(f"{TOC_START}{TOC_END}", "- [A](#a)")
        self.assertEqual(splice_toc(once, "- [A](#a)"), once)


class TestPreservation(unittest.TestCase):
    """Everything outside the markers must come back byte for byte."""

    def test_prefix_and_suffix_are_preserved(self):
        document = f"# Title\n\nIntro text.\n\n{TOC_START}\nold\n{TOC_END}\n\n## A\n"
        self.assertEqual(
            splice_toc(document, "- [A](#a)"),
            f"# Title\n\nIntro text.\n\n{TOC_START}\n- [A](#a)\n{TOC_END}\n\n## A\n",
        )

    def test_trailing_whitespace_outside_the_markers_survives(self):
        document = f"line with trailing spaces   \n{TOC_START}\nold\n{TOC_END}\ntail\t \n"
        result = splice_toc(document, "- [A](#a)")
        self.assertTrue(result.startswith("line with trailing spaces   \n"))
        self.assertTrue(result.endswith(f"{TOC_END}\ntail\t \n"))

    def test_blank_line_runs_outside_the_markers_survive(self):
        document = f"top\n\n\n\n{TOC_START}\nold\n{TOC_END}\n\n\n\nbottom\n"
        self.assertEqual(
            splice_toc(document, "- [A](#a)"),
            f"top\n\n\n\n{TOC_START}\n- [A](#a)\n{TOC_END}\n\n\n\nbottom\n",
        )

    def test_absent_final_newline_stays_absent(self):
        document = f"{TOC_START}\nold\n{TOC_END}\nlast line without newline"
        result = splice_toc(document, "- [A](#a)")
        self.assertFalse(result.endswith("\n"))
        self.assertEqual(
            result, f"{TOC_START}\n- [A](#a)\n{TOC_END}\nlast line without newline"
        )

    def test_present_final_newline_stays_present(self):
        document = f"{TOC_START}\nold\n{TOC_END}\ntail\n"
        self.assertTrue(splice_toc(document, "- [A](#a)").endswith("\ntail\n"))

    def test_document_ending_at_the_closing_marker_gains_no_trailing_newline(self):
        document = f"# Title\n{TOC_START}\nold\n{TOC_END}"
        result = splice_toc(document, "- [A](#a)")
        self.assertEqual(result, f"# Title\n{TOC_START}\n- [A](#a)\n{TOC_END}")

    def test_crlf_line_endings_outside_the_markers_survive(self):
        document = f"# Title\r\n\r\n{TOC_START}\nold\n{TOC_END}\r\n\r\n## A\r\n"
        result = splice_toc(document, "- [A](#a)")
        self.assertTrue(result.startswith("# Title\r\n\r\n"))
        self.assertTrue(result.endswith(f"{TOC_END}\r\n\r\n## A\r\n"))

    def test_bytes_outside_the_markers_are_identical_slices_of_the_input(self):
        document = f"  prefix \t\n\n{TOC_START}\nold\n{TOC_END}\n \tsuffix  "
        result = splice_toc(document, "- [A](#a)")
        head = document[: document.index(TOC_START)]
        tail = document[document.index(TOC_END) + len(TOC_END) :]
        self.assertEqual(result[: len(head)], head)
        self.assertEqual(result[len(result) - len(tail) :], tail)


class TestMarkerSurvival(unittest.TestCase):
    def test_both_markers_remain_in_the_output(self):
        result = splice_toc(f"{TOC_START}\nold\n{TOC_END}\n", "- [A](#a)")
        self.assertIn(TOC_START, result)
        self.assertIn(TOC_END, result)

    def test_markers_keep_their_order(self):
        result = splice_toc(f"{TOC_START}\nold\n{TOC_END}\n", "- [A](#a)")
        self.assertLess(result.index(TOC_START), result.index(TOC_END))

    def test_output_can_be_spliced_again_with_different_content(self):
        once = splice_toc(f"{TOC_START}\nold\n{TOC_END}\n", "- [A](#a)")
        twice = splice_toc(once, "- [B](#b)")
        self.assertEqual(twice, f"{TOC_START}\n- [B](#b)\n{TOC_END}\n")

    def test_markers_are_not_duplicated_by_a_second_splice(self):
        once = splice_toc(f"{TOC_START}\nold\n{TOC_END}\n", "- [A](#a)")
        twice = splice_toc(once, "- [A](#a)")
        self.assertEqual(twice.count(TOC_START), 1)
        self.assertEqual(twice.count(TOC_END), 1)


class TestIdempotency(unittest.TestCase):
    """`--check` compares splice output against the original; drift breaks it."""

    def test_second_splice_returns_an_equal_string(self):
        document = f"# Title\n\n{TOC_START}\nold\n{TOC_END}\n\n## A\n\n## B\n"
        toc = rendered(document)
        once = splice_toc(document, toc)
        self.assertEqual(splice_toc(once, toc), once)

    def test_current_document_is_returned_unchanged(self):
        document = f"# Title\n\n{TOC_START}\nold\n{TOC_END}\n\n## A\n\n### A1\n"
        current = splice_toc(document, rendered(document))
        self.assertEqual(splice_toc(current, rendered(current)), current)

    def test_rendered_pipeline_output_round_trips_over_three_splices(self):
        document = (
            "# Project\n\nIntro.\n\n"
            f"{TOC_START}\n{TOC_END}\n\n"
            "## Install\n\n### From source\n\n## Usage\n\n## License\n"
        )
        first = splice_toc(document, rendered(document))
        second = splice_toc(first, rendered(first))
        third = splice_toc(second, rendered(second))
        self.assertEqual(second, first)
        self.assertEqual(third, first)

    def test_idempotency_holds_without_a_final_newline(self):
        document = f"# T\n\n{TOC_START}\n{TOC_END}\n\n## A"
        once = splice_toc(document, rendered(document))
        self.assertEqual(splice_toc(once, rendered(once)), once)
        self.assertFalse(once.endswith("\n"))

    def test_empty_toc_region_is_idempotent(self):
        once = splice_toc(f"{TOC_START}\nold\n{TOC_END}\n", "")
        self.assertEqual(splice_toc(once, ""), once)


class TestFirstMarkerPairOnly(unittest.TestCase):
    def test_later_marker_pair_in_the_body_is_left_alone(self):
        document = (
            f"{TOC_START}\nold\n{TOC_END}\n\n"
            f"Example usage:\n\n{TOC_START}\nsample\n{TOC_END}\n"
        )
        self.assertEqual(
            splice_toc(document, "- [A](#a)"),
            f"{TOC_START}\n- [A](#a)\n{TOC_END}\n\n"
            f"Example usage:\n\n{TOC_START}\nsample\n{TOC_END}\n",
        )

    def test_closing_marker_used_is_the_first_one_after_the_opening(self):
        document = f"{TOC_START}\nold\n{TOC_END}\nbody\n{TOC_END}\n"
        result = splice_toc(document, "- [A](#a)")
        self.assertEqual(
            result, f"{TOC_START}\n- [A](#a)\n{TOC_END}\nbody\n{TOC_END}\n"
        )


class TestMarkerErrors(unittest.TestCase):
    def test_missing_opening_marker_raises(self):
        with self.assertRaises(MarkerError):
            splice_toc(f"# Title\nbody\n{TOC_END}\n", "- [A](#a)")

    def test_missing_closing_marker_raises(self):
        with self.assertRaises(MarkerError):
            splice_toc(f"# Title\n{TOC_START}\nbody\n", "- [A](#a)")

    def test_both_markers_missing_raises(self):
        with self.assertRaises(MarkerError):
            splice_toc("# Title\n\nNo markers here.\n", "- [A](#a)")

    def test_empty_document_raises(self):
        with self.assertRaises(MarkerError):
            splice_toc("", "- [A](#a)")

    def test_reversed_markers_are_rejected(self):
        with self.assertRaises(MarkerError):
            splice_toc(f"{TOC_END}\nbody\n{TOC_START}\n", "- [A](#a)")

    def test_reversed_markers_do_not_produce_a_scrambled_document(self):
        document = f"{TOC_END}\nbody\n{TOC_START}\n"
        try:
            splice_toc(document, "- [A](#a)")
        except MarkerError:
            pass
        self.assertEqual(document, f"{TOC_END}\nbody\n{TOC_START}\n")

    def test_message_names_both_expected_markers(self):
        for document in (
            f"body\n{TOC_END}\n",
            f"{TOC_START}\nbody\n",
            "body\n",
            f"{TOC_END}\n{TOC_START}\n",
        ):
            with self.subTest(document=document):
                with self.assertRaises(MarkerError) as caught:
                    splice_toc(document, "- [A](#a)")
                self.assertIn(TOC_START, str(caught.exception))
                self.assertIn(TOC_END, str(caught.exception))

    def test_marker_error_is_an_exception(self):
        self.assertTrue(issubclass(MarkerError, Exception))


class TestMarkerConstants(unittest.TestCase):
    def test_constants_have_the_documented_values(self):
        self.assertEqual(TOC_START, "<!-- toc -->")
        self.assertEqual(TOC_END, "<!-- /toc -->")

    def test_opening_marker_is_not_a_substring_of_the_closing_marker(self):
        self.assertNotIn(TOC_START, TOC_END)


if __name__ == "__main__":
    unittest.main()
