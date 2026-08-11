---
issue: 14
title: Heading extraction with fenced-code suppression
analyzed: 2026-08-11T07:20:20Z
estimated_hours: 4
parallelization_factor: 1.0
---

# Parallel Work Analysis: Issue #14

## Overview

Implements `extract_headings`, a line scanner that returns `Heading` values for
ATX headings while suppressing anything inside fenced code blocks and honouring
level bounds.

Internally this is one cohesive scan loop — fence state and heading detection are
evaluated against the same line in the same pass, so splitting them across agents
would mean two agents editing one function. Parallelization factor is 1.0.

The real parallelism is with issue #16, which owns a disjoint pair of paths and
runs concurrently with this one.

## Parallel Streams

### Stream A: Scanner and tests
**Scope**: `extract_headings(text, min_level=1, max_level=6) -> list[Heading]`,
plus unit tests covering fence suppression for both ``` and ~~~ delimiters,
level bounds, and malformed input.
**Files**: `md_toc/parser.py`, `tests/test_parser.py`
**Can Start**: immediately (#12 is closed)
**Estimated Hours**: 4
**Dependencies**: none remaining

## Coordination Points

### Shared Files
None. Imports `Heading` from `md_toc/types.py` but does not modify it.

### Sequential Requirements
#18 (rendering) consumes this output and must wait.

## Conflict Risk Assessment

Low. Runs concurrently with #16; the two touch no common path. Both import from
`md_toc/types.py`, which is closed and frozen.

## Parallelization Strategy

Launch as one agent alongside #16's agent.

## Expected Timeline
- With parallel execution: 4h wall time (concurrent with #16's 3h)
- Without: 7h
- Efficiency gain: 43%
