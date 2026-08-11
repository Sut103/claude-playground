---
issue: 18
title: Nested TOC rendering
analyzed: 2026-08-11T07:28:51Z
estimated_hours: 3
parallelization_factor: 1.0
---

# Parallel Work Analysis: Issue #18

## Overview

Implements `render_toc`, which turns a list of `Heading` values into a nested
Markdown list. It is the join point of the epic: the first module to consume both
#14's parser output and #16's slug generation.

One function over one loop — no internal seam. Parallelization factor 1.0. It is
also the epic's second serialization point: #13 and #15 both wait on it.

## Parallel Streams

### Stream A: Renderer and tests
**Scope**: `render_toc(headings) -> str`. Two spaces of indentation per level
below the shallowest heading present, each entry a Markdown link to the heading's
anchor slug, with one `seen` dict shared across the document so duplicate
headings disambiguate correctly.
**Files**: `md_toc/render.py`, `tests/test_render.py`
**Can Start**: immediately (#14 and #16 closed, #19 fixed)
**Estimated Hours**: 3
**Dependencies**: none remaining

## Coordination Points

### Shared Files
None. Imports from `md_toc.types` and `md_toc.slug`; modifies neither.

### Sequential Requirements
#13 (splice) and #15 (CLI) both consume this and must wait. Once it lands, both
release together as the epic's final parallel pair.

## Conflict Risk Assessment

Low — sole agent, disjoint paths. The live risk is behavioural rather than
textual: the anchor dialect was just corrected under #19, so the renderer must
call `slugify` with one shared `seen` dict per document rather than a fresh dict
per heading, or duplicate headings will silently all link to the same anchor.

## Parallelization Strategy

Sequential. It gates the final pair, so it runs alone.

## Expected Timeline
- With parallel execution: 3h wall time
- Without: 3h
- Efficiency gain: 0% (serialization point)
