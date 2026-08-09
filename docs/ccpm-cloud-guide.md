# CCPM を Claude Code のクラウドセッションで動かす — 実務ガイド

**2026-08-09 時点 / 対象: [automazeio/ccpm](https://github.com/automazeio/ccpm)**

この文書は「CCPM をクラウドの Claude Code で使いたい人が、何を直せば動くのか」だけを書いたものである。調査の経緯は載せない。各項目には根拠の種別を付す。

- **［実測］** — 実際のクラウドセッションで確認した
- **［公式］** — Anthropic または GitHub のドキュメントに明記がある
- **［外部］** — 第三者の報告や未解決 Issue が根拠
- **［未検証］** — 確認できていない。判断に使うなら自分で測ること

---

## 1. 最初にやること — 1 分の到達性テスト

**これを最初にやらないと、以降の作業量が見積もれない。**

```bash
gh api repos/{owner}/{repo}
```

| 結果 | 意味 | 以降の方針 |
| --- | --- | --- |
| **200** | VM から GitHub API に直接届く | CCPM の bash スクリプト層を `gh api` REST に書き換えれば、ローカルと同一コードで動く |
| **403** | 直接経路が無効なサーフェス | bash からは GitHub に触れない。同期処理はローカル固定か、モデル駆動（MCP）に倒すしかない |

**重要な注意が 3 つある。**

1. **GitHub App を org に接続しても変わらない。** 403 のエラー文は「An org admin must connect the Claude GitHub App」と言うが、これは実態を表していない。公式ドキュメントは「App のインストールは Auto-fix の webhook を有効にするだけで、**セッションレベルのアクセス制御ではない**」と明言している［公式］。App 接続済み・リポジトリ添付済みでも 403 になる構成が実在する［実測］。

2. **環境のネットワーク設定を緩めても変わらない。** GitHub 通信は network access 設定とは独立した別プロキシを通る［公式］。実際、egress を無制限にしても結果は 1 項目も変わらなかった［実測］。そもそも Trusted のデフォルト許可ドメインに `api.github.com` は最初から入っている。

3. **同じアカウント・同じリポジトリでも、セッションの起動元が違えば結果が変わる。** チームが使うサーフェスを固定し、そこで測ること。

---

## 2. 環境の前提

クラウドセッションの実行環境［公式・実測］。

| 項目 | 値 |
| --- | --- |
| OS / アーキテクチャ | Ubuntu 24.04 / x86_64 |
| CPU / メモリ / ディスク | 4 vCPU / 16 GB / 30 GB |
| `git` | プリインストール済み。正常に動作する |
| `gh` CLI | **プリインストールされていない** |
| `GH_TOKEN` / `GITHUB_TOKEN` | 値は `proxy-injected` というプレースホルダ。プロキシが送信時に実トークンへ差し替える |

**`gh` の導入方法。** Cloud environment の setup script に入れる。結果はファイルシステムのスナップショットとしてキャッシュされ、毎セッション走るわけではない。

```bash
apt-get update && apt-get install -y gh
```

ただし Ubuntu リポジトリの版は **2.45.0** と古い［実測］。新しい版が要るなら GitHub 公式リポジトリから取得することになり、その場合は `release-assets.githubusercontent.com` への到達が必要になるため、環境の network access を Custom か Full にする。

**スクリプトが `GITHUB_TOKEN` を直読みしていないか確認すること。** 直読みするとプレースホルダ文字列を掴んで失敗する。`gh` 経由なら問題ない［公式］。

---

## 3. プロキシの構造 — 4 つのゲート

クラウドセッションの GitHub 通信は、独立した 4 つの関門を通る。**どこで止まっているかを取り違えると、効かない対策に時間を使うことになる。**

| # | ゲート | 制御する主体 | 挙動 |
| --- | --- | --- | --- |
| ① | 一般の外向き通信 | 環境の network access 設定 | Trusted / Custom / Full。**GitHub 経路には効かない** |
| ② | GraphQL | プロキシ固定 | 特定の操作以外はすべて 403。**自前トークンでも回避できない** |
| ③ | API パス単位の書き込み許可 | プロキシ固定 | `git/refs` への書き込みは拒否。**repo スコープ判定より前に走る** |
| ④ | repo スコープ | セッションの起動サーフェス | 添付済みリポジトリのみ。構成によっては添付済みでも 403 |

**ゲート②について補足する。** 公式ドキュメントは「PR ワークフロー用の pinned set のみを提供する」と説明しているが、**この pinned set に `gh` 自身のクエリは含まれない**［実測］。`gh pr list` ですら `PullRequestList` として名指しで拒否される。実務上は「**`gh` の高レベルサブコマンドは全滅**」と考えてよい。

```
gh issue list    → 403  (IssueList)
gh issue view    → 403
gh issue create  → 403  (RepositoryInfo preamble)
gh issue close   → 403
gh repo view     → 403
gh pr list       → 403  (PullRequestList)
```

**使えるのは `gh api` + REST パスだけである。** プロキシのエラーメッセージ自身がそう案内している。

---

## 4. 何ができて、何ができないか

### 4.1 git プロトコル — ほぼ制約なし

| 操作 | 可否 | 備考 |
| --- | --- | --- |
| clone / fetch / push | **可**［実測］ | |
| 任意の名前のブランチへ push | **可**［実測］ | `claude/` プレフィックスは不要 |
| 1 セッションから複数ブランチへ push | **可**［実測］ | worktree の中からでも可 |
| `.github/workflows/` を含む push | **可**［実測］ | |
| 保護されていない main への push | **可**［実測］ | force-push（履歴の書き換え）も通る |
| **保護ブランチへの push** | **不可**［公式］ | 実運用で main を保護しているなら epic-merge の直接 push は通らない |
| 他者の PR があるブランチへの push | **不可**［公式］ | |
| 他者のコミットを含むブランチへの push | **不可**［公式］ | |
| **ブランチの削除** | **不可**［実測］ | 下記 4.3 |

### 4.2 GitHub API

| 経路 | 可否 | 備考 |
| --- | --- | --- |
| `gh api user` / `rate_limit` | **可**［実測］ | ユーザ・グローバルスコープは通る |
| `gh api repos/{owner}/{repo}/...` | **サーフェス次第**［実測］ | §1 のテストで判定する |
| `gh api graphql` | **不可**［公式・実測］ | |
| `gh` の高レベルサブコマンド | **不可**［実測］ | §3 参照 |
| 横断列挙（`user/repos` 等） | **不可**［実測］ | `repos/{owner}/{repo}/...` の形に限る |
| 組み込み GitHub MCP ツール | **可**［実測］ | Issue の読み書き、sub-issue、PR 操作。**ただしモデルからしか呼べない** |

### 4.3 ブランチ削除だけは 3 経路すべてで塞がれている［実測］

| 経路 | 結果 |
| --- | --- |
| `git push origin --delete <branch>` | 403（説明文なし、sideband 切断） |
| `gh api --method DELETE .../git/refs/heads/<branch>` | `Write access to this GitHub API path is not permitted through this proxy.` |
| GitHub MCP | ブランチ／ref 削除ツールが存在しない |

**塞がれているのは「ref の削除」であって、破壊的な操作全般ではない。** 履歴を書き換える force-push は通る。REST 側では `git/refs` への DELETE と PATCH の両方が同じ文言で拒否される。

**回避策:** GitHub UI の Branches 画面、ローカルの clone、または GitHub Actions（ワークフローを push できるため理論上は可能だが**未検証**）。リポジトリ設定の「Automatically delete head branches」を有効にすれば、PR マージ時に自動削除される。

---

## 5. CCPM の各部品はどうなるか

| CCPM の構成要素 | 判定 | 理由と対処 |
| --- | --- | --- |
| **`init.sh`（初期化）** | **要書き換え** | `gh repo view`（GraphQL で落ちる）、`gh label create` / `gh label list`（repo スコープ）、`gh auth login`（対話的でクラウドでは不可能）、`gh extension install` に依存する。**導入の第一歩から動かない** |
| **報告系スクリプト**<br>`status.sh` `standup.sh` `search.sh` `next.sh` `blocked.sh` ほか | **無改修で動く** | ソースを確認したところ純粋にローカルのファイル操作のみで、GitHub API に一切触れない。`find` / `grep` / `wc` / `sed` だけで構成されている |
| **`epic-sync`（Issue 同期）** | **要書き換え** | `gh issue create` / `gh issue comment` が GraphQL で落ちる。`gh api` の REST へ全面的に置き換える必要がある |
| **`gh-sub-issue`（親子 Issue）** | **要書き換え** | GraphQL の `addSubIssue` mutation を使うため不可。REST の `POST /repos/{o}/{r}/issues/{n}/sub_issues` に置換する。無改修の場合、CCPM はタスクリストへ fallback するので**停止はしない**（階層表現が失われるだけ） |
| **worktree による並列実行** | **git 面は制約なし** | 複数ブランチ push も worktree からの push も通る。ただし CCPM の実際の設計は 1 つの `epic/<name>` ブランチに複数エージェントが同時コミットし、各自 `git pull --rebase` で同期する形であり、**その競合とリベースの安定性は未検証**［未検証］ |
| **`epic-merge`** | **一部書き換え** | main へのマージ push 自体は通る（**保護していなければ**）。ただし内部で使う `gh issue close` は GraphQL で落ちるため、そこは REST か MCP に置き換える |
| **epic 完了後のブランチ整理** | **クラウドでは不可** | §4.3 のとおり。外に逃がす |
| **skill の配布** | **手順の変更が必要** | 公式手順は絶対パスの symlink で、参照先がクラウド VM に存在しない |

**skill の配布方法は 2 通りある［公式］。**

1. `skill/ccpm/` の実体をリポジトリの `.claude/skills/ccpm/` に**実ファイルとしてコミットする**。クラウドセッションはクローンされたリポジトリの `.claude/skills/` を読み込む
2. リポジトリの `.claude/settings.json` にプラグインとして宣言する。セッション開始時に自動インストールされるため、`/plugin` コマンドがクラウドで使えなくても機能する

---

## 6. sub-issue を REST で張る

CCPM の階層構造をクラウドで維持したい場合の実装。**GraphQL も `gh` の高レベルサブコマンドも使わない。**

**押さえるべき契約:** URL に入るのは issue **number**、body の `sub_issue_id` に入るのは内部 **id** である。ここを取り違えると 404 になる（よくある間違い）。

```bash
# 既存 Issue を紐づける場合 — id の解決が要る
child_id=$(gh api "repos/$REPO/issues/$child" --jq .id)
gh api --method POST "repos/$REPO/issues/$parent/sub_issues" -F sub_issue_id="$child_id"
```

**ただし `epic-sync` は Issue を自分で作る側なので、id 解決は不要にできる。** 作成レスポンスが `id` を返すため、その場で捕まえておけば **タスク 1 本あたり 1 往復節約できる**。

```bash
read -r num id < <(gh api --method POST "repos/$REPO/issues" \
  -f title="$title" -f body="$body" --jq '"\(.number) \(.id)"')
```

そのまま流せる実装を [`docs/examples/ccpm-subissue-rest.sh`](./examples/ccpm-subissue-rest.sh) に置いてある。`gh repo view` を避けて `git remote` からリポジトリ名を導出しているのも、GraphQL 制約への対応である。

```bash
./docs/examples/ccpm-subissue-rest.sh check        # どの層で詰まっているかを切り分ける
./docs/examples/ccpm-subissue-rest.sh experiment   # 親子 Issue を作って検証
./docs/examples/ccpm-subissue-rest.sh add 12 34    # #34 を #12 の sub-issue にする
```

**MCP 経路でも同じことができる［実測］。** 検証用 Issue で `sub_issue_write(add)` → `get_sub_issues` / `get_parent` の双方向を確認済み。ただし MCP ツールはモデルからしか呼べないため、bash スクリプト層の代替にはならない。10 タスクの一括同期のようなループをモデルに任せると、ターンを消費するうえに非決定的になる。

**REST 経路がプロキシ越しに通るかは、§1 のテスト結果次第である。** REST エンドポイント自体は他所で動作実績がある。

---

## 7. 自動化との組み合わせ

### Routines（スケジュール／イベント起動）

**GitHub トリガで反応できるイベントは Pull request と Release だけ**［公式］。`issues.opened` や `issues.labeled` は存在しないため、**「Issue にラベルが付いたら自動着手」は webhook では組めない。**

代替は API トリガである。routine ごとの `/fire` エンドポイントに POST する形で、Issue イベントを GitHub Actions で受けて中継する。

```bash
curl -X POST https://api.anthropic.com/v1/claude_code/routines/{trigger_id}/fire \
  -H "Authorization: Bearer {token}" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"text": "Issue #123 labeled ready"}'
```

**`text` の扱いに注意。** 渡した内容は `<routine-fire-payload>` というブロックで untrusted としてラップされる。**routine の prompt 側で「payload を参照して動け」と明示しない限り、不活性なコンテキストとして無視される**［公式］。

**上限が 2 種類ある［公式］。** GitHub webhook イベントには per-routine / per-account の時間あたり上限があり、超過分は破棄される。routine の実行自体にもアカウント日次上限がある。**タスク数だけセッションを起動する設計は、この上限に正面から当たる。**

### 並列度をどう決めるか

CCPM の README が挙げる実例は **1 つの Issue を 5 エージェントで分担する**形である。物理リソース（4 vCPU / 16 GB）で先に詰まることは、同時ビルドを避ける限りあまりない。

**実際の律速は 2 つある。**

- **レート制限** — クラウドセッションはアカウントの他の利用と枠を共有し、並列実行は比例して消費する［公式］。Opus で大量に回すと使用量上限に到達するという実践報告がある［外部］
- **コンテキストの混線** — 1 セッションで複数タスクを扱うと破綻するという報告が複数ある［外部］

**大きな並列度が本当に必要になったら、詰まるのは VM のスペックではなくアカウントのレート制限である。** その時点で self-hosted 環境かローカルの大きいマシンを検討することになる。

---

## 8. 導入手順

### Phase 0 — 到達性テスト（1 分）

§1 のとおり。**ここの結果で以降の作業量が変わる。**

### Phase 1 — リポジトリを整える

- [ ] CCPM skill を `.claude/skills/ccpm/` に実ファイルでコミットする、または `.claude/settings.json` にプラグイン宣言する
- [ ] Cloud environment の setup script に `gh` の導入を入れる（版に注意）
- [ ] **`init.sh` を書き換える。** `gh repo view` を `git remote` からの導出に、`gh label create` を `gh api --method POST repos/{o}/{r}/labels` に、`gh auth login` を削除する
- [ ] `epic-sync` の `gh issue create` / `gh issue comment` を `gh api` の REST に置き換える
- [ ] `gh sub-issue` を REST 実装に置き換える（§6）
- [ ] `epic-merge` の `gh issue close` を REST か MCP に置き換える
- [ ] **同期処理の先頭に preflight チェックを入れる。** 通らなければ**何も書き込まずに中断**すること。中途半端な同期は Issue とローカルのタスクファイルの整合を壊す
- [ ] ブランチ整理の逃がし先を決める（GitHub の「Automatically delete head branches」設定、または Actions）
- [ ] main を保護しているなら、`epic-merge` を PR 作成までに留める設計にする
- [ ] `GITHUB_TOKEN` を直読みしている箇所がないか監査する
- [ ] **CCPM に乗せる閾値を決める。** 並列可能タスクが 3 本以上ある epic のみ通す、など。小さな修正に PRD は過剰

### Phase 2 — 小さい epic を 1 本、通しで回す

並列 2〜3 タスクで PRD → sync → 並列実行 → PR → 統合まで通す。**測るのは速度ではなく、どのフェーズがどちら側で詰まったか。**

### Phase 3 — チーム運用に組み込む

Auto-fix の標準化と、Issue イベント → Actions → routine の `/fire` という起動経路。**先に日次・時間あたり上限を確認しておく。**

---

## 9. どこで実行するか

| CCPM フェーズ | 場所 | 理由 |
| --- | --- | --- |
| PRD ブレスト | ローカル | 対話そのものが成果物。plan mode 向き |
| Epic 作成・タスク分解 | ローカル | 設計判断を含む。曖昧さをここで潰すのが全体の要 |
| `epic-sync` | サーフェス次第 | §1 のテストが 200 ならクラウド可。403 ならローカル固定 |
| タスク実行 | **クラウド** | worktree 並列がそのまま使える |
| 進捗トラッキング | どちらでも | 状態は Issues にあり、スクリプトは純ローカル。安い |
| CI 追従 | クラウド | Auto-fix |
| `epic-merge` | クラウド可 | main を保護しているなら PR 作成まで |
| ブランチ整理 | **クラウド外** | 技術的に選択の余地がない |
| 統合・重いテスト | ローカル | リソースと到達範囲 |

---

## 10. 導入前に把握しておくリスク

| リスク | 内容と対策 |
| --- | --- |
| **サーフェス依存** | 同じアカウント・同じリポジトリでも、起動元が違えば `gh api` の可否が変わる。使うサーフェスを固定し、preflight を必須にする |
| **ブランチの堆積** | クラウドから削除できないため、epic を回すほど残る。自動削除設定か定期的な棚卸しを用意する |
| **レート制限** | 並列実行はアカウント枠を比例消費する。使用量の可視化を運用に組み込む |
| **中途半端な同期** | epic-sync が途中で失敗すると Issue とタスクファイルの整合が壊れる。preflight での早期中断が唯一の防御 |
| **儀式のコスト** | 小さなタスクに PRD と Epic は過剰。閾値を明文化しないとチームが CCPM を迂回し、仕様と実装が乖離する |
| **`.claude/` の名前空間衝突** | CCPM が `.claude/prds/`、`.claude/epics/` と独自の skills / commands を占有する。既存の命名と衝突しないか事前確認 |
| **仕様の陳腐化** | 「全行が仕様に遡れる」は運用が伴って初めて成立する。実装で判断が変わったら仕様ファイルに戻して更新する規律が要る |
| **移植できない部分** | CCPM 自体は harness 非依存だが、Cloud environment の setup script とネットワーク設定は Anthropic 側に残る |
| **CCPM 本体の既知バグ** | `sync.md` が存在しないフラグ `gh issue create --json` を使っている（[#1024](https://github.com/automazeio/ccpm/issues/1024)）、`gh sub-issue` の構文が誤っている（[#1022](https://github.com/automazeio/ccpm/issues/1022)）。**クラウド以前に、ローカルでもドキュメント通りには通らない** |

---

## 11. 未確定の事項

判断に使う前に自分で測るべきもの。

| # | 問い | 確かめ方 |
| --- | --- | --- |
| 1 | `POST .../sub_issues` はプロキシ経由の REST でも通るか | §1 が 200 のサーフェスで `ccpm-subissue-rest.sh experiment` |
| 2 | 1 つの epic ブランチに複数エージェントが同時コミットする形は安定するか | 小さい epic を実際に並列で回す |
| 3 | GitHub Actions 経由ならブランチを削除できるか | `workflow_dispatch` のワークフローを置いて叩く |
| 4 | 保護ブランチでの挙動 | 保護を有効にした検証用リポジトリで push |
| 5 | 自前 PAT を `GH_TOKEN` に設定すると repo スコープ 403 を回避できるか | 環境変数に PAT を設定して再テスト。公式記述と外部報告が食い違っている領域 |

---

## 12. まとめ

**CCPM はクラウドで動く。ただし GitHub に触る部分は全面的に書き換えが要る。**

| | 状態 |
| --- | --- |
| そのまま動く | 報告系スクリプト、worktree による並列実行、`epic-merge` の main push |
| 書き換えが要る | `init.sh`、`epic-sync` / `issue-sync`、sub-issue 操作、`epic-merge` の Issue クローズ |
| クラウドでは不可能 | ブランチの削除 |
| 事前に測る必要がある | `gh api repos/{owner}/{repo}` の可否（サーフェス依存） |

書き換えの中身は一貫している。**`gh` の高レベルサブコマンドを `gh api` の REST に置き換える。** これができれば、ローカルとクラウドで同一のコードが動き、CCPM の「決定的な処理は LLM を通さず bash で」という設計思想も保てる。

---

## 参考

- [automazeio/ccpm](https://github.com/automazeio/ccpm) — CCPM 本体
- [yahsan2/gh-sub-issue](https://github.com/yahsan2/gh-sub-issue)
- [REST API endpoints for sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) — GitHub プロキシ、setup script、リソース上限、許可ドメイン
- [Use Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) — GitHub 認証、App の位置づけ
- [Automate work with routines](https://code.claude.com/docs/en/routines) — トリガ、ブランチ push ルール、実行上限
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — skill の探索とクラウドでの読み込み

**関連文書:** 検証の経緯・出典の突き合わせ・訂正の記録は [`ccpm-addendum.md`](./ccpm-addendum.md) と [`ccpm-evidence-review.md`](./ccpm-evidence-review.md) にある。本ガイドはそれらの現時点の結論だけを抜き出したものである。

**実測環境:** Claude Code cloud セッション（Ubuntu 24.04 / x86_64 / 4 vCPU / 15 GB RAM / 30 GB 空き）。GitHub 到達は MCP サーバ経由に一本化された構成。
