"""Tests for md_toc.render — nested Markdown TOC rendering.

The two details worth guarding hardest are relative indentation (the shallowest
level present must render flush left) and the single shared `seen` dict (a
fresh dict per heading would silently point every duplicate at one anchor), so
each gets its own test class.
"""

import unittest

from md_toc.render import render_toc
from md_toc.types import Heading


class TestEntryFormat(unittest.TestCase):
    def test_single_heading_renders_one_line(self):
        self.assertEqual(
            render_toc([Heading(1, "Overview")]),
            "- [Overview](#overview)",
        )

    def test_entry_is_a_markdown_link_to_the_anchor(self):
        self.assertEqual(
            render_toc([Heading(1, "Getting Started")]),
            "- [Getting Started](#getting-started)",
        )

    def test_flat_list_is_one_line_per_heading(self):
        headings = [
            Heading(2, "Install"),
            Heading(2, "Usage"),
            Heading(2, "License"),
        ]
        self.assertEqual(
            render_toc(headings),
            "- [Install](#install)\n- [Usage](#usage)\n- [License](#license)",
        )

    def test_document_order_is_preserved(self):
        headings = [Heading(1, "Zebra"), Heading(1, "Apple"), Heading(1, "Mango")]
        self.assertEqual(
            [line.split("[")[1].split("]")[0] for line in render_toc(headings).split("\n")],
            ["Zebra", "Apple", "Mango"],
        )

    def test_line_count_matches_heading_count(self):
        headings = [Heading(1 + (i % 3), f"H{i}") for i in range(10)]
        self.assertEqual(len(render_toc(headings).split("\n")), 10)


class TestLinkText(unittest.TestCase):
    def test_original_casing_is_preserved_in_link_text(self):
        self.assertEqual(
            render_toc([Heading(1, "API REFERENCE")]),
            "- [API REFERENCE](#api-reference)",
        )

    def test_inline_punctuation_is_preserved_in_link_text(self):
        self.assertEqual(
            render_toc([Heading(1, "What's New?")]),
            "- [What's New?](#whats-new)",
        )

    def test_markdown_markup_survives_in_link_text_only(self):
        self.assertEqual(
            render_toc([Heading(2, "**Bold** `code`")]),
            "- [**Bold** `code`](#bold-code)",
        )

    def test_unicode_title_is_preserved(self):
        self.assertEqual(
            render_toc([Heading(1, "Café Menu")]),
            "- [Café Menu](#café-menu)",
        )

    def test_empty_title_still_renders_an_entry(self):
        # An empty title slugifies to "", leaving a bare "#" fragment rather
        # than raising or dropping the entry.
        self.assertEqual(render_toc([Heading(1, "")]), "- [](#)")


class TestNesting(unittest.TestCase):
    def test_child_is_indented_two_spaces(self):
        headings = [Heading(1, "Top"), Heading(2, "Child")]
        self.assertEqual(
            render_toc(headings),
            "- [Top](#top)\n  - [Child](#child)",
        )

    def test_each_level_adds_exactly_two_spaces(self):
        headings = [
            Heading(1, "A"),
            Heading(2, "B"),
            Heading(3, "C"),
            Heading(4, "D"),
        ]
        self.assertEqual(
            render_toc(headings).split("\n"),
            [
                "- [A](#a)",
                "  - [B](#b)",
                "    - [C](#c)",
                "      - [D](#d)",
            ],
        )

    def test_nested_document_returns_to_shallower_level(self):
        headings = [
            Heading(1, "Title"),
            Heading(2, "Install"),
            Heading(3, "macOS"),
            Heading(3, "Linux"),
            Heading(2, "Usage"),
        ]
        self.assertEqual(
            render_toc(headings).split("\n"),
            [
                "- [Title](#title)",
                "  - [Install](#install)",
                "    - [macOS](#macos)",
                "    - [Linux](#linux)",
                "  - [Usage](#usage)",
            ],
        )

    def test_deepest_level_six_under_level_one(self):
        headings = [Heading(1, "Top"), Heading(6, "Deep")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Top](#top)", "          - [Deep](#deep)"],
        )


class TestRelativeIndentation(unittest.TestCase):
    def test_shallowest_h2_renders_at_zero_indentation(self):
        headings = [Heading(2, "Install"), Heading(3, "macOS")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Install](#install)", "  - [macOS](#macos)"],
        )

    def test_shallowest_h3_renders_at_zero_indentation(self):
        headings = [Heading(3, "Install"), Heading(4, "macOS")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Install](#install)", "  - [macOS](#macos)"],
        )

    def test_shallowest_h6_renders_at_zero_indentation(self):
        self.assertEqual(render_toc([Heading(6, "Deep")]), "- [Deep](#deep)")

    def test_h2_document_matches_h1_document_modulo_titles(self):
        from_h1 = render_toc(
            [Heading(1, "Alpha"), Heading(2, "Beta"), Heading(3, "Gamma")]
        )
        from_h2 = render_toc(
            [Heading(2, "Alpha"), Heading(3, "Beta"), Heading(4, "Gamma")]
        )
        self.assertEqual(from_h1, from_h2)

    def test_baseline_is_the_minimum_level_not_the_first(self):
        # The document opens at h2 but a shallower h1 appears later; the h1 is
        # the baseline, so the leading h2 is indented rather than flush left.
        headings = [Heading(2, "Preface"), Heading(1, "Title"), Heading(2, "Body")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            [
                "  - [Preface](#preface)",
                "- [Title](#title)",
                "  - [Body](#body)",
            ],
        )

    def test_no_line_is_indented_when_all_levels_are_equal(self):
        headings = [Heading(4, "One"), Heading(4, "Two")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [One](#one)", "- [Two](#two)"],
        )


class TestLevelJumps(unittest.TestCase):
    def test_h1_straight_to_h4_indents_by_the_level_difference(self):
        headings = [Heading(1, "Title"), Heading(4, "Deep")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Title](#title)", "      - [Deep](#deep)"],
        )

    def test_h1_then_h3_does_not_collapse_to_one_level(self):
        headings = [Heading(1, "Title"), Heading(3, "Sub")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Title](#title)", "    - [Sub](#sub)"],
        )

    def test_jump_down_and_back_up_keeps_absolute_offsets(self):
        headings = [
            Heading(1, "Title"),
            Heading(4, "Deep"),
            Heading(2, "Back"),
            Heading(5, "Deeper"),
        ]
        self.assertEqual(
            render_toc(headings).split("\n"),
            [
                "- [Title](#title)",
                "      - [Deep](#deep)",
                "  - [Back](#back)",
                "        - [Deeper](#deeper)",
            ],
        )

    def test_skipped_level_does_not_raise(self):
        try:
            render_toc([Heading(1, "A"), Heading(6, "B"), Heading(2, "C")])
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"render_toc raised on skipped levels: {exc!r}")


class TestDuplicateAnchors(unittest.TestCase):
    def test_duplicate_titles_get_distinct_anchors(self):
        headings = [Heading(2, "Setup"), Heading(2, "Setup")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Setup](#setup)", "- [Setup](#setup-1)"],
        )

    def test_three_duplicates_number_consecutively(self):
        headings = [Heading(2, "Notes")] * 3
        self.assertEqual(
            render_toc(headings).split("\n"),
            [
                "- [Notes](#notes)",
                "- [Notes](#notes-1)",
                "- [Notes](#notes-2)",
            ],
        )

    def test_all_anchors_in_a_duplicate_heavy_document_are_unique(self):
        headings = [Heading(2, "Setup") for _ in range(5)]
        anchors = [line.split("(#")[1].rstrip(")") for line in render_toc(headings).split("\n")]
        self.assertEqual(len(set(anchors)), 5)

    def test_duplicates_are_numbered_in_document_order(self):
        headings = [
            Heading(1, "Guide"),
            Heading(2, "Setup"),
            Heading(2, "Usage"),
            Heading(2, "Setup"),
            Heading(2, "Usage"),
            Heading(2, "Setup"),
        ]
        anchors = [line.split("(#")[1].rstrip(")") for line in render_toc(headings).split("\n")]
        self.assertEqual(
            anchors,
            ["guide", "setup", "usage", "setup-1", "usage-1", "setup-2"],
        )

    def test_duplicates_at_different_levels_still_disambiguate(self):
        # The seen dict is keyed by slug alone, so nesting does not reset it.
        headings = [Heading(1, "Setup"), Heading(3, "Setup")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Setup](#setup)", "    - [Setup](#setup-1)"],
        )

    def test_titles_normalizing_to_the_same_slug_are_disambiguated(self):
        headings = [Heading(2, "What's New?"), Heading(2, "Whats New")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [What's New?](#whats-new)", "- [Whats New](#whats-new-1)"],
        )

    def test_seen_dict_does_not_leak_between_calls(self):
        first = render_toc([Heading(1, "Setup"), Heading(1, "Setup")])
        second = render_toc([Heading(1, "Setup"), Heading(1, "Setup")])
        self.assertEqual(first, second)
        self.assertEqual(
            second.split("\n"),
            ["- [Setup](#setup)", "- [Setup](#setup-1)"],
        )

    def test_distinct_titles_are_not_suffixed(self):
        headings = [Heading(2, "Alpha"), Heading(2, "Beta")]
        self.assertEqual(
            render_toc(headings).split("\n"),
            ["- [Alpha](#alpha)", "- [Beta](#beta)"],
        )


class TestEmptyInput(unittest.TestCase):
    def test_empty_list_renders_empty_string(self):
        self.assertEqual(render_toc([]), "")

    def test_empty_list_does_not_raise(self):
        try:
            render_toc([])
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"render_toc raised on an empty list: {exc!r}")


class TestOutputShape(unittest.TestCase):
    def test_output_has_no_trailing_newline(self):
        out = render_toc([Heading(1, "A"), Heading(2, "B")])
        self.assertFalse(out.endswith("\n"))

    def test_output_has_no_leading_newline(self):
        out = render_toc([Heading(1, "A"), Heading(2, "B")])
        self.assertFalse(out.startswith("\n"))

    def test_output_contains_no_blank_lines(self):
        out = render_toc([Heading(1, "A"), Heading(2, "B"), Heading(1, "C")])
        self.assertNotIn("\n\n", out)

    def test_repeated_render_is_byte_identical(self):
        headings = [Heading(2, "Setup"), Heading(3, "Setup"), Heading(2, "Usage")]
        self.assertEqual(render_toc(headings), render_toc(headings))

    def test_return_type_is_str(self):
        self.assertIsInstance(render_toc([Heading(1, "A")]), str)
        self.assertIsInstance(render_toc([]), str)


class TestRealisticDocument(unittest.TestCase):
    """One fixture exercising nesting, duplicates and a non-`#` start together."""

    HEADINGS = [
        Heading(2, "Getting Started"),
        Heading(3, "Installation"),
        Heading(4, "macOS"),
        Heading(4, "Linux"),
        Heading(3, "Configuration"),
        Heading(2, "Usage"),
        Heading(3, "Installation"),
        Heading(5, "What's New?"),
        Heading(2, "Getting Started"),
    ]

    EXPECTED = "\n".join(
        [
            "- [Getting Started](#getting-started)",
            "  - [Installation](#installation)",
            "    - [macOS](#macos)",
            "    - [Linux](#linux)",
            "  - [Configuration](#configuration)",
            "- [Usage](#usage)",
            "  - [Installation](#installation-1)",
            "      - [What's New?](#whats-new)",
            "- [Getting Started](#getting-started-1)",
        ]
    )

    def test_renders_expected_document(self):
        self.assertEqual(render_toc(self.HEADINGS), self.EXPECTED)

    def test_every_anchor_is_unique(self):
        anchors = [
            line.split("(#")[1].rstrip(")")
            for line in render_toc(self.HEADINGS).split("\n")
        ]
        self.assertEqual(len(anchors), len(set(anchors)))

    def test_shallowest_h2_entries_are_flush_left(self):
        flush = [
            line
            for line in render_toc(self.HEADINGS).split("\n")
            if not line.startswith(" ")
        ]
        self.assertEqual(len(flush), 3)


class TestParserIntegration(unittest.TestCase):
    def test_renders_headings_extracted_from_markdown_source(self):
        from md_toc.parser import extract_headings

        source = "\n".join(
            [
                "## Getting Started",
                "text",
                "### Setup",
                "```",
                "# Not A Heading",
                "```",
                "### Setup",
            ]
        )
        self.assertEqual(
            render_toc(extract_headings(source)).split("\n"),
            [
                "- [Getting Started](#getting-started)",
                "  - [Setup](#setup)",
                "  - [Setup](#setup-1)",
            ],
        )


if __name__ == "__main__":
    unittest.main()
