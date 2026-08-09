# 補遺: CCPM スキルを導入した場合の再検討

**調査日: 2026-08-08 / 前提: [自律型AIエージェント開発プラットフォーム vs CLI由来クラウド開発環境](./ai-dev-platform-comparison.md) と同条件**

対象: [automazeio/ccpm](https://github.com/automazeio/ccpm) — GitHub Issues と Git worktree を使う、AI エージェント向けの spec-driven プロジェクト管理 Agent Skill。

---

## 0. 結論

1. **CCPM は前回レポートの Phase 1（リポジトリをエージェント可読にする）を製品化したものである。** 「計画を `docs/` にコミットして `--cloud` で渡す」という手作業の推奨パターンを、PRD → Epic → Task → GitHub Issues という追跡可能なパイプラインに構造化する。前回の提案と競合せず、それを実装する手段になる。

2. **CCPM を入れると、Claude Code は Jules 型の「タスク単位委譲」を獲得する。しかも仕様がベンダーの外にある。** 仕様は `.claude/` と GitHub Issues に残り、CCPM 自体は agentskills.io 準拠で harness 非依存（Codex 版の移植が実在する）。**Jules を併用する理由は前回よりさらに薄くなる。**

3. **一方、物理制約は一切変わらないので「ローカルを手放せない」という結論は不変。** CCPM は仕様の層であって実行基盤ではない。むしろ CCPM が想定する「最大 12 エージェント並列」は 4 vCPU / 16 GB の VM 1 台では成立しない。

4. **on the Web で使うには、検証で判明した 5 つの具体的な非互換を先に潰す必要がある。** 特に重要なのは、**並列の軸を「worktree（共有ファイルシステム）」から「1 タスク = 1 クラウドセッション（GitHub Issues 経由の協調）」に読み替えること**。

---

## 1. CCPM の前提整理

| 要素 | 内容 |
| --- | --- |
| 中核原則 | 「すべてのコードは仕様に遡れる」。会話履歴ではなくファイルと GitHub に文脈を永続化する |
| ワークフロー | PRD → Epic → Task 分解 → GitHub Issues 同期 → worktree 作成 → 並列エージェント実行 → トラッキング |
| 状態の置き場 | `.claude/prds/`、`.claude/epics/<feature>/epic.md`、`<N>.md`（同期後は Issue 番号にリネーム）、`updates/` |
| タスクのメタデータ | frontmatter に `depends_on` / `parallel` / `conflicts_with` / 受け入れ条件 / 工数見積 |
| Source of truth | **GitHub Issues**。コメントが履歴になる。Projects API に依存しない |
| 並列化 | Git worktree（例: `../epic-payment-integration/`）で複数エージェントを衝突なく走らせる |
| 配布形態 | Agent Skill（agentskills.io 仕様）。`skill/ccpm/` に `SKILL.md` + `references/` + 14 以上の bash スクリプト |
| 依存 | `git` + 認証済み `gh` CLI。オプションで `gh-sub-issue` 拡張（無い場合はタスクリストに fallback） |

**設計上の要点:** 決定的な処理（status、standup、検索）は LLM を通さず bash スクリプトで実行する。これは on the Web でも同じく効く長所で、トークンとレイテンシを食わずに状態を取れる。

---

## 2. CCPM は前回の結論をどう変えるか

### 2.1 変える点 — Jules との差が「思想の違い」から「選べる実装」に変わる

前回の整理は「Jules 型 = タスク単位の委譲 / Claude Code = セッション単位の協働」だった。CCPM を入れると Claude Code も**タスク単位の委譲構造を持つ**。しかも Jules と違い:

| | Jules 型 | Claude Code + CCPM |
| --- | --- | --- |
| タスク分解 | プラットフォームの計画エージェントが実行時に生成 | **リポジトリ内のファイル**として永続化、レビュー可能、diff が取れる |
| タスク間の依存 | 暗黙 | `depends_on` / `parallel` / `conflicts_with` として明示 |
| 追跡 | PR とタスク履歴 | GitHub Issues + コメント（人間もエージェントも同じ場所で協調） |
| 仕様の所有 | ベンダー | **自社リポジトリ** |
| 乗り換え | 不可 | agentskills.io 準拠で他 harness に移植可能 |
| ローカル実行 | 不可 | 同じ仕様でローカルでも動く |

**結論: 「Jules 的な自律委譲が欲しい」という動機は CCPM でほぼ満たせる。** しかも CCPM は Claude Code に閉じないので、「Claude Code に賭ける」リスクのヘッジとしても機能する。Jules を併用するより、CCPM を共通仕様層に置くほうが乗り換えコストが低い。

### 2.2 変えない点 — 物理制約

前回挙げた制約はどれも CCPM では解消しない。

- 4 vCPU / 16 GB RAM / 30 GB ディスク
- egress 許可リスト（社内ネットワークの「中から」ではない）
- 専用シークレットストア不在、対話的 SSO 不可
- GitHub 前提

むしろ CCPM は**リソース制約に正面から当たる**。「最大 12 エージェント同時実行」は 1 台の VM を前提にしていない数字で、ローカルの潤沢なマシンか、self-hosted 環境か、あるいは後述する「1 タスク = 1 セッション」への読み替えが要る。

### 2.3 強化される点 — 前回挙げたアンチパターンへの処方箋になる

| 前回のアンチパターン | CCPM がどう効くか |
| --- | --- |
| 曖昧なまま `--cloud` に投げる | PRD と受け入れ条件が構造的に強制されるので、Jules 型の弱点（曖昧な要件を推測される）を回避できる |
| セッション共有に秘密が載る | チームの共有状態が GitHub Issues になるので、セッションリンクを共有する必要が減る |
| run が緑だから成功とみなす | 受け入れ条件と Issue コメントで成否を判定できる |
| ローカルの暗黙知が届かない | `.claude/` に仕様を集約する運用そのものが Phase 1 と一致する |

---

## 3. Claude Code on the Web での非互換（本セッションで実測）

以下は本レポートを書いている Claude Code cloud セッション内で実際に確認した結果である。

### 3.1 GraphQL がプロキシで拒否される → `gh-sub-issue` が動かない【実測・要対策】

```
$ curl -H "Authorization: Bearer $GITHUB_TOKEN" \
    -d '{"query":"query { viewer { login } }"}' https://api.github.com/graphql
HTTP 403
{"message":"This GraphQL query is not enabled for this session — only the pinned set of
  PR-review operations is served. Use REST via `gh api repos/{owner}/{repo}/...` instead."}
```

`gh-sub-issue` は GitHub の **`addSubIssue` GraphQL mutation** を使う。したがって Anthropic ホストのクラウドセッションでは**親子 Issue リンクを張れない**。ドキュメント上もこの制限は「供給した資格情報にかかわらず適用される」とされており、自前の `GH_TOKEN` を入れても回避できない。

**影響:** `epic-sync` が sub-issue を作れず、CCPM のタスクリスト fallback になる。Epic の階層が平坦化し、Issue 一覧の見通しが落ちる。

**対策の優先順位は 3.6 の検証結果を踏まえて次のとおり:**

1. **`gh api` の REST 呼び出しに差し替える。** bash スクリプトのまま、ローカルでもクラウドでも同一コードで動く唯一の解（3.6 参照）。
2. **モデルが判断しながら行う操作は組み込み MCP ツールに寄せる。** プロキシの GraphQL 制限を受けない別経路であることを実測済み（3.6）。
3. **`epic-sync` だけローカルで実行する。** 暫定回避としては最も単純。
4. **fallback のまま運用する。** CCPM は元々 fallback を持つので動きはする。

### 3.2 `gh` CLI が pre-install されていない【実測・要対策】

```
$ command -v gh          → not installed
$ echo $GH_TOKEN         → proxy-injected
$ echo $GITHUB_TOKEN     → proxy-injected
$ nproc / free -g / df   → 4 vCPU / 15 GB / 30 GB avail
```

CCPM の 14 以上の bash スクリプトは `gh` を前提にしている。

**対策:**
- Cloud environment の **setup script** に `apt update && apt install -y gh` を入れる。結果はスナップショットとしてキャッシュされ、毎セッション走るわけではない（5 分以内に終わり exit 0 すること）。
- **`GITHUB_TOKEN` を直接読むスクリプトがないか確認する。** 直読みするとプレースホルダ文字列 `proxy-injected` を掴んで失敗する。`gh` 経由であればプロキシが実トークンに差し替えるので問題ない。

### 3.3 worktree 並列モデルが 1 セッション内では成立しない【要設計変更・最重要】

worktree の作成自体は VM 内で正常に動く（実測済み）。問題は 2 つある。

- **push 制限:** GitHub プロキシは `git push` を**そのセッションの現在の作業ブランチに対してのみ**許可する。CCPM の epic worktree は複数のタスクブランチを扱うため、複数ブランチへの push が弾かれる。
- **リソース:** 4 vCPU / 15 GB で 12 エージェントがそれぞれビルドとテストを走らせるのは物理的に無理。

**→ 並列の軸を付け替える。**

| | ローカル | Claude Code on the Web |
| --- | --- | --- |
| 並列の単位 | worktree（1 マシンに N エージェント） | **1 タスク = 1 クラウドセッション** |
| 隔離 | 共有ファイルシステム上のディレクトリ分離 | **VM ごと分離**（各 4 vCPU / 16 GB） |
| 協調 | ファイル + Issue | **GitHub Issues とコメント** |
| ブランチ | epic ブランチ配下に複数 | セッションごとに 1 本（push 制限に当たらない） |

具体的には、`claude --cloud "Work on issue #N following .claude/epics/<feature>/N.md"` をタスク数だけ投げる。CCPM が既に `parallel: true` / `conflicts_with` でどのタスクが同時実行可能かを持っているので、**投げる対象の選定はそのまま使える**。

重要なのは、**これが CCPM の設計から外れていないこと**である。CCPM は「Issues が source of truth、コメントが履歴」と定義している。worktree は「1 マシンに複数エージェントを詰め込むための最適化」であって、CCPM の本質ではない。クラウドでは VM そのものが隔離を提供するので、worktree 層は不要になる。

### 3.4 skill の symlink インストールはクラウドに届かない【要対策】

CCPM の Claude Code 向け手順は次の形である。

```
ln -s /path/to/ccpm/skill/ccpm .claude/skills/ccpm
```

絶対パスの symlink をコミットしても、クラウド VM ではその先が存在しないため解決できない。

**対策:** skill の実体をリポジトリに vendoring する（`.claude/skills/ccpm/` に実ファイルとしてコミットする）。バージョン更新を追いたい場合は git submodule も選択肢だが、クラウドセッションのクローンで submodule が初期化されるかは要確認。最も確実なのは実ファイルのコミットで、これは前回レポートの Phase 1 の方針とも一致する。

### 3.5 Routines は Issue イベントで発火できない【制約】

Routines の GitHub トリガが対応するイベントは **Pull request と Release のみ**で、`issues.assigned` や `issues.labeled` は無い。したがって「Issue にラベルが付いたら自動でタスク着手」を webhook で組むことはできない。

**対策:**
- **API トリガ**（routine ごとの `/fire` エンドポイントに POST）を GitHub Actions から叩く。Issue イベントを Actions で受けて routine を起動する形になる。
- または**スケジュール実行**で未着手 Issue をポーリングする。
- 注意: `text` として渡した内容は `<routine-fire-payload>` で untrusted としてラップされる。routine の prompt 側で「payload を参照して動け」と明示しないと、不活性なコンテキスト扱いになって無視される。

### 3.6 補論 — GitHub への到達経路は 3 つあり、詰まるのは 1 つだけ【実測】

3.1 を受けて「`gh` ではなくクラウドセッションに組み込まれた MCP を使えばよいのでは」という検討を行い、同一セッション内で読み取り専用の比較検証をした。

```
# (A) VM 内から直接叩く経路 ── CCPM の gh スクリプトが使う経路
$ curl .../graphql        → 403  "This GraphQL query is not enabled for this session"
$ curl .../repos/{o}/{r}  → 403  "GitHub access is not enabled for this session"

# (B) 組み込み GitHub MCP ツール経由
mcp__github__get_me          → 200  認証済みユーザのプロフィールを返す
mcp__github__list_issues     → 200  ページングが pageInfo / endCursor 形式
mcp__github__sub_issue_write → add / remove / reprioritize を提供
```

**結果: 同一セッション内で、VM から直接叩くと 403 になる操作が MCP ツール経由では通る。** これはドキュメントの「connector traffic travels through Anthropic's servers rather than the session's network」と整合する。しかも `list_issues` のページング契約が `pageInfo` / `endCursor` という GraphQL の形をしていることから、**MCP サーバ自体はサーバ側で GraphQL を使っており、それが正常に動いている**。VM 内プロキシの GraphQL 制限とは無関係の経路である。

**したがってボトルネックは `gh` ではなく「VM 内から GitHub API を直接叩く経路」だった。** 3.1 の記述はこの点で不正確だったので上記のとおり優先順位を改めた。

> 書き込み（実際に sub-issue を張る）は未検証。リポジトリに Issue を作成する操作になるため実行していない。読み取り側の結果と `sub_issue_write` の存在から通る見込みは高いが、本番投入前に検証用リポジトリで確認すること。

#### ただし MCP は `gh` の単純な代替にはならない

| 差分 | 内容 |
| --- | --- |
| **呼び出し主体** | `gh` は bash スクリプトから呼べる。MCP ツールは**モデルしか呼べない**。CCPM は「決定的な処理は LLM を通さず bash で」という設計思想を持ち、14 以上のスクリプトがその実装。MCP に寄せるとこの層が使えなくなる |
| **コストと決定性** | Issue 操作 1 回ごとにモデルのターンを消費する。10 タスクの一括同期のようなループがモデルの根気に依存し、非決定的になる |
| **ID 体系** | `sub_issue_write` は issue number ではなく **`sub_issue_id`** を要求する。CCPM のタスクファイルは Issue 番号でリネームされる設計なので、番号 → ID の解決が一段挟まる |
| **二重実装** | ローカルは `gh`、クラウドは MCP、では「同じ仕様がどこでも動く」という CCPM の利点が崩れる。※ローカル側で GitHub MCP server を `.mcp.json`（project scope）に追加すれば経路を統一できるが、認証は PAT などの別管理になる |

#### より良い解 — プロキシのエラーメッセージ自体が答えを言っている

```
Use REST via `gh api repos/{owner}/{repo}/...` instead.
```

GitHub には sub-issues の REST エンドポイントがある。

```
POST /repos/{owner}/{repo}/issues/{issue_number}/sub_issues   （body に sub_issue_id）
```

つまり **`gh sub-issue add` を `gh api` の REST 呼び出しに置き換えれば、bash スクリプトのまま、ローカルとクラウドで同一コードが動く。** CCPM の設計を壊さない解はこれである。ID 解決は `gh api repos/{o}/{r}/issues/{n} --jq .id` で一行で済む。

#### 推奨 — 「MCP か gh か」ではなく「誰が呼ぶか」で分ける

| 層 | 使うもの | 理由 |
| --- | --- | --- |
| CCPM の決定的スクリプト（status / standup / 検索 / ファイル操作） | 素の bash + git | そもそも GitHub API に触らない。どこでも動く |
| GitHub への一括同期（`epic-sync` などループを伴うもの） | **`gh api` の REST** | スクリプトから呼べる・決定的・ローカルとクラウドで同一コード |
| モデルが文脈を見て行う個別操作（Issue コメント、状況に応じた sub-issue 張り替え、PR 作成） | **組み込み MCP ツール** | プロキシ制限を受けない・認証設定不要・引数を文脈から組める |

この分け方なら、CCPM の「決定的な処理は bash で」という設計を保ったまま、モデル駆動の部分だけ MCP の利点（プロキシ迂回・ゼロ設定認証）を取り込める。

### 3.7 REST 経路の実地検証 — `gh` サブコマンドは軒並み GraphQL を使う【実測】

3.6 の「`gh api` の REST に寄せる」という結論を、実際に `gh` を導入して検証した。**結果として当初の推奨は条件付きに修正が必要**である。

`apt-get install -y gh` は Ubuntu リポジトリから成功する（2.45.0）。その上でプロキシの許可境界を測った。

| 呼び出し | 結果 |
| --- | --- |
| `gh api user` | **200** `Sut103` |
| `gh api rate_limit` | **200** `15000` |
| `gh api repos/{owner}/{repo}` | **403** `GitHub access is not enabled for this session. An org admin must connect the Claude GitHub App for this organization.` |
| `gh api repos/cli/cli`（未アタッチのリポジトリ） | **403** `GitHub access to this repository is not enabled for this session. Use add_repo to request access.` |
| `gh api user/repos`（横断列挙） | **403** `This GitHub API path is not available: sessions are bound to their configured repositories.` |
| `gh api graphql` | **403** pinned-set 制限 |
| `gh issue list` | **403 GraphQL の pinned-set 制限** |
| `gh repo view` | **403 GraphQL の pinned-set 制限** |
| `git ls-remote` / `git push`（対照） | **成功** |

#### 判明したこと

**(1) `gh` の高レベルサブコマンドは内部で GraphQL を使うため、クラウドセッションでは軒並み動かない。**
`gh issue list` と `gh repo view` が返したのは repo スコープの 403 ではなく、**GraphQL の pinned-set 制限**だった。つまり `gh sub-issue` だけの問題ではない。**CCPM のスクリプトが `gh issue list` / `gh issue view` / `gh repo view` を使っている箇所はすべて書き換えが要る。** 使えるのは `gh api` + REST パスだけである。これは 3.1 で見積もっていたより影響範囲が広い。

**(2) REST にも複数段のゲートがある。**
- **ユーザ/グローバルスコープ**（`user`、`rate_limit`）は通る。資格情報の差し替え自体は正常に機能している
- **リポジトリスコープ**は 403。エラー文は「Claude GitHub App を org に接続せよ」と言うが、**これは誤解を招く表示である**（下記 3.8）
- **横断列挙エンドポイント**（`user/repos` など）はそもそも提供されない。`repos/{owner}/{repo}/...` の形に限られる

**(3) git 自体は別系統で、影響を受けない。** clone / fetch / push は通常どおり動く。詰まるのは GitHub **API** の経路だけである。

#### 本セッションでは実験を完了できなかった

親子 Issue を REST だけで紐づける実験は、上記 (2) の org ゲートにより `repos/{owner}/{repo}/issues` の時点で 403 となり実行できなかった。本セッションは GitHub への到達を MCP サーバ経由に限定した構成であり、VM 内からの直接 API 経路が有効化されていない。

実行するには次のいずれかが要る。

1. **Claude GitHub App を org に接続する**（<https://github.com/apps/claude>）。接続後は同じセッションで `gh api` REST が通るようになる見込み
2. **標準の Claude Code on the Web セッション**（claude.ai/code）で実行する。オンボーディング時に GitHub App を接続していれば有効になっている
3. **ローカルで `gh auth login` 済みの環境**で実行する。プロキシを介さないので制限を受けない

そのまま流せる実装を [`docs/examples/ccpm-subissue-rest.sh`](./examples/ccpm-subissue-rest.sh) に置いた。GraphQL も `gh` の高レベルサブコマンドも使わず、`gh api` の REST のみで構成してある。

```bash
./docs/examples/ccpm-subissue-rest.sh check        # どの層で詰まっているかを切り分ける
./docs/examples/ccpm-subissue-rest.sh experiment   # 親子 Issue を作って REST で紐づけ検証
./docs/examples/ccpm-subissue-rest.sh add 12 34    # 実運用: #34 を #12 の sub-issue にする
```

`gh repo view` を避けて `git remote` からリポジトリ名を導出しているのも、(1) の制約への対応である。

### 3.8 訂正 — 403 の原因は GitHub App ではなく「起動サーフェス」だった【実測】

3.7 では repo スコープの 403 を「Claude GitHub App が org に未接続だから」と判断したが、**これは誤りだった**。リポジトリ所有者に確認したところ App は接続済みであり、追加検証でも次のとおり矛盾しない結果が出た。

| 確認項目 | 結果 |
| --- | --- |
| Claude GitHub App の接続 | **接続済み**（所有者確認） |
| セッションへのリポジトリ添付 | **push スコープで添付済み**（`add_repo` が `already_present` を返す） |
| `git ls-remote` / `git push` | **成功**（git 経路は正常） |
| `gh api user` | **200** |
| `gh api repos/{owner}/{repo}`（大文字・小文字とも） | **403** |
| `gh api repos/{owner}/{repo}/contents/README.md` | **403** |

つまり **App も添付も git も正常なのに、repo スコープの GitHub API だけが通らない**。エラー文の「An org admin must connect the Claude GitHub App」は、この状況では実態を表していない。

原因は**セッションを起動したサーフェスの構成**である。本セッションは Claude Code Remote 系のサーフェスで動いており、その構成では **VM 内からの GitHub API 直接アクセスが設計上無効化され、GitHub への到達は MCP サーバ経由に一本化されている**（セッション自身のシステムプロンプトにも「直接の GitHub API アクセスは無い、GitHub MCP ツールを使え」と明記されている）。`add_repo` を `access=push` で呼び直しても状況は変わらなかった。

#### これが CCPM にとって意味すること

3.7 で書いた「App 接続が前提条件」よりも、**さらに厄介な事実**が出てきた。

> **GitHub API の到達性は「Claude Code がクラウドで動いているか」ではなく、「どのサーフェスがそのセッションを起動したか」で決まる。**

同じアカウント・同じリポジトリ・同じ GitHub App でも、起動元が違えば `gh api` が通ったり通らなかったりする。CCPM の運用上、これは次を意味する。

1. **「クラウドでは `gh api` REST を使う」という前提を一般化できない。** チームが使うサーフェスを固定し、そこで実測して初めて前提にできる
2. **preflight チェックを必須にする。** epic の同期が途中まで進んで失敗すると、Issue とローカルのタスクファイルの整合が崩れる。`ccpm-subissue-rest.sh check` 相当を同期処理の先頭で必ず走らせ、通らなければ**何も書き込まずに中断**する設計にする
3. **サーフェスをまたいで運用するなら二経路を持つしかない。** スクリプト用（`gh api` REST）とモデル用（MCP ツール）の両方を実装し、preflight の結果で切り替える。これは CCPM の「決定的処理は bash」という思想を部分的に諦めることを意味する

#### 3.6 / 3.7 の推奨の最終形

| 実行環境 | 使える経路 | CCPM への影響 |
| --- | --- | --- |
| ローカル | `gh` 全機能 + REST | 無改修で動く |
| クラウド（API 直接経路が有効なサーフェス） | **`gh api` REST のみ**（高レベルサブコマンドは不可） | スクリプトを `gh api` 形式に書き換えれば、ローカルと同一コードで動く |
| クラウド（API 直接経路が無効なサーフェス） | **MCP ツールのみ** | bash スクリプト層が使えない。モデル駆動に倒すしかなく、CCPM の設計上の利点が大きく削がれる |

判断のために必要なのは App の接続確認ではなく、**チームが実際に使うサーフェスで `gh api repos/{owner}/{repo}` が通るかを 1 回測ること**である。所要 1 分で、Phase 1 の最初にやるべき項目はこれに置き換わる。

### 3.9 sub-issue 紐づけの実地検証（MCP 経路）【実測・成功】

REST 経路がこのサーフェスで使えないため、まず MCP 経路で「そもそも CCPM が要求する sub-issue 階層をこのリポジトリで張れるのか」「number → id の変換という契約は本当に必要か」を確定させた。`Sut103/claude-playground` に検証用 Issue を 2 本作成して実施した（検証後クローズ済み）。

| 手順 | 結果 |
| --- | --- |
| 親 Issue 作成 | `#1` / `id=5100355234` |
| 子 Issue 作成 | `#2` / `id=5100355274` |
| `sub_issue_write(add, issue_number=1, sub_issue_id=5100355274)` | **成功** — `sub_issues_summary: {total: 1, completed: 0}` |
| `issue_read(get_sub_issues, #1)` | `#2` を返す。子側に `parent_issue_url` が付与される |
| `issue_read(get_parent, #2)` | `#1` を返す |

**双方向で階層が成立している。** CCPM が前提とする Epic → Task の親子構造は、このリポジトリで問題なく表現できる。

#### 確定した契約と、実装上の収穫

**(1) sub-issue API は issue number ではなく内部 id を要求する。** 3.6 の想定どおりで、これは REST・MCP どちらの経路でも同じである。

**(2) ただし Issue 作成のレスポンスが `id` を返すため、追加の lookup は不要。**

```json
{"id":"5100355274","url":"https://github.com/Sut103/claude-playground/issues/2"}
```

CCPM の `epic-sync` は **Issue を自分で作る**側なので、作成時に `id` を捕まえておけば number → id の解決 API を叩く必要がない。**タスク 1 本あたり 1 往復節約できる。** `docs/examples/ccpm-subissue-rest.sh` の `experiment` はこの形に更新した。

```bash
# 作成と同時に number と id を取る
read -r num id < <(gh api --method POST "repos/$REPO/issues" \
  -f title="$title" -f body="$body" --jq '"\(.number) \(.id)"')
```

既存 Issue を後から紐づける場合（`add` サブコマンド）は従来どおり `gh api repos/{o}/{r}/issues/{n} --jq .id` での解決が要る。

**(3) 実行主体は Claude GitHub App だった。** レスポンスの `performed_via_github_app` が `anthropics/claude`（App ID 1236702）を示しており、App の購読イベントにも `sub_issues` が含まれている。**3.8 の訂正——「repo スコープの 403 は App の問題ではない」——を決定的に裏付ける結果である。** App は接続済みで、現に書き込みを実行している。

#### 残っている未検証部分

MCP 経路で**契約と機能は確定した**が、**REST 経路そのものは未検証のまま**である。残る問いは一つに絞られた。

> `POST /repos/{owner}/{repo}/issues/{n}/sub_issues` が、GitHub App 経由の REST でも同じように通るか。

`docs/examples/ccpm-subissue-rest.sh experiment` をローカルまたは API 直接経路が有効なサーフェスで実行すれば確定する。CCPM の bash スクリプト層をクラウドで使えるかは、この 1 点にかかっている。

### 3.10 追試 — ネットワークポリシーを開放しても GitHub API ゲートは変わらない【実測】

**調査日: 2026-08-09 / 別セッション（`claude/ccpm-verification-check-lfny0d`）**

3.8 では repo スコープ 403 の原因を「起動サーフェスの構成」と結論した。これを、**一般の外向き通信ポリシーを開放した環境**で追試し、両者が独立していることを切り分けた。

#### 開いていた側

`GET $HTTPS_PROXY/__agentproxy/status` は `"selective": false`（ドメイン許可リストなし）を返し、実際に一般宛の通信が通る。

| 宛先 | 結果 |
| --- | --- |
| `example.com` / `google.com` / `pypi.org` / `raw.githubusercontent.com` | 200 |
| `api.openai.com` | 401（= 到達している） |
| `git ls-remote https://github.com/cli/cli`（未アタッチのリポジトリ） | 成功 |
| `apt-get install -y gh` | 成功（2.45.0） |

#### 閉じたままだった側

同一セッションで `docs/examples/ccpm-subissue-rest.sh check` と生 curl を流した結果は、**3.7 の表と全項目一致**した。

| 呼び出し | 3.10（ネットワーク開放後） | 3.7 |
| --- | --- | --- |
| `GET /user` | 200 `Sut103` | 200 |
| `GET /rate_limit` | 200（15000） | 200 |
| `GET /repos/{owner}/{repo}` | **403** | 403 |
| `GET /repos/{owner}/{repo}/contents/README.md` | **403** | 403 |
| `GET /repos/{owner}/{repo}/issues` | **403** | 403 |
| `POST /graphql` | **403** pinned-set | 403 |
| `GET /user/repos` | **403** sessions are bound to… | 403 |
| `gh issue list` / `gh repo view` | **403** GraphQL pinned-set | 403 |
| `git ls-remote` / `git push` | 成功 | 成功 |

#### 結論 — プロキシには独立した 2 層がある

| 層 | 制御主体 | 今回の状態 |
| --- | --- | --- |
| 一般の外向き通信ポリシー | 環境設定（作成時に選ぶ network policy） | **無制限。設定変更が効いている** |
| GitHub API ゲート | 起動サーフェスの構成 | **不変。ネットワークを開けても動かない** |

3.8 の訂正をさらに一段絞り込む結果である。**repo スコープ 403 は GitHub App の問題でもなく、ネットワークポリシーの問題でもない。** エラー文の「An org admin must connect the Claude GitHub App」は、この構成では引き続き実態を表していない（App は接続済みで、3.9 のとおり MCP 経由では現に書き込みが成功している）。

**CCPM 運用上の含意:** 「クラウドで `gh api` REST が使えないなら、環境のネットワーク設定を緩めればよい」という回避策は**成立しない**。3.8 の推奨（チームが実際に使うサーフェスで 1 回実測する）は変わらず有効で、その実測項目に「ネットワークポリシーは判断材料にならない」を追記する。3.9 で残った未検証の 1 点も、依然としてこのサーフェスでは確定できない。

---

## 4. CCPM 導入後の推奨アーキテクチャ

```
[ローカル]  PRD ブレスト ─→ Epic 分解 ─→ epic-sync
                                            │  (gh / GraphQL 依存のためローカル)
                                            ▼
                                   GitHub Issues (source of truth)
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
[クラウド] session #101              session #102              session #103
         (1 task = 1 VM)           (1 task = 1 VM)           (1 task = 1 VM)
              └──────────────── PR ────────┴─────────────────────────────┘
                                            │
[クラウド]                            Auto-fix で CI 追従
                                            │
[ローカル]                  統合・重いテスト・teleport で引き取り
```

### CCPM フェーズ別のルーティング

| CCPM フェーズ | 実行場所 | 理由 |
| --- | --- | --- |
| PRD ブレスト | **ローカル** | 対話そのものが成果物。plan mode 向き |
| Epic 作成・タスク分解 | **ローカル** | 設計判断を含む。曖昧さをここで潰すのが全体の要 |
| `epic-sync`（Issue 同期） | **ローカル** | `gh` + GraphQL 依存（3.1 / 3.2） |
| タスク実行 | **クラウド** | 1 タスク 1 セッション。VM ごと隔離、並列、閉じても走る |
| 進捗トラッキング（standup 等） | どちらでも | 状態は Issues にあるので実行場所を問わない。bash スクリプトなので安い |
| CI 追従 | **クラウド** | Auto-fix |
| 統合・重いテスト・デバッグ | **ローカル**（または self-hosted） | リソースと到達範囲 |

---

## 5. Phase ロードマップの改訂

前回の 4 フェーズに、CCPM 固有の作業を差し込む。

**Phase 1（改訂） — リポジトリをエージェント可読にする + CCPM を載せる**

前回の項目に加えて:
- CCPM skill を `.claude/skills/ccpm/` に**実ファイルとして** vendoring する（3.4）
- Cloud environment の setup script に `gh` の導入を追加する（3.2）
- **チームが実際に使うサーフェスで `gh api repos/{owner}/{repo}` が通るかを 1 回測る**（3.8）。App の接続確認では不十分で、起動サーフェスによって結果が変わる。通らなければ CCPM の bash スクリプト層が丸ごと使えない
- **同期処理の先頭に preflight チェックを入れ、通らなければ何も書き込まずに中断する**（3.8）。中途半端な同期は Issue とタスクファイルの整合を壊す
- CCPM のスクリプトを監査し、`GITHUB_TOKEN` 直読みと GraphQL 依存箇所を洗い出す（3.1 / 3.2）
- **`gh` の高レベルサブコマンド（`gh issue list` / `gh issue view` / `gh repo view` 等）を `gh api` の REST 形式に書き換える**（3.7）。`gh sub-issue` だけの問題ではない
- `docs/examples/ccpm-subissue-rest.sh` を雛形に、sub-issue 操作を REST 実装に差し替える
- モデル駆動の GitHub 操作は組み込み MCP ツールを使う方針を `CLAUDE.md` に明記する（3.6）
- 「1 Issue = 1 クラウドセッション」を起動する定型プロンプトを `.claude/commands/` に用意する（3.3）
- **CCPM に乗せる閾値を決める。** 並列可能タスクが 3 本以上ある epic のみ CCPM を通す、など。小さな修正に PRD は過剰

**Phase 2（改訂） — 小さい epic を 1 本、通しで回す**

いきなり 12 並列にせず、並列 2〜3 タスクの epic で PRD → sync → クラウド並列実行 → PR → 統合まで通す。測るのは速度ではなく、**どのフェーズがどちら側で詰まったか**。

**Phase 3 — チーム運用に組み込む**

Auto-fix の標準化に加えて、Issue イベント → GitHub Actions → routine の `/fire` という起動経路を組む（3.5）。

**Phase 4 — 12 並列が本当に必要になったら self-hosted 環境を検討する**

CCPM 本来の並列度を 1 マシンで出したいなら、Anthropic ホスト VM ではなく self-hosted 環境かローカルの大きいマシンになる。

---

## 6. CCPM 導入で新たに増えるリスク

| リスク | 内容と対策 |
| --- | --- |
| 儀式のコスト | 小さなタスクに PRD と Epic は過剰。閾値ルールを明文化しないと、チームが CCPM を迂回し始めて仕様と実装が乖離する |
| Issue の平坦化 | 3.1 の fallback 運用だと sub-issue が張れず、Epic の階層が Issue 一覧上で見えなくなる。ラベル運用で補う |
| Phase 1 未完のまま導入 | 仕様は立派だが環境が組めず失敗する、という最悪の組み合わせになる。CCPM は Phase 1 の**代替ではなく上乗せ** |
| `.claude/` の名前空間衝突 | CCPM が `.claude/prds/`、`.claude/epics/`、独自の skills / commands を占有する。既存の命名と衝突しないか事前確認 |
| 仕様の陳腐化 | 「全行が仕様に遡れる」は運用が伴って初めて成立する。実装で判断が変わったら PRD/タスクファイルに戻して更新する規律が要る |
| ベンダー依存の錯覚 | CCPM は harness 非依存だが、**Cloud environment の setup script とネットワーク設定は Anthropic 側に残る**。ここだけは移植できない |

---

## 7. Jules 併用判断の更新

前回の結論は「主軸を Claude Code に置いたうえでの限定併用は成立するが、既定では不要」だった。**CCPM 導入後は不要度がさらに上がる。**

理由: Jules を検討する動機は「タスク単位の自律委譲」「大量並列」「トレーサビリティ」だが、CCPM はそれらを**ベンダー非依存な形でリポジトリ内に再現する**。しかも Jules 型では得られない性質（仕様がレビュー可能、ローカルでも同じ仕様で動く、他 harness に移植可能）が付いてくる。

残る Jules の固有価値は「別のレート制限枠」と「Gemini 系モデルの別意見」程度で、これは CCPM のタスク定義があれば**どの実行系にも同じ仕様を渡せる**ので、必要になった時点で選べばよい。先に囲い込む理由がない。

---

## 8. 結論（更新）

- **ローカルが必要な理由は変わらない。** 物理制約（リソース・到達範囲・シークレット・SSO）は CCPM では解けない。
- **ただし CCPM は、前回提案した「ルーティング設計」を実装する最良の手段である。** ローカルとクラウドの往復を、口頭の運用ルールではなく**仕様ファイルと Issue 状態**として表現できる。
- **on the Web で使うなら、3.1〜3.5 の 5 点を Phase 1 で先に潰すこと。**
- **GitHub 到達の詰まりは `gh` そのものではなく「VM 内から直接叩く経路」だった（3.6・実測）。** 迂回路は 2 つあり、`gh api` の REST（スクリプト用）と組み込み MCP ツール（モデル用）を、**呼び出し主体で使い分ける**のが正解。CCPM の「決定的処理は bash」という設計を保てるのは前者だけである。
- **最重要の読み替えは 3.3。** CCPM の並列モデルを「worktree 並列」ではなく「1 タスク = 1 クラウドセッション、協調は GitHub Issues」として解釈する。これは CCPM の設計思想から外れておらず、むしろクラウドでは VM 隔離のほうが worktree より強い分離を与える。

CCPM 導入後の役割分担は、前回の結論をより鮮明にする。**ローカルは「仕様を決める場所」、クラウドは「仕様を実行する場所」、GitHub Issues は「両者をつなぐ唯一の真実」。**

---

## 参考

- [automazeio/ccpm](https://github.com/automazeio/ccpm) — CCPM 本体（Agent Skill）
- [ccpm/COMMANDS.md](https://github.com/automazeio/ccpm/blob/main/COMMANDS.md)
- [yahsan2/gh-sub-issue](https://github.com/yahsan2/gh-sub-issue) — GraphQL `addSubIssue` を使う `gh` 拡張
- [petersontylerd/ccpm-codex](https://github.com/petersontylerd/ccpm-codex) — 他 harness への移植例
- [How we fixed the context problem in AI-driven development](https://aroussi.com/post/ccpm-claude-code-project-management) — CCPM の設計背景
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) — GitHub プロキシ、setup script、リソース上限
- [Automate work with routines](https://code.claude.com/docs/en/routines) — GitHub トリガの対応イベント、API トリガ
- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)

**実測環境:** Claude Code on the Web セッション（Ubuntu 24.04 / x86_64 / 4 vCPU / 15 GB RAM / 30 GB 空き）, 2026-08-08
