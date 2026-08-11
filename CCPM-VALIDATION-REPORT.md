# CCPM 検証レポート (2 回目の中断)

- 対象: automazeio/ccpm upstream `7d7e462`
- 実行日: 2026-08-11
- 方針: CCPM スキル規定どおりに実行。CCPM 本体のバグは無条件修正。
  `gh` 障害への MCP 迂回は 1 回のみ許容、以降は中断。
- 結果: **Phase 4 (Execute) preflight で中断**。Phase 1–3 と 5 は完走。

## 到達状況

| Phase | 結果 |
|---|---|
| 導入 (`.claude/skills/ccpm`) | ✅ |
| `init.sh` | ⚠️ exit 0 だが 3 点の劣化 (障害 D) |
| 1. Plan (PRD → Epic) | ✅ |
| 2. Structure (7 タスク分解) | ✅ 並列エージェント 2 バッチ |
| 3. Sync (issue #11, #12–#18) | ✅ **MCP 迂回を 1 回消費** |
| 4. Execute | ❌ **中断** (gh 障害 2 回目) |
| 5. Track | ✅ 同期後の実データで全スクリプト正常 |

生成物: PRD 1、Epic 1、タスク 7、GitHub issue 8 (epic #11 + task #12–#18)、
worktree `../epic-md-toc` (branch `epic/md-toc`)。

## 修正した CCPM 本体のバグ (3 件)

いずれもネットワーク状態に依存せず、正常な GitHub 接続環境でも発生する。

### A. frontmatter 除去で本文が全消滅 (重大)

```bash
sed '1,/^---$/d; 1,/^---$/d' <file>   # → 0 バイト
```

`1,/^---$/` は開始・終了の `---` を両方含む 1 レンジで、1 回で除去は完了して
いる。2 つ目が本文先頭で再活性化し、次の `^---$` が無いため EOF まで削除する。

- 該当: `references/sync.md` Step 1 / Step 2、`references/conventions.md`
- 影響: **epic と全タスクの issue が本文空で作成される**。
  `gh issue create --body-file` は空ファイルでも成功するためエラーにならない
  (サイレントなデータ欠損)。
- 修正: `sed '1,/^---$/d'` の 1 回に変更。
- 検証: 除去結果が 0 → 7222 バイト (epic) / 3002 バイト (task)。

### B. `validate.sh` が引用符付き `depends_on` を解決できない

sed チェーンが `[`, `]`, `,` を除去するが引用符を残すため、`depends_on: ["001"]`
を `"001".md` として探し「参照先が存在しない」と誤警告する。

- 修正: `tr -d '\42\47'` を追加 (octal 指定でシェル引用の入れ子を回避)。
- 検証: 警告 8 件 → 0 件、`✅ All references valid`。

### C. `validate.sh` が CCPM 自身の生成物を invalid と判定

`sync.md` Step 6 が規定する `github-mapping.md` は frontmatter を持たないが、
`validate.sh` は `epics/` 配下の全 `.md` に frontmatter を要求するため、
CCPM が自分で作ったファイルを invalid と報告する
(`execution-status.md`、`updates/*.md` も同様)。

- 修正: 上記の bookkeeping ファイルを frontmatter 検査から除外。
- 併せて同行の `find` 演算子優先順位バグも修正。
  `-name "*.md" -path "*/epics/*" -o -path "*/prds/*"` は
  `(-name AND epics) OR (prds)` と解釈され、`prds/` 配下は拡張子を問わず
  全て走査されていた。括弧で括って修正。
- 検証: `Invalid files: 1` → `0`、`✅ System is healthy!`。

## 障害 D (未修正・CCPM のエラーハンドリング不備): `init.sh` が失敗を握り潰す

`init.sh` は exit 0 で「Initialization Complete!」を返すが実際には:

1. `gh auth status` がトークン無効でも exit 0 のため
   **「✅ GitHub authenticated」と誤報告**。同スクリプト末尾では
   「Auth: Not authenticated」と自己矛盾した表示。
2. `gh-sub-issue` 拡張のインストールが 403 で失敗。
3. `gh repo view` が 403 → 「Not a GitHub repository」と誤判定し、
   **`epic` / `task` ラベルが未作成**。

利用者は「成功」を信じて Sync に進み、そこで初めて失敗する。
今回は Sync を MCP 経由にした結果ラベルが自動生成されたため顕在化しなかった
(`gh` 経由なら `--label` 指定で失敗していたはず)。

## 中断理由: `gh` 障害の 2 回目 (Execute preflight)

```
$ gh issue view 12 --json state,title,labels,body
HTTP 403: This GraphQL query is not enabled for this session —
only the pinned set of PR-review operations is served.
```

Execute の preflight 1 番目が `gh issue view` であり、ここで停止。
preflight の他 2 項目 (ローカルタスクファイル、worktree) は充足済み。

**背景** — GitHub 自体は到達可能で、MCP 経由なら `Sut103` として認証される。
本セッションのプロキシが GitHub アクセスを MCP ツール面に限定し、シェルからの
`gh` / REST / GraphQL を遮断している。CCPM は GitHub 操作を全面的に `gh` CLI へ
ハードコードしており (`sync.md`, `execute.md`, `init.sh`)、この前提が衝突する。

**影響** — Execute (issue 分析、並列エージェント起動、`gh issue edit` による
アサイン) が実行不可。Sync の progress コメント投稿とクローズ処理も同様。
ローカル完結の Phase 1/2/5 は無影響。

## Sync を MCP 経由にしたことによる副作用 (要注意)

`gh` ではなく MCP でイシューを作成した結果、**本文がローカルファイルと一致しない**。

- HTML コメント `<!-- toc -->` `<!-- /toc -->` が本文から除去される
- `->` が `-&gt;` にエスケープされる

issue #13 を読み戻して確認済み。とりわけ #13 は「マーカーコメント間への TOC 挿入」
that itself が主題であり、GitHub 上の本文は該当箇所が空になって意味が通らない。
ローカルの `.claude/epics/md-toc/13.md` が正であり、そちらは無傷。

また `gh-sub-issue` 拡張が使えないため、`Part of #11` はテキスト参照にとどまり、
GitHub 上の親子関係は成立していない (`has_parent: false`)。

## CCPM 規定からの逸脱 (1 件、意図的)

`sync.md` Step 5 は worktree を `main` から作ると規定するが、`main` には CCPM 一式も
epic ファイルも存在しない (本検証は指定ブランチ上で実施)。規定どおり `main` を
基点にすると worktree が空になり Execute が成立しないため、
**指定ブランチ `claude/ccpm-branch-deployment-8cr8cq` を基点**とした。

これは CCPM が「epic は常に main から派生する」ことを暗黙の前提にしていることの
表れであり、フィーチャーブランチ上で CCPM を運用する場合は一般に踏む。

## 切り分け表

| # | 分類 | 根拠 |
|---|---|---|
| A | **CCPM のバグ** (修正済) | GNU sed 単体で再現。ネットワーク非依存 |
| B | **CCPM のバグ** (修正済) | スクリプト静的解析で確定。ネットワーク非依存 |
| C | **CCPM の内部不整合** (修正済) | sync.md の生成物を validate.sh が拒否 |
| D | CCPM のエラーハンドリング不備 (未修正) | 403 は環境由来、握り潰して exit 0 は CCPM 側 |
| 中断要因 | 環境 (CCPM の `gh` 依存と衝突) | MCP 経由では到達可。遮断はシェル経路のみ |

## 再開する場合の選択肢

1. Execute も MCP 経由に振り替える (CCPM 本体の改変が必要)
2. `gh` がそのまま通る環境で Execute 以降を実施
3. A–C の修正を upstream (automazeio/ccpm) へ報告する
