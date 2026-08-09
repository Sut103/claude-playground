# CCPM を Claude Code クラウドで運用できるか — 統合レポート

**最終更新: 2026-08-09 / 初版: 2026-08-08（旧題「補遺: CCPM スキルを導入した場合の再検討」）**

**前提:** [自律型AIエージェント開発プラットフォーム vs CLI由来クラウド開発環境](./ai-dev-platform-comparison.md) と同条件
**対象:** [automazeio/ccpm](https://github.com/automazeio/ccpm) — GitHub Issues と Git worktree を使う、AI エージェント向けの spec-driven プロジェクト管理 Agent Skill

> **この文書について。** 複数セッションにまたがる調査を 1 本にまとめた正典である。検証の途中で 4 度の訂正（GitHub 到達性の原因、push 制限の内容、main push の可否、force-push の可否）が入っており、**訂正結果は本文に織り込み済み**。訂正の経緯そのものは[付録 A](#付録-a-検証履歴と訂正の記録)に、各主張の出典と裏付け／反証の突き合わせは[`docs/ccpm-evidence-review.md`](./ccpm-evidence-review.md) に分離した。

---

## 0. 結論

1. **CCPM は前回レポートの Phase 1（リポジトリをエージェント可読にする）を製品化したものである。** 「計画を `docs/` にコミットして `--cloud` で渡す」という手作業の推奨パターンを、PRD → Epic → Task → GitHub Issues という追跡可能なパイプラインに構造化する。前回の提案と競合せず、それを実装する手段になる。

2. **CCPM を入れると、Claude Code は Jules 型の「タスク単位委譲」を獲得する。しかも仕様がベンダーの外にある。** 仕様は `.claude/` と GitHub Issues に残り、CCPM 自体は agentskills.io 準拠で harness 非依存。**Jules を併用する理由は前回よりさらに薄くなる。**

3. **「CCPM がクラウドで動かない」のではない。書き換えが要るのは 4 層のうち 1 層と、ブランチ削除という 1 操作だけである。**

   | 層 | クラウドでの状態 |
   | --- | --- |
   | ファイル操作・決定的スクリプト（status / standup / 検索） | **無改修で動く** |
   | 並列実行（worktree・複数ブランチ push） | **無改修で動く**（実測で確認。当初の想定を訂正） |
   | GitHub 同期（epic-sync / issue-sync） | **書き換え必須** — `gh` 高レベル → `gh api` REST。かつ到達性がサーフェス依存 |
   | ライフサイクル終端（epic-merge・ブランチ整理） | **ブランチ削除のみ不可** — main への push は force-push まで含めて通る（実測） |

4. **物理制約は CCPM では解けないので「ローカルを手放せない」は不変。** ただし律速は VM のスペックではなく、**アカウント共有のレート制限とコンテキスト混線**である。

5. **導入判断に必要な最初の 1 手は「チームが実際に使うサーフェスで `gh api repos/{owner}/{repo}` が通るかを 1 回測ること」。** GitHub App の接続確認でもネットワーク設定でもない（3.1）。

---

## 1. CCPM の前提整理

| 要素 | 内容 |
| --- | --- |
| 中核原則 | 「すべてのコードは仕様に遡れる」。会話履歴ではなくファイルと GitHub に文脈を永続化する |
| ワークフロー | PRD → Epic → Task 分解 → GitHub Issues 同期 → worktree 作成 → 並列エージェント実行 → トラッキング |
| 状態の置き場 | `.claude/prds/`、`.claude/epics/<feature>/epic.md`、`<N>.md`（同期後は Issue 番号にリネーム）、`updates/` |
| タスクのメタデータ | frontmatter に `depends_on` / `parallel` / `conflicts_with` / 受け入れ条件 / 工数見積 |
| Source of truth | **GitHub Issues**。コメントが履歴になる。Projects API に依存しない |
| 並列化 | README の実例は **1 Issue を 5 エージェントで分担し、同一 worktree 内で同時に走らせる**形。worktree は epic 単位の隔離に使う |
| 配布形態 | Agent Skill（agentskills.io 仕様）。`skill/ccpm/` に `SKILL.md` + `references/` + bash スクリプト群 |
| 依存 | `git` + 認証済み `gh` CLI。オプションで `gh-sub-issue` 拡張（**無い場合はタスクリストに fallback するので停止はしない**） |

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

**結論: 「Jules 的な自律委譲が欲しい」という動機は CCPM でほぼ満たせる。** しかも CCPM は Claude Code に閉じないので、「Claude Code に賭ける」リスクのヘッジとしても機能する。

### 2.2 変えない点 — 物理制約

前回挙げた制約はどれも CCPM では解消しない。

- 4 vCPU / 16 GB RAM / 30 GB ディスク（公式記述・実測とも一致）
- egress 許可リスト（社内ネットワークの「中から」ではない）
- 専用シークレットストア不在、対話的 SSO 不可
- GitHub 前提（CCPM 本体の GitLab 対応 Issue は 2025-09 から未着手）

### 2.3 強化される点 — 前回挙げたアンチパターンへの処方箋になる

| 前回のアンチパターン | CCPM がどう効くか |
| --- | --- |
| 曖昧なまま `--cloud` に投げる | PRD と受け入れ条件が構造的に強制されるので、Jules 型の弱点（曖昧な要件を推測される）を回避できる |
| セッション共有に秘密が載る | チームの共有状態が GitHub Issues になるので、セッションリンクを共有する必要が減る |
| run が緑だから成功とみなす | 受け入れ条件と Issue コメントで成否を判定できる |
| ローカルの暗黙知が届かない | `.claude/` に仕様を集約する運用そのものが Phase 1 と一致する |

---

## 3. クラウドでの制約 — 確定した内容

各項目の末尾に根拠の種別を示す。**［実測］**＝本調査のセッション内で確認、**［公式］**＝Anthropic / GitHub のドキュメント、**［外部］**＝第三者の報告や Issue、**［未検証］**＝根拠が外部情報のみ。

### 3.1 GitHub API の到達性は「起動サーフェス」で決まる【最重要】

**プロキシは少なくとも 4 層の独立したゲートを持つ。** どの層で詰まるかで対処がまったく変わる。

| 層 | 制御主体 | 挙動 |
| --- | --- | --- |
| ① 一般の外向き通信 | 環境の network access 設定 | Trusted / Custom / Full。**GitHub 経路とは無関係**［公式・実測］ |
| ② GraphQL | プロキシ固定 | PR 用の pinned set 以外は 403。**自前トークンでも回避不可**［公式・実測］ |
| ③ API パス単位の書き込み許可 | プロキシ固定 | `git/refs` への書き込み（DELETE / PATCH）は `Write access to this GitHub API path is not permitted` で拒否。**repo スコープ判定より前に走る**［実測］ |
| ④ repo スコープ | セッションのサーフェス構成 | 添付済みリポジトリのみ。**サーフェスによっては添付済みでも 403**［実測・外部］ |

**④ が本題である。** 本調査のセッションでは、GitHub App は接続済み・リポジトリは push スコープで添付済み・`git` は正常なのに、`gh api repos/{owner}/{repo}` だけが 403 を返した。

```
$ gh api repos/{owner}/{repo}
403 {"message":"GitHub access is not enabled for this session.
     An org admin must connect the Claude GitHub App for this organization."}
$ gh api user
200 Sut103
```

**このエラー文は実態を表していない。** 公式ドキュメントが明言している。

> App installation enables PR webhooks for Auto-fix; **it is not a session-level access control.**

原因はセッションを起動したサーフェスの構成である。Claude Code Remote 系のサーフェスでは VM からの GitHub API 直接アクセスが設計上無効化され、到達は MCP サーバ経由に一本化される。同種の未解決 Issue が複数あり（[#76248](https://github.com/anthropics/claude-code/issues/76248)、[#70474](https://github.com/anthropics/claude-code/issues/70474)）、#76248 は**環境変数 `CCR_TEST_GITPROXY=1` まで本調査のセッションと一致する**。

**ネットワーク設定を緩めても解決しない［実測］。** 一般 egress を無制限（`selective: false`）にした環境で全項目を再測したが、結果は完全に一致した。公式も「GitHub operations use a separate proxy that is **independent of this setting**」と明記している。そもそも Trusted のデフォルト許可ドメインに `api.github.com` は最初から含まれている。

> **導入判断の第一歩はこれ。** チームが実際に使うサーフェスで `gh api repos/{owner}/{repo}` を 1 回叩く。所要 1 分。通らなければ CCPM の bash スクリプト層が丸ごと使えない。App の接続確認でもネットワーク設定の確認でも代用できない。

### 3.2 GraphQL 禁止により `gh` の高レベルサブコマンドが使えない

プロキシは PR 用の pinned set 以外の GraphQL を拒否する［公式・実測］。影響は `gh-sub-issue` にとどまらない。

| コマンド | 結果 | 根拠 |
| --- | --- | --- |
| `gh issue list` | **403（GraphQL pinned-set）** | ［実測］cli/cli のソースが GraphQL 実装であることを裏付け |
| `gh repo view` | **403（GraphQL pinned-set）** | ［実測］ |
| `gh sub-issue add` | **不可**（`addSubIssue` mutation を使う） | ［外部］ |
| `gh issue create` / `comment` / `close` | **未検証** | ［未検証］`-R owner/repo` でリポジトリ自動解決を回避すれば通る可能性がある |
| `gh api` + REST パス | **許可されている経路** | ［公式］プロキシのエラー文自身が案内している |

**対処:** CCPM のスクリプトを `gh api` の REST 形式へ書き換える。第三者もクラウドで `gh` を使う際に `-R owner/repo` の明示を必須としており、これはリポジトリ自動解決（GraphQL）が通らない症状と一致する。

**sub-issue は REST で張れる。** `POST /repos/{owner}/{repo}/issues/{n}/sub_issues`（GA 済み）。ただし **URL は issue number、body の `sub_issue_id` は内部 id** という非対称設計で、ここを取り違えると 404 になる。CCPM の `epic-sync` は Issue を自分で作る側なので、**作成レスポンスの `id` を捕まえれば number → id の解決 API は不要**（タスク 1 本あたり 1 往復節約）。実装雛形は [`docs/examples/ccpm-subissue-rest.sh`](./examples/ccpm-subissue-rest.sh)。

```bash
read -r num id < <(gh api --method POST "repos/$REPO/issues" \
  -f title="$title" -f body="$body" --jq '"\(.number) \(.id)"')
```

**MCP 経路では成功する［実測］。** 検証用 Issue 2 本で `sub_issue_write(add)` → `get_sub_issues` / `get_parent` の双方向を確認済み。実行主体は `performed_via_github_app: anthropics/claude` で、これは 3.1 の「403 は App の問題ではない」を決定的に裏付ける。**ただし MCP はモデルしか呼べない**ため、bash スクリプト層の代替にはならない。

**残る未検証:** `POST .../sub_issues` が Claude のプロキシ経由 REST でも通るか。REST エンドポイント自体は[第三者が実地で成功させている](https://jessehouwing.net/create-github-issue-hierarchy-using-the-api/)ので、不確実性はプロキシ経由の場合だけに絞られている。

### 3.3 `gh` CLI が pre-install されていない

Installed tools に `gh` はない［公式・実測］。CCPM は authenticated `gh` を required としている。

**対処:** Cloud environment の setup script に導入を入れる（結果はスナップショットされ毎回は走らない）。`apt-get install -y gh` は成功するが **2.45.0 と古い**［実測］。CCPM の Issue には 2.92.0 前提の記述があるため、新しい版が要るなら公式リポジトリから取得する必要があり、その際は `release-assets.githubusercontent.com` への到達が要る。

**注意:** `GITHUB_TOKEN` を直読みするスクリプトはプレースホルダ `proxy-injected` を掴んで失敗する。`gh` 経由なら問題ない［公式］。

### 3.4 並列実行 — worktree はそのまま動く【訂正済み】

> **初版では「push 制限により worktree 並列は成立しない」と結論していたが、これは誤りだった。**

同一セッションから 7 通りの push を実測し、**すべて成功**した。

| ブランチ名 | 操作 | 結果 |
| --- | --- | --- |
| `claude/ccpm-probe-a` / `-b` | 新規作成 | **成功** |
| `claude/ccpm-probe-epic/task-1` | `claude/` 配下ネスト | **成功** |
| `ccpm-probe-noprefix` | **プレフィックス無し** | **成功** |
| `feature/ccpm-probe` | 別プレフィックス | **成功** |
| `claude/ccpm-probe-a` | **worktree 内**から更新 | **成功** |
| `claude/ccpm-probe-epic/task-2` | **worktree 内**から新規ブランチ | **成功** |

**1 セッション・1 worktree から、名前を問わず複数ブランチへ push できる。** これは公式の規則と整合する — `claude/` プレフィックスは常に許可、それ以外も「保護ブランチ」「他者の PR がある」「他者のコミットを含む」のいずれにも当たらなければ通る［公式］。

**したがって CCPM の worktree 並列モデルは、push の面ではクラウドでそのまま動く。** 「1 タスク = 1 クラウドセッション」への読み替えは**必須ではなくなった**。むしろ後者は 3.7 のレート上限に当たるため、既定は worktree 並列でよい。

**残る並列度の制約はリソースではない。** CCPM README の実例は 5 エージェント（初版の「12 並列」は誤り）。5 であれば 4 vCPU / 16 GB でも同時ビルドを避ける限り成立する。実際の律速は次の 2 つ［公式・外部］。

- **レート制限** — クラウドセッションはアカウントの他の利用と枠を共有し、並列実行は比例して消費する
- **コンテキスト混線** — 1 セッションで複数タスクを扱うと破綻するという実践報告が複数ある

### 3.5 ライフサイクル終端がクラウドで完結しない【新規・重大】

CCPM の `epic-merge` は「テスト実行 → main へ no-ff マージ → push → ローカルファイルのアーカイブ → Issue クローズ」で閉じる。この最後の部分がクラウドでは実行できない。

**(A) main への push は通る【訂正・実測で確定】。**

初版は [#56474](https://github.com/anthropics/claude-code/issues/56474)（harness レベルの恒久ブロック、設定でも解除不可）を根拠に「main へは push できない」としていた。**リポジトリ所有者の許可を得て実測したところ、これは誤りだった。**

```
# ① fast-forward push
$ git push origin HEAD:refs/heads/main
   b64a5c5..40f287d  HEAD -> main                        ← 成功

# ② force-push で巻き戻し（非 fast-forward・履歴の書き換え）
$ git push --force origin b64a5c5:refs/heads/main
 + 40f287d...b64a5c5 -> main (forced update)             ← 成功

# ③ 対照: 同一セッションでのブランチ削除
$ git push origin --delete ccpm-probe-noprefix
error: RPC failed; HTTP 403                              ← 依然として拒否
```

**通常の push だけでなく、履歴を書き換える force-push まで通る。** main は検証前の状態に復元済みで、リポジトリに残った変更はない。素の `git push origin main` も harness に遮断されなかった。

> **プロキシが禁じているのは「ref の削除」であって、破壊的な更新一般ではない。** 直前まで「削除が塞がれている以上、非 fast-forward 更新も塞がれているだろう」と推測していたが、これも外れた。force-push は通り、削除だけが通らない。ゲートは操作の危険度ではなく、**操作の種類**で引かれている。

**CCPM への含意:** `epic-merge` の main へのマージ push は**そのまま動く**。PR ベースへの置換は、レビュー可能性という運用上の理由から推奨するにとどまる。**クラウドで技術的に不可能なのは、epic 完了後のブランチ削除だけである。**

**(B) ブランチ削除はどの経路でも不可［実測］。** 3 経路すべてで拒否され、しかも理由が異なる。

| 経路 | 結果 | 返る理由 |
| --- | --- | --- |
| git protocol（`git push --delete`） | 不可 | 説明文なしの 403、sideband 切断 |
| REST（`gh api --method DELETE .../git/refs/heads/x`） | 不可 | `Write access to this GitHub API path is not permitted through this proxy.` |
| GitHub MCP | 不可 | **ブランチ／ref 削除ツールが存在しない**（403 以前の問題） |

REST 側を切り分けると、ブロックされているのは DELETE という動詞ではなく **`git/refs` というパス**だった。同じ DELETE でも `labels` は repo スコープの 403 に落ち、`git/refs` への PATCH も同じ書き込みブロックになる。未アタッチのリポジトリに対しても同じ応答が返るため、この判定は repo スコープより前に走る（3.1 の層③）。

**ref の作成・更新は git protocol 経由で通るのに、削除・巻き戻しに相当する操作だけが両チャネルで塞がれている。** 意図的な設計と見るのが自然である。

**対処:** ブランチ整理は GitHub UI・ローカル・GitHub Actions のいずれかへ逃がす。**ここは技術的に選択の余地がない。** `epic-merge` の PR 化は、技術的強制ではなく運用上の推奨として扱う。

### 3.6 skill の配布 — symlink は届かないが代替が 2 つある

CCPM の Claude Code 向け手順は `ln -s /path/to/ccpm/skill/ccpm .claude/skills/ccpm` で、絶対パスの参照先はクラウド VM に存在しない。なお **symlink 自体は Claude Code が追跡する**［公式］ので、壊れるのは「symlink だから」ではなく「参照先が無いから」である。

**対処は 2 通り［公式］。**

1. skill の実体をリポジトリに vendoring する（`.claude/skills/ccpm/` に実ファイルとしてコミット）。クラウドセッションはクローンされたリポジトリの `.claude/skills/` を読み込む
2. リポジトリの `.claude/settings.json` にプラグインとして宣言する。**セッション開始時に自動インストールされる**ため、`/plugin` がクラウドで使えなくても機能する

CCPM は agentskills.io 準拠なので、`skill/ccpm/` を指すだけで有効になる。

### 3.7 Routines は Issue イベントで発火できず、実行上限もある

GitHub トリガの対応イベントは **Pull request と Release のみ**［公式］。`issues.assigned` や `issues.labeled` は存在しないため、「Issue にラベルが付いたら自動着手」は webhook では組めない。

**対処:** API トリガ（`/fire` エンドポイント）を GitHub Actions から叩く。ただし `text` として渡した内容は `<routine-fire-payload>` で untrusted としてラップされるため、**routine の prompt 側で「payload を参照して動け」と明示しないと不活性なコンテキスト扱いになる**［公式］。

**加えて 2 種類の上限がある［公式］。**

- GitHub webhook イベントに per-routine / per-account の**時間あたり上限**（超過分は破棄）
- routine 実行に**アカウント日次上限**

**この上限が「1 タスク = 1 クラウドセッション」案を既定にできない理由である。** 3.4 のとおり worktree 並列が動く以上、無理にセッションを分割する必要はない。

### 3.8 その他の細かい制約

- `.github/workflows/` 配下は `git push` も MCP write も通らない（プロキシの OAuth token に workflow scope がない）［外部］
- 未アタッチのリポジトリへの API・push は 403。`add_repo` が要る［公式・実測］
- 横断列挙エンドポイント（`user/repos` 等）は提供されない。`repos/{owner}/{repo}/...` の形に限られる［実測］
- **ローカルでも sandbox 有効時は `gh` が壊れうる**［外部］。プロキシの TLS MITM を Go の x509 verifier が拒否する（[#36363](https://github.com/anthropics/claude-code/issues/36363)）。「ローカルなら無改修」という前提は sandbox 構成では成り立たない可能性がある
- **CCPM 本体にも未修正の `gh` 依存バグが 2 件ある**［外部］。[#1024](https://github.com/automazeio/ccpm/issues/1024)（`gh issue create --json` は存在しないフラグ）、[#1022](https://github.com/automazeio/ccpm/issues/1022)（`gh sub-issue` の構文誤り）。**epic-sync はクラウド以前に、ローカルでもドキュメント通りには通らない**

---

## 4. CCPM 導入後の推奨アーキテクチャ

```
[ローカル]  PRD ブレスト ─→ Epic 分解 ─→ epic-sync
                                            │  (repo スコープ REST が通らないサーフェスではローカル固定)
                                            ▼
                                   GitHub Issues (source of truth)
                                            │
[クラウド]                     epic worktree で並列実行
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              claude/task-1  task-2      task-3     ← 複数ブランチ push 可（3.4）
                    └───────────┴───────────┘
                                │
                               PR  ← epic-merge の代替。main 直 push は不可（3.5）
                                │
[クラウド]                Auto-fix で CI 追従
                                │
[ローカル/UI]      マージ・ブランチ削除・重いテスト・teleport で引き取り
```

### CCPM フェーズ別のルーティング

| CCPM フェーズ | 実行場所 | 理由 |
| --- | --- | --- |
| PRD ブレスト | **ローカル** | 対話そのものが成果物。plan mode 向き |
| Epic 作成・タスク分解 | **ローカル** | 設計判断を含む。曖昧さをここで潰すのが全体の要 |
| `epic-sync`（Issue 同期） | **サーフェス次第** | repo スコープ REST が通るなら クラウド可。通らないならローカル固定（3.1） |
| タスク実行 | **クラウド** | **epic worktree の並列がそのまま使える**（3.4）。セッション分割は任意 |
| 進捗トラッキング（standup 等） | どちらでも | 状態は Issues にあるので実行場所を問わない。bash スクリプトなので安い |
| CI 追従 | **クラウド** | Auto-fix |
| `epic-merge` | **クラウド可** | main 直 push は force-push まで通る（3.5・実測）。PR 化は運用判断 |
| ブランチ整理 | **クラウド外** | 削除がどの経路でも不可（3.5）。**技術的に選択の余地がない** |
| 統合・重いテスト・デバッグ | **ローカル**（または self-hosted） | リソースと到達範囲 |

---

## 5. Phase ロードマップの改訂

**Phase 0（新設） — 1 分の到達性テスト**

チームが実際に使うサーフェスで `gh api repos/{owner}/{repo}` を叩く。**結果によって Phase 1 の作業量が変わる**ため、ここが最初。App の接続確認とネットワーク設定は判断材料にならない（3.1）。

**Phase 1（改訂） — リポジトリをエージェント可読にする + CCPM を載せる**

- CCPM skill を `.claude/skills/ccpm/` に**実ファイルとして** vendoring する、またはリポジトリの `.claude/settings.json` にプラグイン宣言する（3.6）
- Cloud environment の setup script に `gh` の導入を追加する。**版に注意**（3.3）
- **同期処理の先頭に preflight チェックを入れ、通らなければ何も書き込まずに中断する。** 中途半端な同期は Issue とタスクファイルの整合を壊す
- CCPM のスクリプトを監査し、`GITHUB_TOKEN` 直読みと GraphQL 依存箇所を洗い出す（3.2 / 3.3）
- **`gh` の高レベルサブコマンドを `gh api` の REST 形式に書き換える**（3.2）。`gh sub-issue` だけの問題ではない
- `docs/examples/ccpm-subissue-rest.sh` を雛形に、sub-issue 操作を REST 実装に差し替える
- **ブランチ整理の逃がし先を決める**（3.5）。クラウドから削除できないため、Actions か手作業の棚卸しを用意する
- `epic-merge` の PR 化を検討する（3.5）。**技術的強制ではないので、レビュー方針次第**
- **CCPM 本体の既知バグ 2 件にパッチを当てる**（3.8）
- モデル駆動の GitHub 操作は組み込み MCP ツールを使う方針を `CLAUDE.md` に明記する（3.2）
- **CCPM に乗せる閾値を決める。** 並列可能タスクが 3 本以上ある epic のみ CCPM を通す、など。小さな修正に PRD は過剰

**Phase 2（改訂） — 小さい epic を 1 本、通しで回す**

並列 2〜3 タスクの epic で PRD → sync → クラウドで worktree 並列実行 → PR → 統合まで通す。測るのは速度ではなく、**どのフェーズがどちら側で詰まったか**。

**Phase 3 — チーム運用に組み込む**

Auto-fix の標準化に加えて、Issue イベント → GitHub Actions → routine の `/fire` という起動経路を組む（3.7）。**日次・時間あたり上限を先に確認しておく。**

**Phase 4 — 並列度がレート制限に当たったら self-hosted 環境を検討する**

CCPM 本来の並列度を出したいとき、詰まるのは VM のスペックではなくアカウントのレート制限である（3.4）。self-hosted 環境かローカルの大きいマシンが選択肢になる。

---

## 6. CCPM 導入で新たに増えるリスク

| リスク | 内容と対策 |
| --- | --- |
| 儀式のコスト | 小さなタスクに PRD と Epic は過剰。閾値ルールを明文化しないと、チームが CCPM を迂回し始めて仕様と実装が乖離する |
| Issue の平坦化 | `gh-sub-issue` の fallback 運用だと Epic の階層が Issue 一覧上で見えなくなる。REST 実装に差し替えるか、ラベル運用で補う |
| **ブランチの堆積** | クラウドから削除できないため、epic を回すほどブランチが残る（3.5）。定期的な棚卸しを Actions か手作業で用意する |
| **レート制限の突然死** | 並列実行はアカウント枠を比例消費する。Opus で大量に回すと上限に到達するという実践報告がある。使用量の可視化を運用に組み込む |
| Phase 1 未完のまま導入 | 仕様は立派だが環境が組めず失敗する、という最悪の組み合わせになる。CCPM は Phase 1 の**代替ではなく上乗せ** |
| `.claude/` の名前空間衝突 | CCPM が `.claude/prds/`、`.claude/epics/`、独自の skills / commands を占有する。既存の命名と衝突しないか事前確認 |
| 仕様の陳腐化 | 「全行が仕様に遡れる」は運用が伴って初めて成立する。実装で判断が変わったら PRD/タスクファイルに戻して更新する規律が要る |
| **サーフェス依存の運用崩壊** | 同じアカウント・同じリポジトリでも、起動元が違えば `gh api` の可否が変わる（3.1）。使うサーフェスを固定し、preflight を必須にする |
| ベンダー依存の錯覚 | CCPM は harness 非依存だが、**Cloud environment の setup script とネットワーク設定は Anthropic 側に残る**。ここだけは移植できない |

---

## 7. Jules 併用判断の更新

前回の結論は「主軸を Claude Code に置いたうえでの限定併用は成立するが、既定では不要」だった。**CCPM 導入後は不要度がさらに上がる。**

理由: Jules を検討する動機は「タスク単位の自律委譲」「大量並列」「トレーサビリティ」だが、CCPM はそれらを**ベンダー非依存な形でリポジトリ内に再現する**。しかも Jules 型では得られない性質（仕様がレビュー可能、ローカルでも同じ仕様で動く、他 harness に移植可能）が付いてくる。

残る Jules の固有価値は「別のレート制限枠」と「Gemini 系モデルの別意見」程度。ただし **3.4 で判明したとおり、CCPM の実質的な律速はレート制限である**ため、「別枠」の価値は初版の想定よりやや上がっている。とはいえ CCPM のタスク定義があれば**どの実行系にも同じ仕様を渡せる**ので、必要になった時点で選べばよい。先に囲い込む理由はない。

---

## 8. 結論

- **ローカルが必要な理由は変わらない。** 物理制約（リソース・到達範囲・シークレット・SSO）は CCPM では解けない。
- **CCPM は、前回提案した「ルーティング設計」を実装する最良の手段である。** ローカルとクラウドの往復を、口頭の運用ルールではなく**仕様ファイルと Issue 状態**として表現できる。
- **クラウドで書き換えが要るのは GitHub 同期の 1 層だけ。** スクリプト層・並列実行層・`epic-merge` はそのまま動く。当初「4 層のうち 2 層」と見積もっていたが、**実際は 1 層と、ブランチ削除という 1 操作**だった。
- **GitHub 到達の詰まりは `gh` そのものではなく「VM 内から直接叩く経路」であり、しかもその可否は起動サーフェスで決まる。** 迂回路は 2 つあり、`gh api` の REST（スクリプト用）と組み込み MCP ツール（モデル用）を、**呼び出し主体で使い分ける**のが正解。CCPM の「決定的処理は bash」という設計を保てるのは前者だけである。
- **並列の軸は付け替えなくてよい。** worktree 並列はクラウドでそのまま動く（3.4・実測）。「1 タスク = 1 クラウドセッション」は選択肢の 1 つに留め、既定にはしない。routine の日次上限に当たるためである。

CCPM 導入後の役割分担は、前回の結論をより鮮明にする。**ローカルは「仕様を決める場所」、クラウドは「仕様を実行する場所」、GitHub Issues は「両者をつなぐ唯一の真実」。** そこに 1 つ足すなら、**「ブランチの後始末だけはクラウドの外」**である。

---

## 付録 A: 検証履歴と訂正の記録

本文は最新の結論のみを載せている。以下は、そこに至るまでに 2 度の訂正が入った経緯である。判断の再現性のために残す。

| 時点 | 主張 | その後 |
| --- | --- | --- |
| 初版 3.1 | GraphQL 403 により `gh-sub-issue` が動かない。影響は sub-issue 周辺 | **範囲を拡大して本文へ** — `gh issue list` / `repo view` も GraphQL 依存と判明（3.2） |
| 初版 3.3 | push は「そのセッションの現在の作業ブランチ」にのみ許可される。ゆえに worktree 並列は成立しない | **取り下げ** — 実測で名前を問わず複数ブランチ push が成功（3.4） |
| 初版 3.3 | CCPM は最大 12 エージェント並列を想定 | **訂正** — README の実例は 5 エージェント。数字の出所が不明（3.4） |
| 初版 3.4 | skill の symlink インストールが届かない。対策は vendoring | **補強** — symlink 自体は追跡される。対策はもう 1 つある（3.6） |
| 3.6 | GitHub 到達経路は 3 つあり、詰まるのは VM 直接経路のみ | 本文 3.1 の層構造へ統合 |
| 3.7 | repo スコープ 403 の原因は GitHub App が org 未接続だから | **訂正（3.8）** — App は接続済み。原因は起動サーフェス |
| 3.8 | 原因は起動サーフェスの構成 | **確証（3.10・外部検証）** — 公式ドキュメント 2 点と未解決 Issue 3 件が裏付け |
| 3.10 | ネットワークポリシーを開放しても GitHub API ゲートは不変 | 本文 3.1 の層①と④の分離として統合 |
| 3.11 | push 制限は「現在のブランチのみ」ではなかった。一方でブランチ削除は不可 | 本文 3.4 と 3.5 へ統合。削除は後に 3 経路すべてで不可と確認 |
| 統合時 | main への push は harness レベルで恒久ブロック（根拠: 外部 Issue のみ） | **取り下げ** — 実 push で確定。fast-forward も force-push も通る（3.5 A） |
| 統合時 | 削除が塞がれている以上、force-push も塞がれているだろう | **取り下げ** — force-push は通る。ゲートは危険度ではなく操作の種類で引かれている（3.5 A） |

**訂正が 3 度とも「制約を過大に見積もっていた」方向だった点は記録しておく価値がある。** 原因は 3 つに整理できる。

1. **エラーメッセージが実態と違う** — "An org admin must connect the Claude GitHub App" は App の問題ではなかった
2. **公式ドキュメントを当たる前に、実測から一般化した** — push 制限の記述がこれに当たる
3. **外部 Issue を実測せずに採用した** — main push の恒久ブロックがこれに当たる

**根拠の種別（実測／公式／外部／未検証）を各項目に明示する運用は、3 番目の失敗を検出するために有効だった。**「未検証」と印を付けていた項目が、実際に外れた。

## 付録 B: 出典と裏付け／反証の突き合わせ

各主張について、支持する情報と否定する情報の双方を収集した検証記録は [`docs/ccpm-evidence-review.md`](./ccpm-evidence-review.md) にある。9 つの仮説それぞれについて、公式ドキュメント・CCPM 本体のソースと Issue・GitHub CLI のソース・anthropics/claude-code の未解決 Issue・第三者の実践記事を突き合わせている。

---

## 参考

- [automazeio/ccpm](https://github.com/automazeio/ccpm) — CCPM 本体（Agent Skill）
- [yahsan2/gh-sub-issue](https://github.com/yahsan2/gh-sub-issue) — GraphQL `addSubIssue` を使う `gh` 拡張
- [petersontylerd/ccpm-codex](https://github.com/petersontylerd/ccpm-codex) — 他 harness への移植例
- [How we fixed the context problem in AI-driven development](https://aroussi.com/post/ccpm-claude-code-project-management) — CCPM の設計背景
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) — GitHub プロキシ、setup script、リソース上限
- [Automate work with routines](https://code.claude.com/docs/en/routines) — GitHub トリガの対応イベント、ブランチ push ルール、実行上限
- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) — GitHub 認証、App の位置づけ
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — skill の探索、symlink、クラウドでの読み込み
- [REST API endpoints for sub-issues](https://docs.github.com/en/rest/issues/sub-issues)

**実測環境:** Claude Code cloud セッション（Ubuntu 24.04 / x86_64 / 4 vCPU / 15 GB RAM / 30 GB 空き）, 2026-08-08 〜 2026-08-09。GitHub 到達は MCP サーバ経由に一本化された構成（`CCR_TEST_GITPROXY=1`）。
