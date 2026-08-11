---
issue: 16
title: GitHub anchor slug generation
analyzed: 2026-08-11T07:20:20Z
estimated_hours: 3
parallelization_factor: 1.0
---

# Parallel Work Analysis: Issue #16

## Overview

Implements `slugify`, translating heading text into GitHub's anchor dialect:
lowercase, punctuation stripped, spaces to hyphens, with numeric suffixes
disambiguating repeats via a caller-held `seen` map.

One pure function and its tests — no internal seam worth splitting. The duplicate
disambiguation is the highest-risk detail and is covered by dedicated tests rather
than being folded into the end-to-end pass.

## Parallel Streams

### Stream A: Slug generation and tests
**Scope**: `slugify(title, seen) -> str` plus unit tests for casing, punctuation
removal, whitespace handling, unicode, and `-1`/`-2` duplicate suffixes.
**Files**: `md_toc/slug.py`, `tests/test_slug.py`
**Can Start**: immediately (#12 is closed)
**Estimated Hours**: 3
**Dependencies**: none remaining

## Coordination Points

### Shared Files
None. Does not import from the parser; operates on plain strings.

### Sequential Requirements
#18 (rendering) consumes this and must wait.

## Conflict Risk Assessment

Low. Disjoint from #14's paths. The interface risk is the `seen` argument's
type — fixed as a mutable dict of slug to occurrence count in the issue body,
so #18 can be written against it before this lands.

## Parallelization Strategy

Launch as one agent alongside #14's agent.

## Expected Timeline
- With parallel execution: 3h wall time (concurrent with #14's 4h)
- Without: 7h
- Efficiency gain: 43%
