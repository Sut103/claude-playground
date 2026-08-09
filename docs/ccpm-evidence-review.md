# CCPM 非互換仮説の外部裏付け／反証レビュー

**調査日: 2026-08-09 / 対象: [`docs/ccpm-addendum.md`](./ccpm-addendum.md) 第 3 章で挙げた「CCPM が Claude Code クラウドで動かないであろう事象」**

前回までの検証はすべて**このセッション内での実測**だった。本レポートはそれを離れ、公式ドキュメント・CCPM 本体のソースと Issue・GitHub CLI のソースと Issue・anthropics/claude-code の Issue・第三者の実践記事をインターネットから広く収集し、**各仮説を裏付ける情報と否定する情報の双方**を突き合わせたものである。

実測とは独立した情報源を優先し、実測と食い違う場合はその食い違い自体を記録した。

---

## 0. 総括

| # | 仮説（addendum の主張） | 外部証拠の判定 | 一言 |
| --- | --- | --- | --- |
| 1 | GraphQL がプロキシで拒否され `gh-sub-issue` が動かない | **確証（公式ドキュメントに明記）** | 仕様として文書化されている。ただし CCPM 側に fallback がある |
| 2 | `gh` CLI が pre-install されていない | **確証（公式ドキュメントに明記）** | 対策も公式に示されている。**軽微** |
| 3 | `gh` の高レベルサブコマンドが軒並み GraphQL 依存 | **確証（cli/cli のソースコード）** | `gh issue list` は GraphQL 実装。影響は CCPM の広範囲に及ぶ |
| 4 | repo スコープ REST 403 はサーフェス依存（App でもネットワークでもない） | **確証。かつ公式ドキュメントが 3 点すべてを裏付け** | 同種の未解決 Issue が複数存在 |
| 5a | worktree 並列は push 制限で成立しない | **部分的に反証** — 制限は「現在のブランチのみ」ではなく `claude/*` プレフィックス | **仮説の記述が不正確。要修正** |
| 5b | 4 vCPU / 16 GB で 12 エージェント並列は無理 | **確証（スペックは公式）／ただし前提の「12」は誤り** | CCPM の実際の記述は「5 エージェント」 |
| 6 | skill の symlink インストールがクラウドに届かない | **確証。ただし公式の代替が 2 つある** | symlink 自体は追跡される。壊れるのは絶対パスの参照先 |
| 7 | Routines は Issue イベントで発火できない | **確証（公式の対応イベント表）** | PR と Release のみ |
| 8 | sub-issue API は number ではなく内部 id を要求 | **確証（公式 API 仕様＋第三者の実地報告）** | REST 経路そのものは他所で動作実績あり |
| 9 | CCPM は GitHub 前提で代替経路がない | **確証（本体 Issue で GitLab 対応は未着手）** | — |

**総合すると、addendum の 9 項目のうち 7 項目は外部情報で裏付けられた。** 一方で **2 項目に不正確な記述が見つかり（5a・5b）、3 項目については「対策が想定より整っている」ことが判明した（1・2・6）。**

さらに、実測では見えていなかった**新しい阻害要因が 4 つ**見つかった（第 3 章）。これらは addendum に未記載である。

---

## 1. 各仮説の詳細

### 仮説 1 — GraphQL 拒否により `gh-sub-issue` が動かない

#### 裏付け

**(A) 公式ドキュメントが仕様として明記している。** [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) の GitHub proxy 節:

> **GraphQL restrictions**: the proxy serves only a pinned set of GraphQL operations for pull-request workflows. The proxy rejects everything else on the GraphQL endpoint with a 403 that says `This GraphQL query is not enabled for this session` and names the REST fallback, `gh api repos/{owner}/{repo}/...`. **The restriction applies to every request through the proxy regardless of the credentials you supply, so a `GH_TOKEN` you set gets the same 403.** Claude can't reach GitHub APIs that exist only in GraphQL, such as Projects v2, through the proxy.

実測で得た 403 の文言と一字一句一致する。**「自前トークンでは回避できない」という addendum の記述も公式に裏付けられた。**

**(B) `gh-sub-issue` は実際に GraphQL の `addSubIssue` mutation を使う。** [yahsan2/gh-sub-issue](https://github.com/yahsan2/gh-sub-issue) の実装がこれで、GraphQL 経由では `GraphQL-Features: sub_issues` ヘッダも要る。

**(C) CCPM の同期処理は実際にこの拡張の有無を分岐条件にしている。** [`skill/ccpm/references/sync.md`](https://github.com/automazeio/ccpm) の epic-sync フロー:

```bash
if gh extension list | grep -q "yahsan2/gh-sub-issue"
```

#### 反証・緩和

**(A) CCPM 公式が fallback を明記している。** README の Optional 節:

> `gh-sub-issue` extension: "GitHub integration — uses `gh-sub-issue` extension for proper parent-child relationships. **Falls back to task lists if not installed.**"

つまり「動かない」ではなく「階層表現が劣化する」が正しい。**このシナリオでの CCPM は停止しない。**

**(B) REST 経路が公式に存在する。** [REST API endpoints for sub-issues](https://docs.github.com/en/rest/issues/sub-issues) — `POST /repos/{owner}/{repo}/issues/{issue_number}/sub_issues`。GraphQL を一切使わずに親子関係を張れる。sub-issues は 2025-04-30 に [GA 済み](https://github.blog/changelog/2025-04-09-evolving-github-issues-and-projects/)で、preview ヘッダも不要。

**(C) プロキシのエラーメッセージ自身が REST を案内している**（上記引用の `names the REST fallback`）。これは addendum 3.6 の推奨と同じ方向である。

#### 判定

**仮説は正しいが、「動かない」は言い過ぎ。** 正確には「GraphQL 経路の sub-issue 階層が張れず、CCPM は task list へ degrade する」。REST への差し替えという公式に示された解が存在する。

---

### 仮説 2 — `gh` CLI が pre-install されていない

#### 裏付け

公式ドキュメントに明記:

> GitHub's [`gh` CLI](https://cli.github.com) **isn't pre-installed**. If you need a `gh` command the built-in tools don't cover, like `gh release` or `gh workflow run`, install and authenticate it yourself

Installed tools 表にも `gh` はない（Node/Python/Go/Rust/Ruby/Java/PHP/Docker などのみ）。CCPM は README の Prerequisites で `git` と **authenticated `gh` CLI** を required としているため、前提が満たされない。

#### 反証・緩和

**(A) 公式が setup script での導入手順を用意している。** ドキュメントの例がまさに「`gh` CLI をインストールする setup script」であり、結果は[環境キャッシュ](https://code.claude.com/docs/en/cloud-environments)としてスナップショット化され毎回は走らない。

**(B) 実測でも `apt-get install -y gh` は成功した**（2.45.0）。

**(C) 第三者が SessionStart hook による自動導入を公開している。** [Run `gh` Command in Claude Code on the Web](https://dev.to/oikon/run-gh-command-in-claude-code-on-the-web-2kp3) は `bun x gh-setup-hooks` を `.claude/settings.json` の SessionStart hook に置き、`CLAUDE_CODE_REMOTE` でクラウド環境を判定して `~/.local/bin` にバイナリを落とす方式を示している。

#### 判定

**事実だが軽微。** 公式・非公式ともに確立した回避策がある。**ただし apt 版は 2.45.0 で古い**（後述 3.2）。

---

### 仮説 3 — `gh` の高レベルサブコマンドが軒並み GraphQL 依存

#### 裏付け

**(A) cli/cli のソースコードが決定的。** [`pkg/cmd/issue/list/http.go`](https://raw.githubusercontent.com/cli/cli/trunk/pkg/cmd/issue/list/http.go) は GraphQL 実装である:

```go
"query IssueList($owner: String!, $repo: String!, $limit: Int..."
err := client.GraphQL(repo.RepoHost(), query, variables, &response)
```

`gh issue list` は REST ではなく GraphQL を叩く。実測の 403 と整合する。

**(B) 第三者も同じ壁に当たっている。** 前掲 dev.to 記事の注意書き:

> "Due to sandbox proxy configuration, you need to use the `-R owner/repo` flag when using `gh` commands."

`-R` が必要になるのは **`gh` のリポジトリ自動解決（`gh repo view` 相当）が通らない**ためで、これは GraphQL 依存の症状そのもの。独立した観測として仮説を裏付ける。

**(C) CCPM は該当コマンドを実際に使っている。** sync.md には `gh issue create` / `gh issue comment <N>` / `gh issue close $epic_issue` が並ぶ。

#### 反証・緩和

**(A) `gh api` + REST パスは明示的に許可されている**（プロキシのエラー文が案内している経路）。書き換え先は存在する。

**(B) すべてのサブコマンドが GraphQL とは限らない。** 我々が実測で GraphQL 403 を確認したのは `gh issue list` と `gh repo view` の 2 つ。`gh issue create` / `gh issue comment` / `gh issue close` は**未検証**である。`-R` を付ければリポジトリ解決を飛ばせるため、これらが REST のみで完結する可能性は残る。addendum 3.7 の「軒並み」は、確認済み 2 件からの一般化としてはやや強い。

#### 判定

**方向性は正しいが、影響範囲の見積もりに未検証部分がある。** 「`gh issue list` / `gh repo view` は確実に不可」「create/comment/close は要検証」が正確な表現。

---

### 仮説 4 — repo スコープ REST 403 はサーフェス依存

これは addendum が 3.7 → 3.8 → 3.10 と 2 度訂正した項目で、最も強い外部裏付けが得られた。

#### 裏付け

**(A) 「GitHub App の接続は access control ではない」と公式が明記。** [Use Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web):

> With either method, a cloud session can access any repository the connecting GitHub account can see, not just the repositories the Claude GitHub App is installed on. **App installation enables PR webhooks for Auto-fix; it is not a session-level access control.**

**403 のエラー文（"An org admin must connect the Claude GitHub App"）が実態を表していない**という 3.8 の訂正が、公式記述で裏付けられた。

**(B) 「GitHub 経路はネットワーク設定と独立」と公式が明記。**

> **GitHub operations use a [separate proxy](#github-proxy) that is independent of this setting**

3.10 の実測結論（ネットワークを開けても GitHub API ゲートは変わらない）と完全に一致する。しかも Trusted の[デフォルト許可ドメイン](https://code.claude.com/docs/en/cloud-environments)には `api.github.com` が最初から含まれており、**ネットワークポリシーは元から論点ではなかった**。

**(C) サーフェス依存を示す未解決 Issue が複数ある。**

| Issue | 内容 |
| --- | --- |
| [#76248](https://github.com/anthropics/claude-code/issues/76248) | 2026-07-10 頃から Cowork/remote セッションで、**自前の fine-grained PAT を渡しても** authorized repository set 外への push と API が 403。`CCR_TEST_GITPROXY=1` が新しい git-proxy 強制ルールのフラグと推測されている。open / `area:cowork` / `has repro` |
| [#70474](https://github.com/anthropics/claude-code/issues/70474) | **CCR routine セッション**から GitHub に到達できない。sandbox 外では 200 を返す PAT が sandbox 内では失敗。`stale` ラベル、メンテナ応答なし |
| [#61189](https://github.com/anthropics/claude-code/issues/61189) | クラウドセッションでは `git push` も GitHub MCP write も `.github/workflows/` 配下を変更できない（proxy の OAuth token に workflow scope がない） |

**#76248 のエラー文は我々が受け取ったものと同型で、しかも我々のセッション環境変数にも `CCR_TEST_GITPROXY=1` が存在する。** 同じ強制ルールの下にいる可能性が高い。

#### 反証・緩和

**(A) 標準サーフェスでは REST が使える前提で書かれている。** プロキシのエラー文が `gh api repos/{owner}/{repo}/...` を fallback として案内している以上、**そのパスが通るサーフェスが存在する**ことは公式が前提にしている。「クラウドでは REST も使えない」という一般化は誤り。

**(B) 自前トークンの pass-through は公式には生きている（はず）。**

> If you set a token, it passes through to the container unchanged, so your scripts, and GitHub's `gh` CLI if you install it, use it directly.

ただしこれは #76248 の報告（PAT pass-through が壊れた）と矛盾する。**ドキュメントと現実が食い違っている領域**である。

#### 判定

**3.8 / 3.10 の結論は外部情報で完全に裏付けられた。** 加えて、これが我々の環境固有の異常ではなく、**Cowork/CCR 系サーフェス全体に影響する既知の未解決問題**である可能性が高いことが分かった。

---

### 仮説 5a — worktree 並列は push 制限で成立しない

**ここで addendum の記述に誤りが見つかった。**

#### addendum の記述

> push 制限: GitHub プロキシは `git push` を**そのセッションの現在の作業ブランチに対してのみ**許可する。

#### 反証

**(A) 公式ドキュメントのルールは違う。** [Routines](https://code.claude.com/docs/en/routines) の Repositories and branch permissions:

> Claude pushes its work to branches **prefixed with `claude/`, which are always accepted**. When your prompt directs Claude to push to another branch, Claude Code checks the push first and rejects it if any of the following is true:
> * The branch is protected on GitHub
> * Someone else has an open pull request from that branch
> * The branch carries commits authored by someone other than you

**制限の軸は「現在のブランチかどうか」ではなく「`claude/` プレフィックスかどうか」である。**

**(B) 別の Issue も同じルールを報告している。** [#24535](https://github.com/anthropics/claude-code/issues/24535) "Allow pushing to the task-assigned branch, not just `claude/*` branches":

> the git proxy restricts pushes to only `claude/*` branches
> - ✅ Can push to `claude/pr-129-review-fixes-KKnEk`
> - ❌ Cannot push to `127-auto-chat-titling` (403 from proxy)

**これは CCPM にとって重大な差である。** worktree 上の各タスクブランチを `claude/epic-<name>/task-<N>` のように命名すれば、**1 セッションから複数ブランチを push できる可能性がある。** つまり worktree 並列モデルが push 制限で否定されるとは限らない。

#### 裏付け（仮説を支持する側）

**(A) デフォルトブランチへの push は harness レベルで恒久的にブロックされる。** [#56474](https://github.com/anthropics/claude-code/issues/56474) によれば、`settings.json` で明示的に許可しても main への push は通らず、無効化するフラグも環境変数も存在しない。CCPM の `epic-merge`（no-ff で main にマージして push）は**クラウドでは実行できない**。

**(B) `.github/workflows/` は push できない**（#61189）。CCPM を Actions と連携させる拡張は詰まる。

**(C) `add_repo` で追加していないリポジトリへの push は 403**（#76248）。

#### 判定

**「push 制限で worktree 並列が成立しない」は不正確。** 正しくは:

- タスクブランチを `claude/` プレフィックスで切れば、複数ブランチ push は**通る可能性が高い（未検証）**
- ただし **`epic-merge`（main への直接マージ push）は確実に不可**
- したがって worktree 並列そのものより、**CCPM のライフサイクル終端がクラウドで完結しない**ことが本質的な制約

**これは addendum で最も修正が必要な箇所であり、同時に最も安価に検証できる項目でもある**（`claude/` 付きブランチを 2 本 push してみるだけ）。

---

### 仮説 5b — 4 vCPU / 16 GB で 12 エージェント並列は無理

#### 裏付け

**スペックは公式の記述と一致する。** [Resource limits](https://code.claude.com/docs/en/cloud-environments):

> * 4 vCPUs
> * 16 GB of RAM
> * 30 GB of disk
>
> The VM may stop tasks that need significantly more memory, such as large build jobs or memory-intensive tests.

実測の `nproc` / `free -g` / `df`（4 / 15 / 30）とも一致する。

**第三者の実践報告も並列度に慎重である。** [gh-sub-issue 作者による CCPM 調査](https://zenn.dev/yahsan2/articles/claude-code-pm-parallel-development):

> 3 つ以上の並列タスクには注意深い監督が必要で、人間のアーキテクトによる調整は依然として不可欠

別の実践記事も「1 つの Claude Code セッションで複数タスクを扱うとコンテキストが混ざって破綻する」「Opus で大量処理を回すと 5 時間の使用量上限にすぐ到達する」と報告している。**物理リソースより先にレート制限とコンテキストが律速になる**という指摘は、addendum になかった視点である。

公式も同じ点を挙げている:

> **Rate limits**: Claude Code on the web shares rate limits with all other Claude and Claude Code usage within your account. Running multiple tasks in parallel consumes more rate limits proportionately.

#### 反証

**「12 エージェント」という前提が CCPM の記述と合わない。** README の実際の記述は:

> Agent 1: Database tables / Agent 2: Service layer / Agent 3: API endpoints / Agent 4: UI components / **Agent 5: Test suites**. All running **simultaneously in the same worktree**.

**CCPM が挙げるのは 5 エージェントで、しかも「同一 worktree 内」である。** addendum の「最大 12 エージェント並列」「worktree で衝突なく走らせる」は、いずれも CCPM の実際の記述とずれている。5 エージェントであれば 4 vCPU / 16 GB でも、ビルドを同時に走らせない限り成立しうる。

#### 判定

**スペック制約は事実だが、前提となる並列数が誤り。** CCPM の主張は 12 ではなく 5、しかも同一 worktree 内での並列である。**結論（クラウド 1 台での大規模並列は非現実的）は変わらないが、根拠は「リソース」より「レート制限とコンテキスト」に置くべき。**

---

### 仮説 6 — skill の symlink インストールがクラウドに届かない

#### 裏付け

**(A) CCPM の Claude Code 向け公式手順は確かに symlink である。** README:

```bash
ln -s /path/to/ccpm/skill/ccpm .claude/skills/ccpm
```

絶対パスの参照先はクラウド VM に存在しないため解決できない。

**(B) `/plugin` はクラウドセッションで使えない。** [Use Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web):

> Commands that only run in the terminal interface, such as `/plugin` or `/resume`, aren't available.

対話的なプラグイン導入は不可。

#### 反証

**(A) symlink 自体は Claude Code が追跡する。** [Skills](https://code.claude.com/docs/en/skills):

> A `<skill-name>` entry in the enterprise, personal, or project locations **can be a symlink to a directory elsewhere on disk. Claude Code follows the symlink** and reads `SKILL.md` from the target directory

**壊れるのは「symlink だから」ではなく「参照先がクラウドに存在しないから」である。** 記述の精度として重要な差。

**(B) 公式の代替が 2 つ明記されている。**

> Cloud sessions additionally **load project skills committed to the cloned repository's `.claude/skills/`**.
> For cloud sessions, you can instead commit the skill to the repository's `.claude/skills/`, **or ship it in a plugin declared in the repository's `.claude/settings.json`. Repo-declared plugins install at session start**

つまり **(1) 実ファイルを vendoring する、(2) リポジトリの `.claude/settings.json` にプラグインを宣言する** の 2 通りがあり、後者は `/plugin` が使えなくてもセッション開始時に自動インストールされる。addendum は (1) しか挙げていなかった。

**(C) CCPM は Agent Skills 標準準拠なので、`skill/ccpm/` を指すだけでよい。** README: "Point your tool at `skill/ccpm/` — it follows the open standard and activates automatically."

#### 判定

**問題は実在するが、公式の解決手段は addendum が把握していたより 1 つ多い。** リスクは低い。

---

### 仮説 7 — Routines は Issue イベントで発火できない

#### 裏付け

[Routines](https://code.claude.com/docs/en/routines) の Supported events は 2 種類のみ:

| Event | Triggers when |
| --- | --- |
| Pull request | A PR is opened, closed, assigned, labeled, synchronized, or otherwise updated |
| Release | A release is created, published, edited, or deleted |

**Issue イベントは存在しない。** 「Issue にラベルが付いたら自動着手」は webhook では組めない。

さらに addendum の記述どおり、API トリガの `text` は untrusted としてラップされる:

> The `text` value doesn't reach the routine as a bare message. It arrives wrapped in a `<routine-fire-payload>` block that labels it as untrusted data and tells Claude not to follow instructions inside it unless the routine's own prompt says to.

#### 反証・緩和

**(A) API トリガで代替できる**（addendum の記述どおり）。`/fire` エンドポイントに POST する形で、GitHub Actions から Issue イベントを中継すればよい。

**(B) ただし追加の制約が 2 つある**（addendum に未記載）:

> During the research preview, GitHub webhook events are subject to **per-routine and per-account hourly caps**. Events beyond the limit are dropped until the window resets.

> routines have a **daily cap on how many runs can start per account**

CCPM のようにタスク数だけセッションを起動する設計は、この日次上限に当たりやすい。

#### 判定

**確証。かつ addendum が把握していなかった上限（時間あたり webhook 上限・日次実行上限）が追加で見つかった。**

---

### 仮説 8 — sub-issue API は number ではなく内部 id を要求

#### 裏付け

**(A) 公式 API 仕様。** [REST API endpoints for sub-issues](https://docs.github.com/en/rest/issues/sub-issues):

> `"sub_issue_id"` (integer, required): "**The id** of the sub-issue to add"

URL には issue **number**、body には内部 **id** という非対称な設計である。

**(B) 実際に多くの人が踏んでいる。** [cli/cli#12258](https://github.com/cli/cli/issues/12258) は `gh api --method POST /repos/.../issues/152/sub_issues -F "sub_issue_id=153"` が 404 になったという報告で、153 は明らかに issue **number** である。

**(C) 原因と解を明示した第三者記事がある。** [Create GitHub issue hierarchy using the API](https://jessehouwing.net/create-github-issue-hierarchy-using-the-api/):

> "the URL contains the issue's `number` and the `sub_issue_id` is the issue's internal `id`."

```bash
gh api https://api.github.com/repos/OWNER/REPO/issues/1 --jq .id
gh api https://api.github.com/repos/OWNER/REPO/issues/1/sub_issues -X post -F sub_issue_id=3000028010
```

#### 反証（というより朗報）

**REST 経路そのものは他所で動作実績がある。** 上記記事は REST だけで親子関係の構築に成功している。**addendum 3.9 が残した唯一の未検証項目「`POST .../sub_issues` は GitHub App 経由の REST でも通るか」について、少なくとも「REST エンドポイント自体は正常に機能する」ことは第三者によって確認済み**である。残る不確実性は「Claude のプロキシを経由した場合」だけに絞られる。

**なお [cli/cli#10378](https://github.com/cli/cli/issues/10378) には HTTP 500 の報告もあるが、`platform` ラベルが付き `more-info-needed` で閉じられており、恒常的な障害を示すものではない。**

**GitHub 側の上限も CCPM の規模では問題にならない。** 親 1 件あたり[最大 100 sub-issue、ネスト 8 段](https://github.com/orgs/community/discussions/193327)。

#### 判定

**確証。かつ addendum 3.9 の「1 往復節約できる」という発見（作成レスポンスの `id` を捕まえる）は、この非対称設計への正しい対処である。**

---

### 仮説 9 — CCPM は GitHub 前提で代替経路がない

#### 裏付け

CCPM 本体の [Issue #588 "Support GitLab?"](https://github.com/automazeio/ccpm/issues) は 2025-09-03 に開かれたまま open、"Widen ecosystem" マイルストーン止まりである。GitHub Issues が source of truth という設計は動かない。

Claude Code 側も同様で、[公式の Limitations](https://code.claude.com/docs/en/claude-code-on-the-web):

> **Platform restrictions**: repository cloning and pull request creation require GitHub. GitLab, Bitbucket, and other non-GitHub repositories can be sent to cloud sessions as a local bundle, but **the session can't push results back to the remote**

#### 判定

確証。ただしこれは CCPM 導入の是非の話であって、クラウド固有の阻害要因ではない。

---

## 2. addendum の記述で修正が必要な箇所

| 箇所 | 現在の記述 | 修正すべき内容 |
| --- | --- | --- |
| 3.3 | 「push は**そのセッションの現在の作業ブランチ**に対してのみ許可」 | 実際のルールは **`claude/` プレフィックスなら常に許可**。それ以外は保護ブランチ／他者の PR／他者のコミットがある場合に拒否。**worktree 並列の否定根拠にならない可能性がある** |
| 3.3 | 「CCPM が想定する**最大 12 エージェント並列**」 | CCPM README の記述は **5 エージェント、しかも同一 worktree 内**。数字の出所が不明 |
| 3.3 | 並列不成立の根拠を「push 制限＋リソース」に置く | 実際の律速は **レート制限（アカウント共有）とコンテキスト混線**。物理リソースは二次的 |
| 3.7 | 「`gh` サブコマンドは**軒並み** GraphQL」 | 確認済みは `gh issue list` / `gh repo view` の 2 件。`gh issue create` / `comment` / `close` は未検証 |
| 3.4 | 「symlink インストールはクラウドに届かない」 | symlink 自体は Claude Code が追跡する。壊れるのは参照先。対策は vendoring **に加えてリポジトリ `.claude/settings.json` でのプラグイン宣言**もある |
| 3.1 | 「`gh-sub-issue` が動かない」→ 影響大 | CCPM は fallback を持つ。**degrade であって停止ではない** |

---

## 3. 実測でも addendum でも捉えていなかった新しい阻害要因

### 3.1 `epic-merge` がクラウドで完結しない【新規・重大】

CCPM の epic 完了処理は main への no-ff マージと push を含む。しかし Claude Code の harness はデフォルトブランチへの push を**恒久的にブロック**し、[#56474](https://github.com/anthropics/claude-code/issues/56474) によれば `settings.json` でも環境変数でも解除できない。

**CCPM のライフサイクルは PRD → Epic → Task → 実装 → `epic-merge` で閉じる設計だが、最後の 1 ステップだけはクラウドで実行できない。** PR 経由に置き換える必要がある。これは仕様変更に相当し、addendum の推奨アーキテクチャ図（第 4 章）にも反映されていない。

### 3.2 CCPM 本体に未修正の `gh` 依存バグがある【新規】

| Issue | 内容 |
| --- | --- |
| [#1024](https://github.com/automazeio/ccpm/issues/1024)（2026-05-06、open） | `sync.md` が `gh issue create --json number -q .number` を使っているが、**`gh issue create` は `--json` を受け付けない**（2.92.0 で `unknown flag: --json`）。#653 で一度修正されたはずの regression |
| [#1022](https://github.com/automazeio/ccpm/issues/1022)（2026-03-24、open） | `sync.md` の `gh sub-issue` 構文が誤っている。正しくは `gh sub-issue add "$epic_number" "$task_number" --repo "$REPO"` |

**つまり epic-sync はクラウド以前に、ローカルでも現状のドキュメント通りには通らない。** さらに我々が apt で入れた `gh` は **2.45.0**（Ubuntu 24.04 の版）で、報告に出てくる 2.92.0 より大幅に古い。CCPM を動かすなら公式リポジトリから新しい `gh` を入れる必要があり、その取得には `release-assets.githubusercontent.com` への到達が要る（前掲 dev.to 記事が Full/Custom ネットワークを要求しているのはこのため）。

### 3.3 Routines の日次・時間あたり上限【新規】

前述のとおり、GitHub webhook イベントには per-routine / per-account の時間あたり上限、routine 実行には日次上限がある。**「1 タスク = 1 クラウドセッション」に読み替える** という addendum 3.3 の提案は、この上限に正面から当たる。

### 3.4 ローカル sandbox でも `gh` は壊れる【新規・別系統】

[anthropics/claude-code#36363](https://github.com/anthropics/claude-code/issues/36363) — Claude Code の**ローカル** sandbox でも、プロキシの TLS MITM を Go の x509 verifier が拒否するため `gh` が失敗する。`excludedCommands` に `gh` を入れてもネットワークプロキシは迂回されない。

**「ローカルなら CCPM は無改修で動く」という addendum 3.8 の最終表は、sandbox を有効にしたローカル Claude Code には当てはまらない可能性がある。**（本セッションでは CA bundle が入っているため `gh api user` は 200 で、この問題は再現しない。）

---

## 4. 残る未検証項目と、最も安価な確かめ方

| # | 問い | 検証方法 | コスト |
| --- | --- | --- | --- |
| 1 | **`claude/` プレフィックス付きなら 1 セッションから複数ブランチを push できるか** | `claude/xxx-a` と `claude/xxx-b` を作って push | 1 分。**最も影響が大きい** |
| 2 | `POST .../sub_issues` は Claude のプロキシ経由 REST でも通るか | API 直接経路が有効なサーフェス、またはローカルで `ccpm-subissue-rest.sh experiment` | 1 分 |
| 3 | `gh issue create` / `comment` / `close` は `-R` 付きで通るか | repo スコープ REST が通るサーフェスで実行 | 5 分 |
| 4 | 自前 PAT を `GH_TOKEN` に設定すると repo スコープ 403 を回避できるか | 環境変数に PAT を設定して再実行 | 5 分。ドキュメントと #76248 が矛盾している領域 |
| 5 | `epic-merge` を PR ベースに置換した場合、CCPM の他の処理と整合するか | sync.md / execute.md の読解 | 30 分 |

**1 が最優先。** これが通れば addendum 3.3 の「worktree 並列は成立しない」という最重要の結論が覆り、推奨アーキテクチャ（第 4 章）が書き換わる。

---

## 5. 結論

1. **addendum の技術的判断はおおむね正しい。** 9 仮説のうち 7 つが独立した外部情報で裏付けられ、特に最も議論が揺れた仮説 4（サーフェス依存）は公式ドキュメントの 2 つの記述で決定的に確証された。

2. **一方、最も重要な仮説 5a（push 制限による worktree 並列の否定）は、公式ドキュメントと照らすと不正確である。** 制限の軸は「現在のブランチ」ではなく「`claude/` プレフィックス」であり、CCPM のブランチ命名を変えるだけで回避できる可能性がある。**この 1 点の検証が、CCPM のクラウド運用設計を最も大きく左右する。**

3. **新たに、CCPM のライフサイクル終端（`epic-merge` の main push）がクラウドで実行不可能であることが判明した。** これは push プレフィックスの話とは別に、解除手段が存在しない恒久的な制約である。

4. **CCPM 本体にも未修正の `gh` 依存バグが 2 件あり、クラウド以前の問題として epic-sync がドキュメント通りには動かない。** 導入するなら本体へのパッチ、または `gh api` REST への全面書き換えが前提になる。

5. **総じて「CCPM がクラウドで動かない」のではなく、「CCPM の 4 つの層のうち 2 つが書き換えを要する」が正確である。**

| 層 | クラウドでの状態 |
| --- | --- |
| ファイル操作・決定的スクリプト（status / standup / 検索） | **無改修で動く** |
| GitHub 同期（epic-sync / issue-sync） | **書き換え必須**（`gh` 高レベル → `gh api` REST、かつサーフェス依存） |
| 並列実行（worktree） | **要検証**（`claude/` 命名で回避できる可能性） |
| ライフサイクル終端（epic-merge） | **書き換え必須**（main push 不可、PR 経由へ） |

---

## 参考文献

**CCPM 本体**
- [automazeio/ccpm](https://github.com/automazeio/ccpm) — README、Prerequisites、インストール方法、並列エージェントの記述
- [`skill/ccpm/references/sync.md`](https://raw.githubusercontent.com/automazeio/ccpm/main/skill/ccpm/references/sync.md) — epic-sync の実装
- [Issue #1024](https://github.com/automazeio/ccpm/issues/1024) — `gh issue create --json` regression
- [Issue #1022](https://github.com/automazeio/ccpm/issues/1022) — `gh sub-issue` 構文誤り
- [yahsan2/gh-sub-issue](https://github.com/yahsan2/gh-sub-issue)
- [gh-sub-issue を作った後に Claude Code PM を調査してみた](https://zenn.dev/yahsan2/articles/claude-code-pm-parallel-development) — 拡張の作者による CCPM 分析

**Claude Code 公式ドキュメント**
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) — アクセスレベル、GitHub proxy、Installed tools、リソース上限、デフォルト許可ドメイン
- [Use Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) — GitHub 認証、App の位置づけ、Limitations
- [Automate work with routines](https://code.claude.com/docs/en/routines) — 対応イベント、ブランチ push ルール、fire payload、実行上限
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — skill の探索順、symlink、クラウドセッションでの読み込み
- [Run parallel sessions with worktrees](https://code.claude.com/docs/en/worktrees)

**anthropics/claude-code Issues**
- [#76248](https://github.com/anthropics/claude-code/issues/76248) — Cowork/remote の git proxy が PAT pass-through を遮断（`CCR_TEST_GITPROXY`）
- [#70474](https://github.com/anthropics/claude-code/issues/70474) — routine セッションから GitHub に到達できない
- [#61189](https://github.com/anthropics/claude-code/issues/61189) — `.github/workflows/` へ push できない
- [#56474](https://github.com/anthropics/claude-code/issues/56474) — デフォルトブランチ push の恒久ブロック
- [#36363](https://github.com/anthropics/claude-code/issues/36363) — ローカル sandbox の TLS で `gh` が壊れる
- [#24535](https://github.com/anthropics/claude-code/issues/24535) — push は `claude/*` ブランチのみ

**GitHub 公式・第三者**
- [REST API endpoints for sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
- [Evolving GitHub Issues and Projects (GA)](https://github.blog/changelog/2025-04-09-evolving-github-issues-and-projects/)
- [community discussion #193327](https://github.com/orgs/community/discussions/193327) — sub-issue 100 件上限
- [cli/cli#12258](https://github.com/cli/cli/issues/12258) / [cli/cli#10378](https://github.com/cli/cli/issues/10378) — sub_issues REST の 404 / 500
- [`pkg/cmd/issue/list/http.go`](https://raw.githubusercontent.com/cli/cli/trunk/pkg/cmd/issue/list/http.go) — `gh issue list` の GraphQL 実装
- [Create GitHub issue hierarchy using the API](https://jessehouwing.net/create-github-issue-hierarchy-using-the-api/) — REST で親子関係を張る実地報告
- [Run `gh` Command in Claude Code on the Web](https://dev.to/oikon/run-gh-command-in-claude-code-on-the-web-2kp3) — クラウドで `gh` を動かす実践
