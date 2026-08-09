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
- CCPM のスクリプトを監査し、`GITHUB_TOKEN` 直読みと GraphQL 依存箇所を洗い出す（3.1 / 3.2）
- **`gh sub-issue` 依存を `gh api` の REST 呼び出しに差し替える**（3.6）。検証用リポジトリで書き込みまで通ることを確認してから本番へ
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
