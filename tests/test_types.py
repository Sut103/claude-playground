"""Tests for md_toc.types — the Heading value type and exit-code constants."""

import dataclasses
import unittest

import md_toc
from md_toc import types


class TestHeadingFields(unittest.TestCase):
    def test_has_exactly_two_fields_named_level_and_title(self):
        fields = dataclasses.fields(types.Heading)
        self.assertEqual([f.name for f in fields], ["level", "title"])

    def test_field_annotations(self):
        # `f.type` is the class when annotations are eager, the source string
        # when they are lazy; accept either form.
        fields = {f.name: f.type for f in dataclasses.fields(types.Heading)}
        self.assertIn(fields["level"], (int, "int"))
        self.assertIn(fields["title"], (str, "str"))

    def test_positional_construction(self):
        heading = types.Heading(1, "Intro")
        self.assertEqual(heading.level, 1)
        self.assertEqual(heading.title, "Intro")

    def test_keyword_construction(self):
        heading = types.Heading(level=3, title="Details")
        self.assertEqual(heading.level, 3)
        self.assertEqual(heading.title, "Details")


class TestHeadingEquality(unittest.TestCase):
    def test_value_equality(self):
        self.assertEqual(types.Heading(1, "Intro"), types.Heading(1, "Intro"))

    def test_differs_by_level(self):
        self.assertNotEqual(types.Heading(1, "Intro"), types.Heading(2, "Intro"))

    def test_differs_by_title(self):
        self.assertNotEqual(types.Heading(1, "Intro"), types.Heading(1, "Setup"))

    def test_list_equality(self):
        self.assertEqual(
            [types.Heading(1, "Intro"), types.Heading(2, "Setup")],
            [types.Heading(1, "Intro"), types.Heading(2, "Setup")],
        )

    def test_hashable(self):
        self.assertEqual(
            {types.Heading(1, "Intro"), types.Heading(1, "Intro")},
            {types.Heading(1, "Intro")},
        )


class TestHeadingFrozen(unittest.TestCase):
    def test_dataclass_declared_frozen(self):
        self.assertTrue(types.Heading.__dataclass_params__.frozen)

    def test_cannot_assign_level(self):
        heading = types.Heading(1, "Intro")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            heading.level = 2

    def test_cannot_assign_title(self):
        heading = types.Heading(1, "Intro")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            heading.title = "Setup"

    def test_cannot_delete_field(self):
        heading = types.Heading(1, "Intro")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            del heading.level


class TestExitCodes(unittest.TestCase):
    def test_exit_ok(self):
        self.assertEqual(types.EXIT_OK, 0)

    def test_exit_stale(self):
        self.assertEqual(types.EXIT_STALE, 1)

    def test_exit_error(self):
        self.assertEqual(types.EXIT_ERROR, 2)

    def test_codes_are_distinct(self):
        self.assertEqual(
            len({types.EXIT_OK, types.EXIT_STALE, types.EXIT_ERROR}), 3
        )


class TestPackageReExports(unittest.TestCase):
    def test_heading_reexported(self):
        self.assertIs(md_toc.Heading, types.Heading)

    def test_exit_codes_reexported(self):
        self.assertEqual(md_toc.EXIT_OK, types.EXIT_OK)
        self.assertEqual(md_toc.EXIT_STALE, types.EXIT_STALE)
        self.assertEqual(md_toc.EXIT_ERROR, types.EXIT_ERROR)

    def test_either_import_path_gives_equal_values(self):
        self.assertEqual(md_toc.Heading(1, "Intro"), types.Heading(1, "Intro"))


if __name__ == "__main__":
    unittest.main()
