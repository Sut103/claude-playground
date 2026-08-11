---
name: md-toc
description: CLI that generates and injects a table of contents into Markdown files from their headings
status: backlog
created: 2026-08-11T06:35:03Z
---

# PRD: md-toc

## Executive Summary

`md-toc` is a small command-line tool that reads a Markdown file, derives a table of contents from its headings, and either prints the TOC to stdout or injects it back into the file between marker comments. It targets repositories where long Markdown documents (READMEs, design docs, runbooks) drift out of sync with their hand-maintained TOCs.

## Problem Statement

Long Markdown documents are navigated by their table of contents, but that TOC is usually maintained by hand. Every heading rename, insertion, or reordering silently invalidates it, and the breakage is invisible until a reader clicks a dead anchor. Existing tools exist but tend to arrive as a Node/npm dependency, which is unwelcome in repositories that carry no JavaScript toolchain. The gap is a dependency-light tool that can run in CI and fail the build when a committed TOC no longer matches the document's headings.

## User Stories

### Story 1: Generate a TOC for an existing document
**As a** developer with a long README,
**I want** to generate a TOC from its headings,
**so that** I don't have to write and indent the list by hand.

Acceptance criteria:
- Running `md-toc README.md` prints a nested Markdown list to stdout.
- Nesting depth reflects heading level; the list is indented two spaces per level.
- Each entry is a link to the heading's GitHub-style anchor.
- The source file is not modified.

### Story 2: Keep a TOC in sync in place
**As a** maintainer of a document that changes often,
**I want** the TOC rewritten inside the file,
**so that** the committed document is always current.

Acceptance criteria:
- With `--in-place`, content between `<!-- toc -->` and `<!-- /toc -->` is replaced with the generated TOC.
- Content outside the markers is byte-for-byte unchanged.
- If the markers are absent, the command exits non-zero with a message naming the expected markers, and the file is not modified.
- Running the command twice in a row produces no change on the second run.

### Story 3: Enforce TOC freshness in CI
**As a** repository owner,
**I want** a check mode,
**so that** a pull request that changes headings without updating the TOC fails.

Acceptance criteria:
- With `--check`, the command exits 0 when the existing TOC matches what would be generated, and 1 when it does not.
- In check mode the file is never modified.
- On mismatch, the output identifies the file that is stale.

## Functional Requirements

1. Accept a path to a Markdown file as a positional argument.
2. Parse ATX headings (`#` through `######`) and derive title text and level.
3. Ignore heading-like lines inside fenced code blocks (``` and ~~~).
4. Generate GitHub-compatible anchor slugs: lowercase, spaces to hyphens, punctuation stripped, with a numeric suffix disambiguating duplicate slugs.
5. Emit a nested Markdown list, two spaces of indentation per heading level.
6. Support `--min-level` and `--max-level` to bound which headings are included.
7. Support `--in-place` to rewrite between `<!-- toc -->` / `<!-- /toc -->` markers.
8. Support `--check` to exit non-zero when the embedded TOC is stale.
9. Default (no flags) prints the TOC to stdout and leaves the file untouched.

## Non-Functional Requirements

- **Dependencies**: standard library only; no third-party runtime packages.
- **Performance**: a 10,000-line Markdown file processes in under one second.
- **Portability**: runs on Linux and macOS.
- **Exit codes**: 0 success, 1 stale TOC in check mode, 2 usage or I/O error.
- **Safety**: no command ever modifies a file unless `--in-place` is passed.

## Success Criteria

This PRD is the vehicle for a CCPM end-to-end validation, so the criteria cover both the tool and the process.

Process (primary):
- Each CCPM phase — Plan, Structure, Sync, Execute, Track — runs to its documented completion, or the point of failure is identified with the responsible component named.
- The epic decomposes into no more than 10 tasks with explicit `depends_on` and `parallel` fields.
- Task files and epic frontmatter conform to the schemas in `conventions.md`.

Product (secondary):
- All three user stories' acceptance criteria pass as automated tests.
- `--check` correctly distinguishes a fresh TOC from a stale one on a fixture document.
- Running `--in-place` twice is idempotent.

## Constraints & Assumptions

- **Constraints**: standard library only; single-file document scope; ATX headings only.
- **Assumptions**: input files are UTF-8; GitHub's anchor algorithm is the target dialect; the environment provides a working git repository and a test runner.
- **Resources**: one implementation pass within this validation session; no ongoing maintenance commitment.

## Out of Scope

- Setext headings (underlined with `===` / `---`).
- Recursing over directories or glob expansion across multiple files.
- Anchor dialects other than GitHub's (GitLab, Bitbucket, Pandoc).
- Rewriting or validating existing links in the document body.
- Configuration files; all options are command-line flags.
- Publishing to any package registry.

## Dependencies

- A language runtime with a standard library sufficient for file I/O and regular expressions, plus its test runner.
- Git, for the branch and worktree conventions CCPM applies during execution.
- GitHub API access, for the Sync phase that turns the epic and tasks into issues.
