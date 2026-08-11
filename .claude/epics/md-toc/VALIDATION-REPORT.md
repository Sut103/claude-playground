# CCPM 検証レポート (中断)

- 対象: automazeio/ccpm upstream `7d7e462`
- 実行日: 2026-08-11
- 方針: CCPM スキルの規定どおりに実行し、障害が出た時点で迂回せず中断する
- 結果: **Phase 3 (Sync) Step 1 で中断**。Phase 1–2 は完走。

## 到達状況

| Phase | 結果 |
|---|---|
| 導入 (skill 配置) | ✅ |
| init.sh | ⚠️ exit 0 だが 3 点の劣化を伴う |
| 1. Plan (PRD → Epic) | ✅ |
| 2. Structure (7 タスク分解) | ✅ |
| 3. Sync (GitHub issue 化) | ❌ 中断 |
| 4. Execute | 未到達 (Sync のイシュー番号に依存) |
| 5. Track | ✅ ローカル系のみ確認 |

## 障害 1 (BLOCKER): `gh` CLI が本セッションから GitHub API に到達できない

`gh issue create` が HTTP 403 で失敗:

```
HTTP 403: This GraphQL query (RepositoryInfo, sent by gh pr create/view
(repo info preamble)) is not enabled for this session — only the pinned
set of PR-review operations is served.
```

REST に迂回しても同様:

```
$ gh api repos/Sut103/claude-playground
HTTP 403: GitHub access is not enabled for this session.
```

**背景** — GitHub 自体は到達不能ではない。MCP 経由 (`mcp__github__get_me`) では
`Sut103` として正常に認証される。本セッションのプロキシは GitHub アクセスを
MCP ツール面に限定しており、シェルからの `gh` / REST / GraphQL を遮断している。
一方 CCPM は GitHub 操作を全面的に `gh` CLI へハードコードしている
(`sync.md`, `execute.md`, `init.sh`)。**この two つの前提が衝突している。**

**影響** — Sync が全面不可。Execute は実イシュー番号を前提とするため到達不能。
Track のイシュー系も同様。PRD/Epic/タスクのローカル生成 (Phase 1–2) は無影響。

**迂回策 (本セッションでは意図的に不採用)** — Sync を `gh` ではなく MCP の
`mcp__github__issue_write` 等へ振り替えれば通過可能。ただしこれは CCPM 本体の
改変にあたるため、本セッションの方針により実施していない。

## 障害 2 (CCPM 本体のバグ): frontmatter 除去でファイル全体が消える

CCPM が規定する frontmatter 除去イディオムが、**本文を丸ごと削除する**。

```bash
sed '1,/^---$/d; 1,/^---$/d' <file> > /tmp/body.md   # → 0 バイト
```

再現 (GNU sed 4.9、epic.md / 全タスクファイルで 100% 再現):

```
$ sed '1,/^---$/d; 1,/^---$/d' .claude/epics/md-toc/001.md | wc -l
0
$ sed '1,/^---$/d' .claude/epics/md-toc/001.md | wc -l   # 1 回なら正しい
97
```

**機構** — `1,/^---$/` は開始と終了の `---` を両方含む 1 レンジであり、1 回で
frontmatter 除去は完了している。2 つ目の `1,/^---$/d` は本文先頭で再活性化し、
次の `^---$` が無いため EOF まで削除する。`---` が 3 本ある場合は途中まで削除
される (検証済み: `body` が消え `more` だけ残る)。

**該当箇所** — `references/conventions.md` (Frontmatter Update Pattern),
`references/sync.md` Step 1 (epic body), Step 2 (task body)。

**影響** — GitHub 接続が正常な環境でも、**epic と全タスクのイシューが本文空で
作成される**。`gh issue create --body-file` は空ファイルでも成功するため、
エラーにならず気付けない (サイレントなデータ欠損)。障害 1 が無ければ、この
バグを踏んだまま Sync が「成功」していた。

**修正** — `sed` を 1 回にする。

## 障害 3 (軽微): `validate.sh` が引用符付き `depends_on` を解決できない

```
⚠️ Task 002 references missing task: "001"     # 001.md は実在する
```

`validate.sh:47` の sed チェーンは `[`, `]`, `,` を除去するが引用符を残すため、
`:55` で `"001".md` というパスを探して外れる。`depends_on: ["001"]` は妥当な
YAML であり、CCPM の schema (`conventions.md` / `structure.md`) は値の引用有無を
規定していない。

**影響** — 警告のみ (Errors: 0)。`blocked.sh` / `next.sh` / `standup.sh` は
`depends_on` の空判定しかしないため動作に影響しない。ただし依存グラフの実質的な
検証が機能しておらず、本物の参照切れも検出できない。

## 障害 4 (軽微): `init.sh` が失敗を握り潰して exit 0 する

`init.sh` は「✅ Initialization Complete!」と exit 0 を返すが、実際には:

1. `gh auth status` が「token is invalid」を出しても exit 0 のため
   **「✅ GitHub authenticated」と誤報告**。同じスクリプトの末尾サマリでは
   「Auth: Not authenticated」と矛盾した表示になる。
2. `gh-sub-issue` 拡張のインストールが 403 で失敗 → Sync Step 2 のサブイシュー
   経路が利用不可 (フォールバックはあるため致命的ではない)。
3. `gh repo view` が GraphQL 403 で失敗 → 「ℹ️ Not a GitHub repository」と誤判定し、
   **`epic` / `task` ラベルが未作成のまま**。Sync は `--label` でこれらを指定する
   ため、接続が回復しても最初の `gh issue create` はラベル不在で失敗する。

**影響** — init が「成功」を返すため、利用者は上記 3 点に気付かないまま Sync に
進み、そこで初めて失敗する。

## 環境由来 / CCPM 由来の切り分け

| # | 分類 | 根拠 |
|---|---|---|
| 1 | 環境 (CCPM の `gh` 依存と衝突) | MCP 経由では GitHub 到達可。遮断はシェル経路のみ |
| 2 | **CCPM 本体のバグ** | GNU sed 単体で再現。ネットワーク非依存 |
| 3 | **CCPM 本体のバグ** | スクリプト静的解析で確定。ネットワーク非依存 |
| 4 | CCPM のエラーハンドリング不備 (環境がトリガ) | 403 は環境由来だが、握り潰して exit 0 は CCPM 側 |

障害 2 と 3 はネットワーク状態に関係なく成立するため、GitHub 接続が正常な環境でも
そのまま発生する。
