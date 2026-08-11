---
issue: 17
title: Fixtures and end-to-end acceptance tests
analyzed: 2026-08-11T07:36:36Z
estimated_hours: 4
parallelization_factor: 1.0
---

# Parallel Work Analysis: Issue #17

## Overview

The epic's seam test. Every prior issue verified its own module in isolation; this
one drives the assembled CLI over real fixture files on disk and checks the three
PRD user stories end to end.

Single stream — the fixtures and the tests that consume them are written together,
and splitting them would mean one agent guessing at the other's file contents.

## Parallel Streams

### Stream A: Fixtures and acceptance tests
**Scope**: Markdown fixtures plus end-to-end tests for all three user stories:
stdout generation leaving the file untouched; `--in-place` rewriting between
markers, preserving everything outside them, and being idempotent across two runs;
`--check` returning 0 on fresh and 1 on stale. Also the missing-marker error path
and a fixture with headings inside fenced code blocks.
**Files**: `tests/fixtures/`, `tests/test_acceptance.py`
**Can Start**: immediately (#13 and #15 closed)
**Estimated Hours**: 4
**Dependencies**: none remaining

## Coordination Points

### Shared Files
None. Consumes the CLI as a black box; modifies no source module.

### Sequential Requirements
Last task in the epic. Nothing waits on it; the epic merge does.

## Conflict Risk Assessment

Low as to files, higher as to findings. This is the first task positioned to
contradict an earlier one — it exercises combinations no unit test covered. Any
defect it surfaces belongs in a linked bug issue against the responsible task
rather than a silent fix here, since this task owns no source module.

## Parallelization Strategy

Sequential, alone.

## Expected Timeline
- With parallel execution: 4h wall time
- Without: 4h
- Efficiency gain: 0% (final serialization point)
