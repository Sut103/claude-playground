"""Tests for md_toc.parser — ATX heading extraction with fence suppression."""

import time
import unittest

from md_toc.parser import extract_headings
from md_toc.types import Heading


class TestBasicExtraction(unittest.TestCase):
    def test_single_heading(self):
        self.assertEqual(extract_headings("# Intro"), [Heading(1, "Intro")])

    def test_heading_among_prose(self):
        text = "some prose\n# Intro\nmore prose\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Intro")])

    def test_document_order_preserved(self):
        text = "# One\n## Two\n# Three\n### Four\n"
        self.assertEqual(
            extract_headings(text),
            [
                Heading(1, "One"),
                Heading(2, "Two"),
                Heading(1, "Three"),
                Heading(3, "Four"),
            ],
        )

    def test_no_headings_returns_empty_list(self):
        self.assertEqual(extract_headings("just prose\nand more\n"), [])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(extract_headings(""), [])

    def test_whitespace_only_document(self):
        self.assertEqual(extract_headings("\n\n   \n\t\n"), [])

    def test_trailing_whitespace_stripped_from_title(self):
        self.assertEqual(extract_headings("# Intro   "), [Heading(1, "Intro")])

    def test_extra_space_after_hashes_stripped(self):
        self.assertEqual(extract_headings("#     Intro"), [Heading(1, "Intro")])

    def test_tab_after_hashes_is_a_heading(self):
        self.assertEqual(extract_headings("#\tIntro"), [Heading(1, "Intro")])

    def test_inner_whitespace_preserved(self):
        self.assertEqual(
            extract_headings("## Getting  Started"),
            [Heading(2, "Getting  Started")],
        )

    def test_title_may_contain_hash_characters(self):
        self.assertEqual(
            extract_headings("# C# and F#"), [Heading(1, "C# and F#")]
        )

    def test_no_trailing_newline_still_parsed(self):
        self.assertEqual(
            extract_headings("# One\n## Two"),
            [Heading(1, "One"), Heading(2, "Two")],
        )

    def test_crlf_line_endings(self):
        self.assertEqual(
            extract_headings("# One\r\n## Two\r\n"),
            [Heading(1, "One"), Heading(2, "Two")],
        )


class TestAllSixLevels(unittest.TestCase):
    def test_each_level_parsed_with_correct_level(self):
        for level in range(1, 7):
            with self.subTest(level=level):
                text = "{} Title".format("#" * level)
                self.assertEqual(extract_headings(text), [Heading(level, "Title")])

    def test_all_six_levels_in_one_document(self):
        text = "\n".join("{} L{}".format("#" * n, n) for n in range(1, 7))
        self.assertEqual(
            extract_headings(text),
            [Heading(n, "L{}".format(n)) for n in range(1, 7)],
        )

    def test_seven_hashes_is_not_a_heading(self):
        self.assertEqual(extract_headings("####### Too deep"), [])


class TestNonHeadings(unittest.TestCase):
    def test_hash_with_no_space_is_not_a_heading(self):
        self.assertEqual(extract_headings("#hashtag"), [])

    def test_double_hash_with_no_space_is_not_a_heading(self):
        self.assertEqual(extract_headings("##nospace"), [])

    def test_bare_hash_is_not_a_heading(self):
        self.assertEqual(extract_headings("#"), [])

    def test_hashtag_line_among_real_headings(self):
        text = "# Real\n#hashtag\n## Also Real\n"
        self.assertEqual(
            extract_headings(text),
            [Heading(1, "Real"), Heading(2, "Also Real")],
        )

    def test_indented_hash_is_not_a_heading(self):
        self.assertEqual(extract_headings("    # Indented"), [])

    def test_hash_mid_line_is_not_a_heading(self):
        self.assertEqual(extract_headings("text # not a heading"), [])

    def test_setext_underline_is_not_a_heading(self):
        self.assertEqual(extract_headings("Title\n=====\n"), [])


class TestClosingHashes(unittest.TestCase):
    def test_closing_run_trimmed(self):
        self.assertEqual(extract_headings("## Title ##"), [Heading(2, "Title")])

    def test_closing_run_of_different_length_trimmed(self):
        self.assertEqual(
            extract_headings("# Title ######"), [Heading(1, "Title")]
        )

    def test_closing_run_with_trailing_whitespace_trimmed(self):
        self.assertEqual(
            extract_headings("### Title ###   "), [Heading(3, "Title")]
        )

    def test_hash_attached_to_word_is_kept(self):
        self.assertEqual(extract_headings("## Title#"), [Heading(2, "Title#")])

    def test_title_of_only_hashes_becomes_empty(self):
        self.assertEqual(extract_headings("## ###"), [Heading(2, "")])

    def test_empty_title_after_space(self):
        self.assertEqual(extract_headings("# "), [Heading(1, "")])


class TestBacktickFenceSuppression(unittest.TestCase):
    def test_heading_inside_backtick_fence_suppressed(self):
        text = "# Real\n```\n# Not A Heading\n```\n# Also Real\n"
        self.assertEqual(
            extract_headings(text),
            [Heading(1, "Real"), Heading(1, "Also Real")],
        )

    def test_fence_with_info_string_still_opens(self):
        text = "```python\n# a comment, not a heading\n```\n# Real\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_longer_backtick_run_opens_fence(self):
        text = "`````\n# Hidden\n`````\n# Real\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_multiple_fenced_blocks(self):
        text = (
            "# A\n```\n# hidden1\n```\n# B\n```\n# hidden2\n```\n# C\n"
        )
        self.assertEqual(
            extract_headings(text),
            [Heading(1, "A"), Heading(1, "B"), Heading(1, "C")],
        )

    def test_all_levels_suppressed_inside_fence(self):
        body = "\n".join("{} L{}".format("#" * n, n) for n in range(1, 7))
        self.assertEqual(extract_headings("```\n" + body + "\n```\n"), [])


class TestTildeFenceSuppression(unittest.TestCase):
    def test_heading_inside_tilde_fence_suppressed(self):
        text = "# Real\n~~~\n# Not A Heading\n~~~\n# Also Real\n"
        self.assertEqual(
            extract_headings(text),
            [Heading(1, "Real"), Heading(1, "Also Real")],
        )

    def test_tilde_fence_with_info_string_still_opens(self):
        text = "~~~text\n# hidden\n~~~\n# Real\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_longer_tilde_run_opens_fence(self):
        text = "~~~~~\n# Hidden\n~~~~~\n# Real\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])


class TestFenceDelimitersDoNotCross(unittest.TestCase):
    def test_tilde_does_not_close_backtick_fence(self):
        text = "```\n~~~\n# Still Hidden\n```\n# Real\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_backtick_does_not_close_tilde_fence(self):
        text = "~~~\n```\n# Still Hidden\n~~~\n# Real\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_backtick_fence_containing_tilde_block(self):
        text = "# A\n```\n~~~\n# hidden\n~~~\n# hidden too\n```\n# B\n"
        self.assertEqual(
            extract_headings(text), [Heading(1, "A"), Heading(1, "B")]
        )


class TestUnclosedFence(unittest.TestCase):
    def test_unclosed_backtick_fence_suppresses_rest_of_document(self):
        text = "# Real\n```\n# Hidden\n# Hidden Too\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_unclosed_tilde_fence_suppresses_rest_of_document(self):
        text = "# Real\n~~~\n# Hidden\n# Hidden Too\n"
        self.assertEqual(extract_headings(text), [Heading(1, "Real")])

    def test_unclosed_fence_does_not_raise(self):
        try:
            extract_headings("```\n# Hidden\n")
        except Exception as exc:  # pragma: no cover - failure path
            self.fail("unterminated fence raised {!r}".format(exc))

    def test_fence_opened_on_last_line(self):
        self.assertEqual(extract_headings("# Real\n```"), [Heading(1, "Real")])


class TestLevelBounds(unittest.TestCase):
    def setUp(self):
        self.text = "\n".join("{} L{}".format("#" * n, n) for n in range(1, 7))

    def test_defaults_include_every_level(self):
        self.assertEqual(len(extract_headings(self.text)), 6)

    def test_min_level_excludes_shallower_headings(self):
        self.assertEqual(
            extract_headings(self.text, min_level=3),
            [Heading(n, "L{}".format(n)) for n in range(3, 7)],
        )

    def test_max_level_excludes_deeper_headings(self):
        self.assertEqual(
            extract_headings(self.text, max_level=2),
            [Heading(1, "L1"), Heading(2, "L2")],
        )

    def test_bounds_are_inclusive(self):
        self.assertEqual(
            extract_headings(self.text, min_level=2, max_level=4),
            [Heading(2, "L2"), Heading(3, "L3"), Heading(4, "L4")],
        )

    def test_single_level_window(self):
        self.assertEqual(
            extract_headings(self.text, min_level=3, max_level=3),
            [Heading(3, "L3")],
        )

    def test_empty_window_returns_empty_list(self):
        self.assertEqual(extract_headings(self.text, min_level=5, max_level=2), [])

    def test_bounds_do_not_reorder_survivors(self):
        text = "### Deep\n# Shallow\n### Deeper\n"
        self.assertEqual(
            extract_headings(text, min_level=3),
            [Heading(3, "Deep"), Heading(3, "Deeper")],
        )


class TestPerformance(unittest.TestCase):
    def test_ten_thousand_lines_scanned_quickly(self):
        lines = []
        for i in range(2000):
            lines.append("## Section {}".format(i))
            lines.append("prose line")
            lines.append("```")
            lines.append("# not a heading")
            lines.append("```")
        text = "\n".join(lines)
        self.assertEqual(len(text.splitlines()), 10000)

        start = time.perf_counter()
        headings = extract_headings(text)
        elapsed = time.perf_counter() - start

        self.assertEqual(len(headings), 2000)
        self.assertLess(elapsed, 1.0)


class TestRealisticDocument(unittest.TestCase):
    def test_mixed_document(self):
        text = (
            "# Project\n"
            "\n"
            "Intro prose with a #hashtag in it.\n"
            "\n"
            "## Install ##\n"
            "\n"
            "```sh\n"
            "# apt install thing\n"
            "~~~\n"
            "```\n"
            "\n"
            "### Notes\n"
            "\n"
            "~~~\n"
            "#### buried\n"
            "~~~\n"
            "\n"
            "####### not a heading\n"
            "## License\n"
        )
        self.assertEqual(
            extract_headings(text),
            [
                Heading(1, "Project"),
                Heading(2, "Install"),
                Heading(3, "Notes"),
                Heading(2, "License"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
