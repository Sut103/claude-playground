---
issue: 19
stream: Slug whitespace fix
started: 2026-08-11T07:25:54Z
status: completed
---
## Scope
Remove whitespace-run collapsing from slugify to match GitHub; correct 16.md.
Files: md_toc/slug.py, tests/test_slug.py, .claude/epics/md-toc/16.md

## Progress
- `md_toc/slug.py`: changed `_WHITESPACE_RE` from `\s+` to `\s`, so each
  whitespace character becomes exactly one hyphen instead of a run collapsing
  to one. Leading/trailing whitespace is still stripped before the conversion
  (the existing `.strip()` runs after punctuation removal), so no slug begins
  or ends with a stray hyphen. Updated the module comment and the docstring to
  describe GitHub's actual rule.
- Nothing else changed: lowercasing, punctuation stripping, in-place `seen`
  mutation and the `-1`/`-2` duplicate suffixes are untouched.
- `tests/test_slug.py`: replaced `test_runs_of_spaces_collapse_to_one_hyphen`
  with `test_runs_of_spaces_are_not_collapsed`
  (`"hello     world"` -> `hello-----world`). Added
  `test_two_spaces_become_two_hyphens` (`"A  B"` -> `a--b`),
  `test_cpp_and_csharp_heading_matches_github` (`"C++ / C#"` -> `c--c`) and
  `test_punctuation_between_spaces_leaves_both_hyphens`
  (`"Read & Write"` -> `read--write`). Corrected three cases whose expectations
  depended on collapsing: tabs/newlines (`hello--big-world`), unicode
  punctuation (`smart-quotes--dash`) and emoji (`release--notes`). In
  `test_different_titles_normalizing_alike_are_disambiguated`, the third title
  became `"WHATS NEW!!!"` so it still normalizes to the same base slug and the
  duplicate-numbering coverage is preserved. Casing, punctuation, unicode,
  duplicates and document-order coverage all remain.
- `.claude/epics/md-toc/16.md`: corrected the acceptance criterion and the
  algorithm paragraph to state that each whitespace character becomes one
  hyphen with no collapsing, citing `C++ / C#` -> `c--c`, so the erroneous rule
  is not inherited by future work. Frontmatter preserved; only `updated:` was
  changed.

## Verification
```
$ python3 -m unittest discover
..................................................................................................................
----------------------------------------------------------------------
Ran 114 tests in 0.013s

OK
```
```
$ python3 -c "from md_toc.slug import slugify; print(slugify('C++ / C#', {}), slugify('A  B', {}), slugify('Hello World', {}))"
c--c a--b hello-world
```

All acceptance criteria in 19.md are met.
