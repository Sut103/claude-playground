# `gh` コマンド 能力マトリクス (本セッション環境)

- 検証日: 2026-08-11
- `gh version 2.45.0`
- 対象リポジトリ: `Sut103/claude-playground`
- 検証方法: 各コマンドを実際に実行し、終了コードと出力を記録

> **重要な訂正**
> `CCPM-VALIDATION-REPORT.md` および `CCPM-OBSTACLES-AND-WORKAROUNDS.md` は
> 「`gh` は GraphQL / REST とも 403 で GitHub API に到達できない」と記載しているが、
> **これは誤り**。REST は全面的に利用可能である。本ファイルの結果が正。
> 検証当時 (06:34) の `gh api repos/...` は確かに 403 を返したが、現在は再現しない。

---

## 1. 認証の実態

```
$ env | grep -E '^(GH|GITHUB)_TOKEN'
GH_TOKEN=proxy-injected
GITHUB_TOKEN=proxy-injected
```

トークンは**プレースホルダ文字列**であり、実際の資格情報は egress プロキシが
注入する。したがって:

```
$ gh auth status
  X Failed to log in to github.com using token (GH_TOKEN)
  - The token in GH_TOKEN is invalid.
$ echo $?
0
```

この「invalid」表示は **gh がプレースホルダをローカル検証しているだけの表示上の
アーティファクト**で、実際の認証状態を表さない。無視してよい。

真の認証状態は REST で確認する:

```
$ gh api user --jq .login
Sut103
$ gh api rate_limit --jq .rate.limit
15000
```

---

## 2. できること

### 2.1 `gh api` (REST) — 対象リポジトリに対して全面的に可能

**読み取り (全て検証済み、exit 0)**

| コマンド | 結果 |
|---|---|
| `gh api user --jq .login` | `Sut103` |
| `gh api repos/$R --jq .full_name` | `Sut103/claude-playground` |
| `gh api repos/$R/labels` | 全ラベル取得 |
| `gh api repos/$R/issues --jq 'length'` | `11` |
| `gh api repos/$R/issues/11 --jq .title` | `Epic: md-toc` |
| `gh api repos/$R/issues/11/comments` | 取得可 |
| `gh api repos/$R/branches` | 19 件 |
| `gh api repos/$R/commits` | 取得可 |
| `gh api repos/$R/contents/README.md` | 取得可 |
| `gh api repos/$R/git/refs/heads` | 19 件 |
| `gh api repos/$R/pulls` | 取得可 |
| `gh api repos/$R/actions/workflows` | 取得可 |
| `gh api rate_limit` | `15000` |

**書き込み (全て検証済み、exit 0)**

| 操作 | コマンド |
|---|---|
| Issue 作成 | `gh api -X POST repos/$R/issues -f title=T -f body=B` |
| Issue 更新 | `gh api -X PATCH repos/$R/issues/$N -f 'labels[]=X'` |
| Issue クローズ | `gh api -X PATCH repos/$R/issues/$N -f state=closed -f state_reason=completed` |
| コメント投稿 | `gh api -X POST repos/$R/issues/$N/comments -f body=B` |
| ラベル作成 | `gh api -X POST repos/$R/labels -f name=X -f color=ededed` |
| ラベル削除 | `gh api -X DELETE repos/$R/labels/X` |
| **サブイシュー連結** | `gh api -X POST repos/$R/issues/$P/sub_issues -F sub_issue_id=$ID` |

**オプションも正常動作**: `--paginate`、`--jq`、`-H` (カスタムヘッダ)、`-X`、`-F`/`-f`

> サブイシュー API が使える点は重要。`gh-sub-issue` 拡張のインストールは 403 で
> 失敗するが、**GitHub ネイティブの REST サブイシュー API で代替できる**。
> 検証: 親 #37 / 子 #38 を連結後、`GET issues/37/sub_issues` が `38` を返した。
> 注意: `sub_issue_id` は issue **番号ではなく id** を渡す。

### 2.2 REST ベースの porcelain (数は少ない)

| コマンド | 結果 |
|---|---|
| `gh label create <name> --color <c>` | ✅ 動作 |
| `gh run list` | ✅ 動作 |
| `gh workflow list` | ✅ 動作 |
| `gh browse --no-browser` | ✅ 動作 (ネットワーク不要、URL 出力のみ) |
| `gh auth status` | exit 0 (ただし本文は誤解を招く) |

### 2.3 `git` は `gh` と独立して正常

```
$ git ls-remote --heads origin | wc -l    → 19
$ git clone https://github.com/Sut103/claude-playground /tmp/x   → 成功
```

`push` / `pull` も本セッション中に多数実行し、すべて成功している。

---

## 3. できないこと

### 3.1 GraphQL バックエンドの porcelain — 全滅

```
HTTP 403: This GraphQL query is not enabled for this session —
only the pinned set of PR-review operations is served.
Use REST via `gh api repos/{owner}/{repo}/...` instead.
```

| コマンド | 備考 |
|---|---|
| `gh api graphql` | 直接呼び出しも不可 |
| `gh repo view` | Sync の安全チェックで使用 |
| `gh repo clone` | `git clone` で代替可 |
| `gh issue list` / `view` / `create` / `edit` / `close` / `reopen` / `comment` | **CCPM が全面的に依存** |
| `gh pr list` / `status` / `view` / `create` | |
| `gh release list` | |
| `gh gist list` | |
| `gh label list` | **注意: `create` は通るが `list` は不可** |

`gh issue create` のエラーは特徴的で、issue 作成自体ではなく前段の
リポジトリ情報取得で落ちる:

```
HTTP 403: This GraphQL query (RepositoryInfo, sent by gh pr create/view
(repo info preamble)) is not enabled for this session.
```

### 3.2 ポリシーによる禁止 (transport を問わず不可)

| コマンド | エラー |
|---|---|
| `gh release create` | `Creating, editing, or deleting releases is not permitted for this session` |
| `gh api repos/cli/cli` | `GitHub access to this repository is not enabled for this session` (スコープ外) |
| `gh api users/octocat` | `This GitHub API path is not available: sessions are bound to their configured repositories` |
| `gh api /search/issues?q=...` | 同上 |
| `gh search issues` | 同上 |

これらは REST に書き換えても回避できない。組織のポリシー境界であり、
プロキシ README も「403/407 は再試行せず報告せよ」と明記している。

---

## 4. 判定ルール

**`gh` が使えるかどうかは、コマンドが GraphQL を叩くかどうかで決まる。**

```
GraphQL を使う porcelain  → 403、例外なし
REST を使う porcelain     → 動作
gh api (REST)             → 動作 (スコープ内リポジトリに限る)
横断・検索・リリース作成    → ポリシーで禁止 (transport 無関係)
```

迷ったら porcelain を避けて `gh api` を直接使う。プロキシのエラーメッセージ自身が
`Use REST via gh api repos/{owner}/{repo}/... instead` と誘導している。

---

## 5. CCPM への影響 (結論の訂正)

CCPM は GitHub 操作を **すべて porcelain で書いている**ため、この環境では
Sync / Execute が動かない。しかし **すべての操作に動作する REST 等価物が存在する**。

| CCPM が使う porcelain | 動作する REST 等価物 |
|---|---|
| `gh issue create --title T --body-file F --label L` | `gh api -X POST repos/$R/issues -f title=T -f body="$(cat F)" -f 'labels[]=L'` |
| `gh issue view N --json ...` | `gh api repos/$R/issues/N` |
| `gh issue edit N --add-label L` | `gh api -X PATCH repos/$R/issues/N -f 'labels[]=L'` |
| `gh issue edit N --add-assignee @me` | `gh api -X PATCH repos/$R/issues/N -f 'assignees[]=Sut103'` |
| `gh issue comment N --body-file F` | `gh api -X POST repos/$R/issues/N/comments -f body="$(cat F)"` |
| `gh issue close N` | `gh api -X PATCH repos/$R/issues/N -f state=closed -f state_reason=completed` |
| `gh repo view` (安全チェック) | `gh api repos/$R` |
| `gh label create` | そのまま動作 (または `POST repos/$R/labels`) |
| `gh extension install yahsan2/gh-sub-issue` → `gh sub-issue create --parent` | `gh api -X POST repos/$R/issues/$P/sub_issues -F sub_issue_id=$ID` |

**したがって、CCPM の GitHub 呼び出しを porcelain から `gh api` へ書き換えれば、
本環境でも MCP を使わずに完走できる。** サブイシューを含め、代替不能な操作は
ひとつもない。

これは以前の「`gh` では到達不能なので MCP で迂回するしかない」という結論の
訂正である。実際には MCP 迂回は必須ではなく、**CCPM 側を REST に寄せるという
選択肢があった**。
