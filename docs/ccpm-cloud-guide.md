# CCPM を Claude Code のクラウドセッションで動かす — 実務ガイド

**2026-08-09 時点 / 対象: [automazeio/ccpm](https://github.com/automazeio/ccpm)**

## 本ガイドの限界（先に読んでください）

**本調査では CCPM 自体を一度も起動していません。** インストールもしておらず、`/pm:init` も `epic-sync` も実行していません。確認したのは「環境が何を許し、何を拒むか」であって、「CCPM が通しで動くこと」ではありません。

**CCPM をクラウドの Claude Code で動かしたという報告は、調べた範囲では世の中にも存在しません。** 本ガイドは実測した環境の制約から**演繹した配置案**であり、動作実績の報告ではありません。

そのため、記述には 2 種類のマーカーを付けます。

- **【実証済み】** — 本調査で実際に動かして成功を確認した
- **【未実証】** — 動くはずだが、成功を観測していない

情報の出所を示す根拠バッジ（［実測］［公式］［外部］）とは別軸です。「実測で 403 を確認した」は情報としては確かでも、**推奨が動く証拠にはならない**ためです。

---

## 1. 推奨する配置 — CCPM を書き換えない

**結論から言うと、CCPM を書き換える必要はありません。書き換えずに、実行場所を分けることで解けます。**

```
[ローカル]   init / PRD / Epic 分解 / epic-sync
                        │   gh が無改修で動く（上流が想定する環境）
                        ▼
              GitHub Issues（source of truth）
                        │
[クラウド]    タスク実行
              Issue の読み書きは MCP ツール【実証済み】
              bash から GitHub API を叩かない
                        │
                       PR
                        │
[ローカル / GitHub UI]   マージ・ブランチ整理
```

### なぜこれで足りるのか

CCPM が GitHub に**書き込む**のは `init`（ラベル作成）、`epic-sync`（Issue 作成）、`epic-merge`（Issue クローズ）の 3 か所です。**いずれもローカルで実行できます。** ローカルなら `gh` は無改修で動きます。

クラウドセッションが必要なのは**タスク実行**だけで、そこで要る GitHub 操作は「Issue を読む」「進捗コメントを書く」の 2 つです。**どちらも組み込みの GitHub MCP ツールで通ります【実証済み】。**

タスク仕様（`.claude/epics/<feature>/<N>.md`）はリポジトリにコミットされているので、クラウドセッションは**ただのファイルとして読めます**。GitHub API を介する必要がありません。

### この構成で CCPM から外れる点

正直に書きます。**CCPM のスクリプトは 1 行も変えませんが、クラウド側では `issue-sync` コマンドを使いません。** 進捗コメントはエージェントが MCP ツールで直接投稿します。

これは CCPM の設計思想から大きく外れるものではありません。CCPM が「決定的処理は LLM を通さず bash で」と定めたのは、**10 件の Issue を一括同期するようなループ**を念頭に置いたものです。1 タスクにつき数回のコメント投稿は性質が違い、モデル駆動でも決定性の問題は起きません。

### 前提の確認

**ローカル側で CCPM が動くこと自体は、本調査では未検証です【未実証】。** 上流が想定する環境なので動くはずですが、CCPM 本体には未修正のバグが 2 件あり（§10 参照）、ドキュメント通りには通らない可能性があります。**まずローカルで 1 本通してから**クラウドに広げてください。

---

## 2. 環境の前提

クラウドセッションの実行環境［公式・実測］。

| 項目 | 値 |
| --- | --- |
| OS / アーキテクチャ | Ubuntu 24.04 / x86_64 |
| CPU / メモリ / ディスク | 4 vCPU / 16 GB / 30 GB |
| `git` | プリインストール済み。正常に動作する |
| `gh` CLI | プリインストールされていない |
| `GH_TOKEN` / `GITHUB_TOKEN` | 値は `proxy-injected` というプレースホルダ |

**§1 の構成では、クラウド側に `gh` は要りません。** GitHub 操作は MCP、コード操作は `git` で足ります。`gh` の導入は付録 A に回しました。

---

## 3. プロキシの構造 — 4 つのゲート

クラウドセッションの GitHub 通信は、独立した 4 つの関門を通ります。**どこで止まっているかを取り違えると、効かない対策に時間を使います。**

| # | ゲート | 制御する主体 | 挙動 |
| --- | --- | --- | --- |
| ① | 一般の外向き通信 | 環境の network access 設定 | Trusted / Custom / Full。**GitHub 経路には効かない** |
| ② | GraphQL | プロキシ固定 | 特定の操作以外はすべて 403。**自前トークンでも回避できない** |
| ③ | API パス単位の書き込み許可 | プロキシ固定 | `git/refs` への書き込みは拒否 |
| ④ | repo スコープ | セッションの起動サーフェス | 添付済みリポジトリのみ。構成によっては添付済みでも 403 |

**ゲート②が最も重要です。** 公式は「PR ワークフロー用の pinned set のみを提供する」と説明していますが、**この pinned set に `gh` 自身のクエリは含まれません**［実測］。

```
gh issue list    → 403  (IssueList)
gh issue view    → 403
gh issue create  → 403  (RepositoryInfo preamble)
gh issue close   → 403
gh repo view     → 403
gh pr list       → 403  (PullRequestList)
```

`gh pr list` すら名指しで拒否されます。**実務上は「`gh` の高レベルサブコマンドは全滅」と考えてください。**

そして公式は、この制限が「供給した資格情報にかかわらず適用される」と明記しています［公式］。**つまりゲート②はサーフェスに依存しない可能性が高く、どのクラウド環境でも `gh` の高レベルサブコマンドは使えないと考えるのが安全です。** これが §1 で「クラウドでは `gh` を使わない」構成にした理由です。

**ゲート④だけがサーフェスによって変わります。** ただし本調査では 200 を返す環境を一度も観測していません（付録 A）。

---

## 4. 何ができて、何ができないか

### 4.1 git プロトコル — ほぼ制約なし

| 操作 | 可否 |
| --- | --- |
| clone / fetch / push | **可**【実証済み】 |
| 任意の名前のブランチへ push | **可**【実証済み】（`claude/` プレフィックスは不要） |
| 1 セッションから複数ブランチへ push | **可**【実証済み】（worktree の中からでも） |
| `.github/workflows/` を含む push | **可**【実証済み】 |
| 保護されていない main への push | **可**【実証済み】（force-push も通る） |
| 保護ブランチへの push | **不可**［公式］ |
| 他者の PR があるブランチ / 他者のコミットを含むブランチ | **不可**［公式］ |
| **ブランチの削除** | **不可**【実証済み】 |

### 4.2 GitHub API

| 経路 | 可否 |
| --- | --- |
| 組み込み GitHub MCP ツール | **可**【実証済み】 — Issue の読み書き、sub-issue、PR。**モデルからしか呼べない** |
| `gh api user` / `rate_limit` | **可**【実証済み】 |
| `gh` の高レベルサブコマンド | **不可**【実証済み】 |
| `gh api graphql` | **不可**［公式・実測］ |
| 横断列挙（`user/repos` 等） | **不可**【実証済み】 |
| `gh api repos/{owner}/{repo}/...` | **本調査の環境では 403**。付録 A 参照 |

### 4.3 ブランチ削除だけは 3 経路すべてで塞がれている【実証済み】

| 経路 | 返る理由 |
| --- | --- |
| `git push origin --delete` | 403（説明文なし、sideband 切断） |
| `gh api --method DELETE .../git/refs/heads/x` | `Write access to this GitHub API path is not permitted through this proxy.` |
| GitHub MCP | ブランチ／ref 削除ツールが存在しない |

**塞がれているのは「ref の削除」であって、破壊的な操作全般ではありません。** 履歴を書き換える force-push は通ります。

**回避策:** リポジトリ設定の **「Automatically delete head branches」を有効にする**のが最も運用に馴染みます。PR マージ時に自動で消えます。ほかに GitHub UI の Branches 画面、ローカルの clone。

---

## 5. CCPM の各部品をどこで動かすか

| 構成要素 | 実行場所 | 理由 |
| --- | --- | --- |
| `init.sh`（初期化） | **ローカル** | `gh repo view`（GraphQL）、`gh label create`、`gh auth login`（対話的）に依存する。クラウドでは動かない |
| 報告系スクリプト<br>`status.sh` `standup.sh` `search.sh` ほか | **どちらでも** | ソースを確認したところ純粋にローカルのファイル操作のみで、GitHub API に一切触れない。`find` / `grep` / `wc` / `sed` だけで構成されている |
| `epic-sync`（Issue 同期） | **ローカル** | `gh issue create` / `gh issue comment` が GraphQL で落ちる |
| `gh-sub-issue`（親子 Issue） | **ローカル** | `addSubIssue` mutation を使う。**無改修でもタスクリストへ fallback するので停止はしない**（階層表現が失われるだけ） |
| タスク実行（worktree 並列） | **クラウド** | git 面に制約なし【実証済み】。ただし §7 参照 |
| 進捗コメント | **クラウド（MCP）** | CCPM の `issue-sync` は使わず、エージェントが直接投稿する【実証済み】 |
| `epic-merge` | **ローカル** | 内部の `gh issue close` が GraphQL で落ちる。main への push 自体はクラウドでも通る |
| ブランチ整理 | **クラウド外** | 技術的に選択の余地がない |
| skill の配布 | — | 公式手順は絶対パスの symlink で、参照先がクラウド VM に存在しない |

**skill の配布方法は 2 通りあります**［公式］。

1. `skill/ccpm/` の実体をリポジトリの `.claude/skills/ccpm/` に**実ファイルとしてコミットする**。クラウドセッションはクローンされたリポジトリの `.claude/skills/` を読み込む
2. リポジトリの `.claude/settings.json` に**プラグインとして宣言する**。セッション開始時に自動インストールされる

---

## 6. クラウド側から Issue を扱う

§1 の構成でクラウドセッションが行う GitHub 操作は 2 つだけです。**どちらも MCP ツールで実証済みです。**

### 読む

タスク仕様はリポジトリのファイルとして読めるので、GitHub API は原則不要です。Issue 本体やコメントを見たい場合は MCP ツールを使います。

```
issue_read(get_issue, #N)         → Issue 本体
issue_read(get_comments, #N)      → コメント履歴
issue_read(get_sub_issues, #N)    → 子 Issue 一覧
issue_read(get_parent, #N)        → 親 Issue
```

### 書く

進捗コメントは `add_issue_comment`、完了時のクローズは `issue_write` で行います。

### sub-issue の契約【実証済み】

親子関係を張る操作も MCP で通ります。検証用 Issue 2 本で、`sub_issue_write(add)` → `get_sub_issues` / `get_parent` の**双方向が成立すること**を確認済みです。実行主体は `performed_via_github_app: anthropics/claude` でした。

**押さえるべき契約:** この API は issue **number** ではなく内部 **id** を要求します。

```json
{"id":"5100355274","url":"https://github.com/OWNER/REPO/issues/2"}
```

**ただし Issue を自分で作る側は、追加の lookup が要りません。** 作成レスポンスが `id` を返すため、その場で捕まえておけば **1 タスクあたり 1 往復節約できます。** これはローカルの `epic-sync` を書き換える際にも同じく効きます。

---

## 7. 自動化・並列度

### Routines で Issue イベントは拾えない

**GitHub トリガで反応できるイベントは Pull request と Release だけです**［公式］。`issues.labeled` は存在しないため、**「Issue にラベルが付いたら自動着手」は webhook では組めません。**

代替は API トリガです。routine ごとの `/fire` エンドポイントに GitHub Actions から POST します。

**注意:** 渡した `text` は `<routine-fire-payload>` で untrusted としてラップされます。**routine の prompt 側で「payload を参照して動け」と明示しない限り、不活性なコンテキストとして無視されます**［公式］。

**上限が 2 種類あります**［公式］。webhook イベントには per-routine / per-account の時間あたり上限、routine 実行にはアカウント日次上限。**タスク数だけセッションを起動する設計は、この上限に当たります。**

### 並列度をどう決めるか

CCPM の README が挙げる実例は **1 つの Issue を 5 エージェントで分担する**形です。物理リソース（4 vCPU / 16 GB）で先に詰まることは、同時ビルドを避ける限りあまりありません。**実際の律速は 2 つです。**

- **レート制限** — クラウドセッションはアカウントの他の利用と枠を共有し、並列実行は比例して消費する［公式］
- **コンテキストの混線** — 1 セッションで複数タスクを扱うと破綻するという報告が複数ある［外部］

**なお CCPM の並列モデルは「タスクごとに別ブランチ」ではありません。** 1 つの `epic/<name>` ブランチに複数エージェントが同時にコミットし、各自 `git pull --rebase` で同期する設計です。git の面でプロキシ由来の制約はありませんが、**この競合とリベースの安定性は未検証です【未実証】。**

---

## 8. 導入手順

### Phase 1 — ローカルで 1 本通す

**クラウドの話をする前に、ローカルで CCPM が動くことを確認してください。** 本調査ではここも未検証です。

- [ ] CCPM をローカルに導入し、`/pm:init` を通す
- [ ] 小さな PRD → Epic → `epic-sync` まで実行し、Issue が期待どおり作られるか確認する
- [ ] **既知のバグ 2 件に当たらないか確認する**（§10）。当たるなら先にパッチを当てる

### Phase 2 — リポジトリをクラウド向けに整える

- [ ] CCPM skill を `.claude/skills/ccpm/` に実ファイルでコミットする、または `.claude/settings.json` にプラグイン宣言する
- [ ] ブランチ整理の逃がし先を決める（「Automatically delete head branches」を有効にするのが簡単）
- [ ] main を保護しているなら、`epic-merge` を PR 作成までに留める設計にする
- [ ] **CCPM に乗せる閾値を決める。** 並列可能タスクが 3 本以上ある epic のみ通す、など。小さな修正に PRD は過剰

### Phase 3 — クラウドでタスクを 1 本実行する

- [ ] `epic-sync` はローカルで実行し、Issue を作る
- [ ] クラウドセッションを 1 本起動し、`.claude/epics/<feature>/<N>.md` に従って作業させる
- [ ] 進捗コメントが MCP で投稿できることを確認する
- [ ] PR まで到達させる
- [ ] **測るのは速度ではなく、どのフェーズがどちら側で詰まったか**

### Phase 4 — 並列に広げる

- [ ] 並列 2〜3 タスクで epic を 1 本通す
- [ ] 同一 `epic/<name>` ブランチへの並行コミットが破綻しないか観察する【未実証の領域】
- [ ] レート制限の消費を計測する

---

## 9. リスク

| リスク | 内容と対策 |
| --- | --- |
| **ローカル環境が必須になる** | §1 の構成は同期をローカルに置く。全員がブラウザだけで完結する運用にはできない。無人運用を目指すなら付録 A の検討が要る |
| **ブランチの堆積** | クラウドから削除できない。自動削除設定か定期的な棚卸しを用意する |
| **レート制限** | 並列実行はアカウント枠を比例消費する。使用量の可視化を運用に組み込む |
| **中途半端な同期** | `epic-sync` が途中で失敗すると Issue とタスクファイルの整合が壊れる。ローカル実行なら失敗しにくいが、失敗時の復旧手順は決めておく |
| **儀式のコスト** | 小さなタスクに PRD と Epic は過剰。閾値を明文化しないとチームが CCPM を迂回し、仕様と実装が乖離する |
| **`.claude/` の名前空間衝突** | CCPM が `.claude/prds/`、`.claude/epics/` と独自の skills / commands を占有する。既存の命名と衝突しないか事前確認 |
| **仕様の陳腐化** | 「全行が仕様に遡れる」は運用が伴って初めて成立する |
| **CCPM 本体の既知バグ** | `sync.md` が存在しないフラグ `gh issue create --json` を使っている（[#1024](https://github.com/automazeio/ccpm/issues/1024)）、`gh sub-issue` の構文が誤っている（[#1022](https://github.com/automazeio/ccpm/issues/1022)）。**クラウド以前に、ローカルでもドキュメント通りには通らない** |
| **そもそもの費用対効果** | CCPM がクラウドで固有に足す価値は薄い可能性がある。仕様のトレーサビリティは「計画を `docs/` にコミットして `--cloud` で渡す」でも大半が得られ、並列実行はクラウドセッションが元から提供する。**導入前に、この単純な代替で足りないか一度検討すること** |

---

## 10. 未確定の事項

判断に使う前に、自分で測るべきもの。

| # | 問い | 確かめ方 |
| --- | --- | --- |
| 1 | **ローカルで CCPM が通しで動くか** | Phase 1。本調査では未検証 |
| 2 | §1 の構成が通しで機能するか | Phase 3。本調査では未検証 |
| 3 | 1 つの epic ブランチに複数エージェントが同時コミットする形は安定するか | Phase 4 |
| 4 | `gh api repos/{owner}/{repo}` が 200 を返す環境は実在するか | 付録 A |
| 5 | 保護ブランチでの挙動 | 保護を有効にした検証用リポジトリで push |

---

## 11. まとめ

**CCPM を書き換えるのではなく、実行場所を分けて解きます。**

| 区分 | 該当するもの |
| --- | --- |
| **クラウドで動く**【実証済み】 | git 操作全般、MCP による Issue の読み書きと sub-issue、報告系スクリプト |
| **ローカルに置く** | `init`、`epic-sync`、`gh-sub-issue`、`epic-merge` の Issue クローズ |
| **クラウドでは不可能**【実証済み】 | ブランチの削除 |
| **未検証** | CCPM がローカルで通しで動くこと、本構成が通しで機能すること |

この配置なら CCPM のスクリプトは 1 行も変えません。クラウド側で `gh` すら要りません。**代償はローカル環境が必須になることで、完全な無人運用はできません。** それが要件なら付録 A を検討してください。

---

## 付録 A. できたらよいこと — クラウドから GitHub API を叩く

**ここに書くことは、本調査で一度も成功していません。**

`gh api repos/{owner}/{repo}` が **200 を返す環境を、全セッションを通じて一度も観測していません。** 根拠はプロキシのエラーメッセージが `gh api repos/{owner}/{repo}/...` を代替として案内していること、および公式ドキュメントの「repo スコープ: 添付されたリポジトリにのみ届く」という記述からの**推論のみ**です。

それでも、これが成立すれば得られるものは大きいので記録します。

### A.1 何が嬉しいのか

- `epic-sync` をクラウドで実行できる → **ローカル環境なしで運用が閉じる**
- Routines による無人運用が可能になる
- ローカルとクラウドで同一のスクリプトが動く

### A.2 まず測る

```bash
gh api repos/{owner}/{repo}
```

**200 が返る環境が見つかったら、そこが出発点です。** 403 なら、この付録の内容はすべて不可能です。

このテストは以下では代替できません。いずれも 200 と 403 を区別せず、それぞれに反例があります。

- **GitHub App の接続状態** — 接続済みでも 403 になる。公式も「access control ではない」と明言
- **リポジトリの添付** — 添付済みでも 403
- **`git` が動くか** — git は別系統。動いていても API は 403
- **ネットワーク設定** — 独立した別プロキシ。全開放しても不変
- **他セッションでの実績** — 起動元が違えば結果が変わる

### A.3 200 が得られた場合にやること【未実証】

CCPM の GitHub 層を `gh api` の REST に書き換えます。**これは上流へのフォークになり、恒久的な保守コストが発生します。** CCPM には GitHub アクセスの抽象層がないため、改変は侵襲的になります。

- `init.sh` — `gh repo view` を `git remote` からの導出に、`gh label create` を `gh api --method POST repos/{o}/{r}/labels` に、`gh auth login` を削除
- `epic-sync` — `gh issue create` / `gh issue comment` を `gh api` の REST に
- `gh sub-issue` — REST の `POST /repos/{o}/{r}/issues/{n}/sub_issues` に
- `epic-merge` — `gh issue close` を REST に
- **同期処理の先頭に preflight チェックを入れ、通らなければ何も書き込まずに中断する**

sub-issue の REST 実装は [`docs/examples/ccpm-subissue-rest.sh`](./examples/ccpm-subissue-rest.sh) にあります。**このスクリプトは `check` が 403 で落ちる環境でしか試せておらず、`experiment` は実行できていません。** 200 が返る環境が手に入ったら、まずこれを通してください。

```bash
./docs/examples/ccpm-subissue-rest.sh check        # どの層で詰まっているかを切り分ける
./docs/examples/ccpm-subissue-rest.sh experiment   # 親子 Issue を作って検証
```

### A.4 ただし、これでも `gh` の高レベルサブコマンドは戻りません

重要な限界です。ゲート②（GraphQL）は**資格情報にかかわらず適用される**と公式が明記しており、repo スコープとは別の層です。**200 が得られても `gh issue create` は動きません。** 使えるのは `gh api` + REST パスだけで、書き換えは避けられません。

### A.5 クラウドに `gh` を導入する

A.3 に進む場合のみ必要です。setup script に入れると、結果がスナップショットとしてキャッシュされます。

```bash
apt-get update && apt-get install -y gh
```

Ubuntu リポジトリの版は **2.45.0** と古いことに注意してください【実証済み】。新しい版が要るなら GitHub 公式リポジトリから取得することになり、`release-assets.githubusercontent.com` への到達が必要なので network access を Custom か Full にします。

**スクリプトが `GITHUB_TOKEN` を直読みしていないか確認してください。** 直読みするとプレースホルダ文字列 `proxy-injected` を掴んで失敗します。`gh` 経由なら問題ありません［公式］。

---

## 参考

- [automazeio/ccpm](https://github.com/automazeio/ccpm) — CCPM 本体
- [yahsan2/gh-sub-issue](https://github.com/yahsan2/gh-sub-issue)
- [REST API endpoints for sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) — GitHub プロキシ、setup script、リソース上限、許可ドメイン
- [Use Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) — GitHub 認証、App の位置づけ
- [Automate work with routines](https://code.claude.com/docs/en/routines) — トリガ、ブランチ push ルール、実行上限
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — skill の探索とクラウドでの読み込み

**関連文書:** 検証の経緯・出典の突き合わせ・訂正の記録は [`ccpm-addendum.md`](./ccpm-addendum.md) と [`ccpm-evidence-review.md`](./ccpm-evidence-review.md) にあります。

**実測環境:** Claude Code cloud セッション（Ubuntu 24.04 / x86_64 / 4 vCPU / 15 GB RAM / 30 GB 空き）。GitHub 到達は MCP サーバ経由に一本化された構成。
