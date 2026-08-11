---
issue: 12
title: Package scaffold, Heading type, and exit-code constants
analyzed: 2026-08-11T07:10:00Z
estimated_hours: 1
parallelization_factor: 1.0
---

# Parallel Work Analysis: Issue #12

## Overview

This issue creates the `md_toc/` package and the two symbols every later module
imports: the `Heading` value type and the three exit-code constants. It performs
no I/O and no parsing.

It admits no meaningful parallelism. Both owned files are small, and `__init__.py`
re-exports `Heading` from `types.py`, so splitting them across agents would create
an import-ordering dependency between two files totalling a few dozen lines. The
honest parallelization factor is 1.0 — inflating it here would cost coordination
overhead and buy nothing.

The parallelism in this epic lives *between* issues, not inside this one: #12 is
the single serialization point, and clearing it releases the #14/#16 pair.

## Parallel Streams

### Stream A: Package foundation
**Scope**: Create the package and its shared vocabulary — the `Heading` dataclass
and the `EXIT_OK` / `EXIT_STALE` / `EXIT_ERROR` constants — plus a unit test
asserting value equality and the constant values.
**Files**: `md_toc/__init__.py`, `md_toc/types.py`, `tests/test_types.py`
**Can Start**: immediately
**Estimated Hours**: 1
**Dependencies**: none

## Coordination Points

### Shared Files
None. No other issue in the epic owns `md_toc/__init__.py` or `md_toc/types.py`.
Every later issue *imports* from `types.py` but none modify it.

### Sequential Requirements
This issue must complete before #14 and #16 start, since both import `Heading`.

## Conflict Risk Assessment

Minimal. A single agent owns both source files, and no concurrent issue writes to
the paths involved. The only downstream risk is interface churn: if `Heading`'s
field names change after #14 and #16 have started, both would need edits. That is
mitigated by fixing the field names (`level`, `title`) in the issue body before
any dependent work begins.

## Parallelization Strategy

Sequential. Launch one agent for Stream A and wait for it to complete before
releasing the next wave.

## Expected Timeline
- With parallel execution: 1h wall time
- Without: 1h
- Efficiency gain: 0%
