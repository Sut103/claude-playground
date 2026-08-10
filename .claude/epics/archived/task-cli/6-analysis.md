---
issue: 6
title: ストア層
analyzed: 2026-08-10T12:43:28Z
estimated_hours: 3
parallelization_factor: 1.0
---

# Parallel Work Analysis: Issue #6

## Overview

本 Issue は単一のモジュール `taskcli/store.py` に閉じており、内部にさらなる並列ストリームを持たない。
**並列性は Issue の内部ではなく Issue 間にある** — #6 / #7 / #8 の 3 本が、互いにファイルを
共有しないため同時に走れる。CCPM の「Starting a Full Epic」に相当する形の並列である。

## Parallel Streams

### Stream A: ストア層
**Scope**: ストア層 の実装とその単体テスト
**Files**: `taskcli/store.py`、`tests/test_store.py`
**Can Start**: immediately（#5 パーサ層が完了済み）
**Estimated Hours**: 3
**Dependencies**: none

## Coordination Points

### Shared Files
なし。本 Issue が書き込むのは上記 2 ファイルのみ。
`taskcli/parser.py` は読み取り専用で参照する。

### Sequential Requirements
#5（パーサ層）の完了が前提。`Task` / `Priority` / `parse_line` / `format_line` の
公開 API に依存する。

## Conflict Risk Assessment

**低。** #6 / #7 / #8 は書き込み先ファイルが完全に分離している。
残るリスクは git のインデックス競合のみ — 同一 worktree・同一ブランチへ 3 エージェントが
同時にコミットするため、`index.lock` の取り合いが起こりうる。**本検証の観測対象である。**

## Parallelization Strategy

3 Issue を同時起動する。各エージェントは自分の 2 ファイルのみを `git add` し、
`git add -A` を使わない（他エージェントの作業中ファイルを巻き込まないため）。

## Expected Timeline
- With parallel execution: 3h wall time（3 本の最長）
- Without: 12h
- Efficiency gain: 50%
