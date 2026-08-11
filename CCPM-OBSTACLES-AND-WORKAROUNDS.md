# CCPM 障害・代替手段レポート

- 対象: automazeio/ccpm upstream `7d7e462`
- 実行日: 2026-08-11
- 観点: CCPM を規定どおり実行した際に発生した障害、実際のコマンド、採用した代替手段
- 関連: 欠陥そのものの分析と CCPM 評価は `CCPM-VALIDATION-REPORT.md` を参照

---

## A. 環境起因の障害 — `gh` CLI が GitHub API に到達できない

以下 6 件はすべて同一の根本原因。バイナリは正常で、**API 経路だけが遮断**されている。

### ① `gh` 未インストール (init.sh 内で自動解決)

```
$ command -v gh
$ echo $?
1
```

`init.sh` が `apt-get install gh` で自動導入し `gh version 2.45.0` として動作。
CCPM の想定どおり回復した唯一のケース。

### ② 認証チェックが誤報告

```
$ gh auth status
github.com
  X Failed to log in to github.com using token (GH_TOKEN)
  - Active account: true
  - The token in GH_TOKEN is invalid.
$ echo $?
0
```

失敗しているのに exit 0。`init.sh` は `if gh auth status &> /dev/null` で判定する
ため「✅ GitHub authenticated」と表示する。同スクリプト末尾のサマリは
「Auth: Not authenticated」と表示し、自己矛盾する。

### ③ GraphQL 遮断 → ラベル未作成

```
$ gh repo view
HTTP 403: This GraphQL query is not enabled for this session —
only the pinned set of PR-review operations is served.
Use REST via `gh api repos/{owner}/{repo}/...` instead.
```

`init.sh` はこれを「ℹ️ Not a GitHub repository - skipping label creation」と誤判定し、
**`epic` / `task` ラベルを作成せずに完了**する。Sync は `--label` でこれらを要求する。

### ④ `gh-sub-issue` 拡張のインストール失敗

```
$ gh extension install yahsan2/gh-sub-issue
could not check for binary extension: HTTP 403: GitHub access to this
repository is not enabled for this session.
```

### ⑤ BLOCKER 1 — Sync Step 1 (1 回目の中断点)

```
$ gh issue create --repo Sut103/claude-playground --title "Epic: md-toc" \
    --body-file /tmp/epic-body.md --label "epic,epic:md-toc,feature"
HTTP 403: This GraphQL query (RepositoryInfo, sent by gh pr create/view
(repo info preamble)) is not enabled for this session.
```

エラーメッセージの指示どおり REST に落としても同じ。

```
$ gh api repos/Sut103/claude-playground
HTTP 403: GitHub access is not enabled for this session.
An org admin must connect the Claude GitHub App for this organization.
```

### ⑥ BLOCKER 2 — Execute preflight (2 回目の中断点)

```
$ gh issue view 12 --json state,title,labels,body
HTTP 403: This GraphQL query is not enabled for this session ...
```

Execute の preflight 1 番目がこれ。残る 2 項目 (ローカルタスクファイル、worktree)
は充足済みだった。

### 切り分けの決め手

「GitHub に到達できない」と結論づける前に、MCP 経由の読み取りを 1 回だけ実行した。

```
mcp__github__get_me → {"login":"Sut103","id":18696845, ...}   成功
```

これにより **認証情報の問題ではなく、シェル経路のみが遮断されている**と確定。
CCPM は GitHub 操作を全面的に `gh` へハードコードしており
(`sync.md` / `execute.md` / `init.sh`)、この前提と衝突する。

---

## B. 代替手段の対応表

| CCPM 規定コマンド | 採用した代替 | 等価性 |
|---|---|---|
| `gh issue create --repo ... --label ...` | `mcp__github__issue_write` (method: create) | ✅ |
| `gh issue view <N> --json ...` | `mcp__github__issue_read` (method: get) | ✅ |
| `gh issue edit <N> --add-assignee @me --add-label "in-progress"` | `mcp__github__issue_write` (method: update, assignees/labels) | ✅ |
| `gh issue comment <N> --body-file` | `mcp__github__add_issue_comment` | ✅ |
| `gh issue close <N>` | `mcp__github__issue_write` (update, state: closed, state_reason: completed) | ✅ |
| `gh label create "epic" --color ...` | 代替不要 — REST の issue 作成が未知ラベルを自動生成 | ⚠️ 偶然の回復 |
| `gh extension install yahsan2/gh-sub-issue` | **代替なし** | ❌ |
| `gh sub-issue create --parent <N>` | 本文冒頭に `Part of #11` を記載 | ❌ 親子関係は不成立 |

ラベルの行が「偶然の回復」なのは、③で未作成のままだった `epic` / `task` を
REST の issue 作成が自動生成したため。`gh` 経由なら `--label` 指定の時点で
失敗していたはずで、**迂回したことで障害③が顕在化しなかった**。

### 迂回のコスト (副作用)

`gh` ではなく MCP で書き込んだ結果、**issue 本文がローカルファイルと一致しない**。
issue #13 を読み戻して確認済み。

- HTML コメント `<!-- toc -->` `<!-- /toc -->` が本文から除去される
- `->` が `-&gt;` にエスケープされる

#13 は「マーカーコメント間への TOC 挿入」自体が主題であり、GitHub 上の本文は
該当箇所が空になって文意が通らない。またサブイシュー拡張が使えないため
`has_parent: false` で、親子関係はテキスト参照どまり。
**ローカルファイルが正**という前提でのみ成立している状態。

---

## C. CCPM 本体のバグを露呈させたコマンド

### A. frontmatter 除去で本文が全消滅 (重大)

Sync Step 1 を実行した瞬間に判明。

```
$ sed '1,/^---$/d; 1,/^---$/d' .claude/epics/md-toc/epic.md > /tmp/epic-body.md
$ wc -c < /tmp/epic-body.md
0
$ sed '1,/^---$/d' .claude/epics/md-toc/001.md | wc -l
97
```

`---` を 3 本持つファイルで機構を確定させた (本文が消え `more` だけ残存)。
**`gh issue create --body-file` は空ファイルでも成功する**ため、403 が先に
出ていなければ全 issue が本文空のまま「Sync 成功」していた。

### B. `validate.sh` が引用符付き `depends_on` を解決できない

```
$ bash references/scripts/validate.sh
⚠️ Task 002 references missing task: "001"     ← 001.md は実在する
(同種 8 件)
```

`validate.sh:47` の sed が `[`, `]`, `,` を除去して引用符を残し、`:55` で
`"001".md` を探して外れる。

修正の途中でスクリプトを壊した記録も残す。

```
$ bash -n validate.sh
validate.sh: line 47: unexpected EOF while looking for matching `''
```

シェル引用の入れ子が原因。octal 指定 `tr -d '\42\47'` に変えて解決。

### C / E. CCPM 自身の生成物を invalid 判定

実行して初めて出るタイプ。どちらも `sync.md` が「そう作れ」と規定したものを
`validate.sh` が拒否する内部不整合。

```
Sync Step 6 直後:  ⚠️ Missing frontmatter: github-mapping.md
Archive 直後:      ⚠️ Missing epic.md in archived
```

### D. Execute の状態分裂 (静的解析では検出不能)

エージェントからの「`12-analysis.md` が存在しない」という報告が発端。

```
worktree:        .claude/epics/md-toc/updates/12/stream-A.md → status: completed
main リポジトリ:  .claude/epics/md-toc/updates/12/stream-A.md → status: in_progress
```

`execute.md` が `.claude/epics/` の状態をどの作業コピーが保持するか規定して
いないため、メインセッションの書き込みと worktree のエージェントが互いに
見えない。**並列エージェントを実走させないと出ない欠陥**。

---

## D. 設計前提の衝突 (コマンドは通るが規定どおりでは破綻する)

### worktree の基点

`sync.md` Step 5 の規定:

```
git checkout main && git pull origin main
git worktree add ../epic-md-toc -b epic/md-toc
```

`main` には CCPM 一式も epic ファイルも存在しないため、規定どおり実行すると
**worktree が空になり Execute が成立しない**。指定ブランチ基点に変更した。

```
$ git worktree add ../epic-md-toc -b epic/md-toc     # HEAD = 指定ブランチ
```

CCPM が「epic は常に main から派生する」を暗黙の前提にしていることの表れで、
フィーチャーブランチ運用では一般に踏む。マージも同様に指定ブランチへ向けた
(`git push origin --delete epic/md-toc` は未 push のため不要)。

### アーカイブが未クローズ課題を不可視化する

マージ手順どおり実行した結果:

```
$ mv .claude/epics/md-toc .claude/epics/archived/
$ bash references/scripts/status.sh
📚 Epics: Total: 0        # アーカイブ済みは集計外
📝 Tasks: Open: 0         # 未クローズの #22 が消えた
$ bash references/scripts/next.sh
📊 Summary: 0 tasks ready to start
```

未完了作業が追跡系から完全に消える。修正には設計判断が要るため報告にとどめた。

---

## E. まとめ

| 分類 | 件数 | 対応 |
|---|---|---|
| 環境起因 (`gh` 遮断) | 6 | MCP へ振り替え (許諾 2 回)。sub-issue のみ代替不能 |
| CCPM 本体のバグ | 5 | 全て修正済 (A/B/C/D/E) |
| CCPM の未修正課題 | 2 | 報告のみ (init の握り潰し、アーカイブの不可視化) |
| 設計前提の衝突 | 2 | 逸脱して続行、理由を記録 |

環境起因の 6 件は本セッション固有だが、**CCPM 本体のバグ 5 件は接続が正常な
環境でもそのまま発生する**。

upstream への報告価値:

1. **A (frontmatter 除去)** — 全 issue が本文空になるうえエラーを出さない。最優先。
2. **D (状態分裂)** — スクリプトを読むだけでは発見できず、並列実行を実走させた
   本検証で初めて顕在化した。CCPM の中核機能である並列エージェント実行に直結する。
3. B / C / E — いずれも `validate.sh` の信頼性に関わる。
