"""Tests for md_toc.slug — GitHub anchor slug generation.

Duplicate disambiguation is the highest-risk detail in this module, so it gets
its own test class with an explicit three-way case.
"""

import unittest

from md_toc.slug import slugify


class TestCasing(unittest.TestCase):
    def test_lowercases_title(self):
        self.assertEqual(slugify("Getting Started", {}), "getting-started")

    def test_lowercases_all_caps(self):
        self.assertEqual(slugify("API REFERENCE", {}), "api-reference")

    def test_mixed_case_is_flattened(self):
        seen = {}
        self.assertEqual(slugify("MiXeD CaSe", seen), "mixed-case")
        # "mixed case" normalizes to the same base, so it is a duplicate.
        self.assertEqual(slugify("mixed case", seen), "mixed-case-1")

    def test_already_lowercase_is_unchanged(self):
        self.assertEqual(slugify("intro", {}), "intro")


class TestWhitespace(unittest.TestCase):
    def test_single_space_becomes_hyphen(self):
        self.assertEqual(slugify("hello world", {}), "hello-world")

    def test_runs_of_spaces_are_not_collapsed(self):
        # GitHub emits one hyphen per whitespace character, not one per run.
        self.assertEqual(slugify("hello     world", {}), "hello-----world")

    def test_two_spaces_become_two_hyphens(self):
        self.assertEqual(slugify("A  B", {}), "a--b")

    def test_tabs_and_newlines_are_whitespace_too(self):
        self.assertEqual(slugify("hello\t\tbig\nworld", {}), "hello--big-world")

    def test_leading_and_trailing_whitespace_is_dropped(self):
        self.assertEqual(slugify("   Getting Started   ", {}), "getting-started")

    def test_whitespace_only_title_yields_empty_slug(self):
        self.assertEqual(slugify("   \t  ", {}), "")


class TestPunctuation(unittest.TestCase):
    def test_apostrophe_and_question_mark_are_stripped(self):
        self.assertEqual(slugify("What's New?", {}), "whats-new")

    def test_punctuation_is_stripped_not_replaced(self):
        # The comma vanishes; only the space becomes a hyphen.
        self.assertEqual(slugify("Hello, World", {}), "hello-world")

    def test_cpp_and_csharp_heading_matches_github(self):
        # "++", "/" and "#" are removed before spaces are converted, leaving
        # two spaces — GitHub turns each into its own hyphen.
        self.assertEqual(slugify("C++ / C#", {}), "c--c")

    def test_punctuation_between_spaces_leaves_both_hyphens(self):
        self.assertEqual(slugify("Read & Write", {}), "read--write")

    def test_existing_hyphens_are_preserved(self):
        self.assertEqual(slugify("Well-Known URIs", {}), "well-known-uris")

    def test_underscores_are_preserved(self):
        self.assertEqual(slugify("snake_case name", {}), "snake_case-name")

    def test_digits_are_preserved(self):
        self.assertEqual(slugify("Section 42", {}), "section-42")

    def test_markdown_markup_is_stripped(self):
        self.assertEqual(slugify("**Bold** `code`", {}), "bold-code")

    def test_trailing_punctuation_leaves_no_trailing_hyphen(self):
        self.assertEqual(slugify("Overview!", {}), "overview")

    def test_leading_punctuation_leaves_no_leading_hyphen(self):
        self.assertEqual(slugify("...Overview", {}), "overview")

    def test_punctuation_only_title_yields_empty_slug(self):
        self.assertEqual(slugify("???", {}), "")

    def test_empty_title_does_not_raise(self):
        self.assertEqual(slugify("", {}), "")


class TestUnicode(unittest.TestCase):
    def test_accented_letters_survive_in_lowercase(self):
        self.assertEqual(slugify("Café Menu", {}), "café-menu")

    def test_accented_uppercase_is_lowercased_not_stripped(self):
        self.assertEqual(slugify("ÉTUDE", {}), "étude")

    def test_cjk_text_is_retained(self):
        self.assertEqual(slugify("日本語 見出し", {}), "日本語-見出し")

    def test_cyrillic_text_is_retained(self):
        self.assertEqual(slugify("Привет Мир", {}), "привет-мир")

    def test_unicode_punctuation_is_stripped(self):
        # The em dash vanishes, leaving the two spaces that flanked it.
        self.assertEqual(slugify("“Smart” quotes — dash", {}), "smart-quotes--dash")

    def test_emoji_is_stripped(self):
        self.assertEqual(slugify("Release 🎉 Notes", {}), "release--notes")


class TestDuplicates(unittest.TestCase):
    def test_first_occurrence_has_no_suffix(self):
        self.assertEqual(slugify("Setup", {}), "setup")

    def test_second_occurrence_gets_dash_one(self):
        seen = {}
        slugify("Setup", seen)
        self.assertEqual(slugify("Setup", seen), "setup-1")

    def test_three_identical_titles_share_one_seen_dict(self):
        seen = {}
        self.assertEqual(
            [slugify("Setup", seen) for _ in range(3)],
            ["setup", "setup-1", "setup-2"],
        )

    def test_five_identical_titles_number_consecutively(self):
        seen = {}
        self.assertEqual(
            [slugify("Notes", seen) for _ in range(5)],
            ["notes", "notes-1", "notes-2", "notes-3", "notes-4"],
        )

    def test_distinct_titles_are_counted_independently(self):
        seen = {}
        self.assertEqual(
            [
                slugify("Setup", seen),
                slugify("Usage", seen),
                slugify("Setup", seen),
                slugify("Usage", seen),
            ],
            ["setup", "usage", "setup-1", "usage-1"],
        )

    def test_different_titles_normalizing_alike_are_disambiguated(self):
        seen = {}
        self.assertEqual(slugify("What's New?", seen), "whats-new")
        self.assertEqual(slugify("Whats New", seen), "whats-new-1")
        self.assertEqual(slugify("WHATS NEW!!!", seen), "whats-new-2")

    def test_empty_slugs_are_disambiguated_too(self):
        seen = {}
        self.assertEqual(slugify("!!!", seen), "")
        self.assertEqual(slugify("???", seen), "-1")

    def test_seen_is_mutated_in_place(self):
        seen = {}
        slugify("Setup", seen)
        self.assertEqual(seen, {"setup": 0})
        slugify("Setup", seen)
        self.assertEqual(seen, {"setup": 1})
        slugify("Setup", seen)
        self.assertEqual(seen, {"setup": 2})

    def test_caller_dict_object_identity_is_kept(self):
        seen = {}
        before = id(seen)
        slugify("Setup", seen)
        slugify("Setup", seen)
        self.assertEqual(id(seen), before)
        self.assertEqual(len(seen), 1)

    def test_fresh_seen_resets_numbering(self):
        first_doc = {}
        slugify("Setup", first_doc)
        slugify("Setup", first_doc)
        second_doc = {}
        self.assertEqual(slugify("Setup", second_doc), "setup")

    def test_slugs_do_not_leak_between_documents(self):
        first_doc = {}
        [slugify("Setup", first_doc) for _ in range(3)]
        second_doc = {}
        self.assertEqual(
            [slugify("Setup", second_doc) for _ in range(2)],
            ["setup", "setup-1"],
        )
        # The first document's counter is untouched by the second.
        self.assertEqual(first_doc, {"setup": 2})

    def test_suffixed_slug_does_not_collide_with_a_literal_title(self):
        # A heading literally named "Setup 1" is a different base slug, so it
        # is counted on its own rather than merged with "Setup"'s suffixes.
        seen = {}
        self.assertEqual(slugify("Setup", seen), "setup")
        self.assertEqual(slugify("Setup 1", seen), "setup-1")
        self.assertEqual(slugify("Setup", seen), "setup-1")


class TestDocumentOrder(unittest.TestCase):
    def test_realistic_document_sequence(self):
        seen = {}
        titles = [
            "Getting Started",
            "Installation",
            "Usage",
            "Installation",
            "What's New?",
            "Usage",
            "Usage",
        ]
        self.assertEqual(
            [slugify(t, seen) for t in titles],
            [
                "getting-started",
                "installation",
                "usage",
                "installation-1",
                "whats-new",
                "usage-1",
                "usage-2",
            ],
        )


if __name__ == "__main__":
    unittest.main()
