# CCPM 実行の時系列 — 忠実に通った箇所と、代替した箇所

本文書は [`ccpm-run-report.md`](./ccpm-run-report.md) の実行を、**時系列**で「CCPM の記述どおりにやったか」「`gh` を使ったか」の 2 軸で切り分けた記録である。

## 凡例

| 記号 | 意味 |
| --- | --- |
| ✅ | CCPM の記述どおりに実行し、成功した |
| ⚠️ | CCPM の記述どおりに**実行し、失敗した**。代替手段を使った |
| 🔍 | CCPM の記述を**読んだ時点で不備を特定し、実行せずに**代替した（失敗を発生させていない） |
| ⛔ | CCPM が指示しているが、**実施しなかった** |
| gh✅ / gh❌ | `gh` を実行して成功／失敗 |

**「⚠️」と「🔍」の区別は重要である。** 前者は実際に踏み抜いた不具合、後者は事前に回避したため実害が出ていない。後者を「失敗した」と書くのは誇張になる。

---

## 第 0 段階: 環境準備（CCPM 実行前）

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 0-1 | `curl codeload.github.com/automazeio/ccpm` で CCPM を取得 | — | **失敗**（403 / セッションのリポジトリスコープ外）<br>**代替**: `add_repo(automazeio/ccpm, read)` → `git clone` で取得 |
| 0-2 | `apt-get install gh` | gh✅ | 成功（2.45.0）。Ubuntu の版は古いが動作する |
| 0-3 | `gh auth status` | gh❌ | 「The token in GH_TOKEN is invalid」と表示。**ただし終了コードは 0** |
| 0-4 | `gh repo view --json` | gh❌ | 403 — GraphQL がプロキシで遮断 |
| 0-5 | `gh issue list` | gh❌ | 403 — 同上 |
| 0-6 | `gh api repos/Sut103/claude-playground` | gh❌ | 403「GitHub access is not enabled for this session」 |
| 0-7 | `gh api repos/.../issues`、`gh api repos/.../labels` | gh❌ | 403 — 同上 |
| 0-8 | GitHub 到達手段の確保 | — | **代替**: GitHub MCP ツール。`list_issues` / `get_me` が成功し、**以降の GitHub 操作はすべて MCP に一本化**した |

**この時点で `gh` の使用可能範囲が確定した。** 高レベルサブコマンド（`issue` / `repo` / `pr`）は全滅、`gh api` も 403。以降、CCPM が `gh` を指示する箇所はすべて MCP に置き換えることになる。

---

## 第 1 段階: 導入

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 1-1 | skill の配置 | 🔍 | CCPM 公式手順は `ln -s /path/to/ccpm/skill/ccpm ~/.claude/skills/ccpm` の**シンボリックリンク**。クラウドセッションでは参照先が永続せずリポジトリにも入らないため、**実行せず**、`.claude/skills/ccpm/` へ**実ファイルとしてコピー**した<br>結果: **セッション再起動なしに skill が認識された** |
| 1-2 | `init.sh` の実行 | ⚠️ gh❌ | **CCPM の記述どおり実行した。終了コード 0、「✅ Initialization Complete!」を表示。しかし中身は全滅**（下表） |

### 1-2 の内訳（すべて `init.sh` 内部）

| `init.sh` の処理 | 実際 | 表示 |
| --- | --- | --- |
| `gh auth status` | gh❌ トークン無効 | **✅ GitHub authenticated**（終了コード 0 だけを見ているため偽陽性） |
| `gh extension install yahsan2/gh-sub-issue` | gh❌ 403 | エラーを出すが続行（Extensions: 0） |
| `gh repo view` | gh❌ 403 | **ℹ️ Not a GitHub repository**（誤診） |
| `gh label create epic` / `task` | **未実行**（上の誤診で `else` 分岐に入りスキップ） | 無言 |
| ディレクトリ作成・`CLAUDE.md` 生成 | ✅ 成功 | ✅ |

**代替**: ラベルは作成しないまま先へ進んだ（後述 3-3 で問題にならないことが判明）。

---

## 第 2 段階: Plan フェーズ

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 2-1 | `Skill(ccpm)` で skill を起動 | ✅ | 成功。`SKILL.md` が読み込まれた |
| 2-2 | `plan.md` 規定のブレスト（問題・利用者・成功条件・スコープ外・制約） | ✅ | 成功。対話で 4 問を確認 |
| 2-3 | `.claude/prds/task-cli.md` の作成（frontmatter スキーマ、9 セクション、品質ゲート） | ✅ | 成功 |
| 2-4 | `prd-list.sh` / `prd-status.sh` / `status.sh` | ✅ | 3 本とも正常動作 |
| 2-5 | `.claude/epics/task-cli/epic.md` の作成 | ✅（軽微な逸脱） | 成功。ただし `plan.md` のテンプレートが指定する `### Frontend Components` / `### Backend Services` / `### Infrastructure` は CLI ツールに該当しないため、**層構成（パーサ／ストア／表示／コマンド）に置き換えた**。その旨をエピック本文に明記 |

**Plan フェーズは CCPM の記述どおりに完走した。** GitHub には一切触れないフェーズであり、`gh` も不要だった。

---

## 第 3 段階: Structure フェーズ

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 3-1 | `structure.md` 規定の「5〜10 タスクは並列 Task エージェント（3〜4件/バッチ）」で分解 | ✅ | 成功。2 バッチ（001-003 / 004-007）で 7 タスク。**バッチ間で frontmatter の形式・依存値とも一貫していた** |
| 3-2 | `epic.md` への `## Tasks Created` 追記 | ✅ | 成功 |
| 3-3 | `epic-list.sh` / `epic-status.sh` / `next.sh` / `blocked.sh` / `in-progress.sh` / `standup.sh` | ✅ | 6 本とも正常動作。依存グラフも正しく解釈された |
| 3-4 | `validate.sh` | ⚠️ | **実行して失敗**。全 7 件の依存を「references missing task」と誤警告。原因は `depends_on: [1]` に対し `1.md` を探すが実ファイルが `001.md` であること（**CCPM はゼロ埋めの有無を規定していない**）<br>**代替**: 警告を無視して続行。sync 後（ファイル名 `4.md`／`depends_on: [4]`）に再実行し**全件パス**したことで原因を確定 |

---

## 第 4 段階: Sync フェーズ — ここが最も置き換えの多い区間

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 4-1 | リポジトリ安全チェック（remote が `automazeio/ccpm` でないこと） | ✅ | CCPM のシェル片をそのまま実行、成功 |
| 4-2 | frontmatter 除去 `sed '1,/^---$/d; 1,/^---$/d'` | ⚠️ | **CCPM の記述どおり実行し、8 ファイルすべてが 0 バイトになった**。最小再現も取り、GNU sed 4.9 でファイル全体が消えることを確認<br>**代替**: `sed '1{/^---$/!q}; 1,/^---$/d'` に差し替え、正常に本文を抽出 |
| 4-3 | Epic Issue の作成（CCPM: `gh issue create --json number -q .number`） | 🔍 gh❌ | 0-4〜0-7 で `gh` の高レベルサブコマンドが 403 と確定していたため**実行せず**（加えて `gh issue create` に `--json` は存在しない — 既知バグ #1024）<br>**代替**: `mcp__github__issue_write(method=create)` → **#3 作成成功** |
| 4-4 | ラベル `epic` / `epic:task-cli` / `feature` の付与 | — | `get_label` で**いずれも未作成**と確認（1-2 の帰結）。MCP に**ラベル作成ツールは存在しない**<br>**結果**: `issue_write` の `labels` に渡したところ **GitHub 側が既定色 `ededed` で自動生成**した。追加の代替手段は不要だった |
| 4-5 | タスク Issue 7 件の作成 | 🔍 gh❌ | 同上。**代替**: `issue_write(method=create)` を 7 回 → **#4〜#10 作成成功** |
| 4-6 | sub-issue 階層の構築（CCPM: `gh sub-issue create --parent`） | 🔍 gh❌ | 拡張自体が 1-2 で導入失敗。構文も誤り（既知バグ #1022）<br>**代替**: `mcp__github__sub_issue_write(method=add)` を 7 回 → `sub_issues_summary.total = 7`。**ただし本ツールは呼び出しごとに親 Issue 本文全体を返すため、途中からサブエージェントに委譲**してコンテキスト消費を回避 |
| 4-7 | タスクファイルのリネームと依存の再マップ（CCPM: `sed -i.bak "s/\b001\b/<new>/g" <file>`） | 🔍 | **記述を読んだ時点でファイル全体置換だと判明**。本セッションのタスク本文は「003 / 004 / 005 と並行して」のように番号を多用しており、実行すれば散文が壊れた。**実行せず**<br>**代替**: frontmatter の `depends_on` / `conflicts_with` 行のみを書き換えるスクリプト。001→4 … 007→10 のリネームと依存再マップに成功 |
| 4-8 | frontmatter の `github:` / `updated:` 更新（CCPM: `sed -i.bak "/^github:/c\\..."`） | ✅ | CCPM の書式そのままで成功 |
| 4-9 | worktree 作成（CCPM: `git checkout main && git pull` してから `git worktree add ../epic-<name> -b epic/<name>`） | 🔍 | **main には `.claude/` が無いため、記述どおりだとタスク仕様ゼロの worktree ができる**と判明。**実行せず**<br>**代替**: 現在の作業ブランチから `git worktree add ../epic-task-cli -b epic/task-cli`。worktree 内に仕様 7 件が入ることを確認 |
| 4-10 | `github-mapping.md` の作成 | ✅ | CCPM の書式どおり作成、成功 |
| 4-11 | `validate.sh` の再実行 | ✅ | **依存参照が全件パス**（3-4 の原因確定）。ただし `github-mapping.md` を「Missing frontmatter」と警告 — **CCPM 自身が frontmatter なしで作れと指示したファイル** |

---

## 第 5 段階: Execute フェーズ

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 5-1 | `<N>-analysis.md` の作成（`execute.md` 規定） | ✅（が後段に副作用） | 3 件作成、成功。**ただしこれが 5-6 の集計破壊を引き起こす** |
| 5-2 | `updates/<N>/stream-<X>.md` の作成（Step 2） | ✅ | 3 件、エージェントが作成 |
| 5-3 | 並列エージェントの起動（Step 3、`execute.md` のプロンプト雛形に準拠） | ✅（指示を 1 点補強） | **#6 / #7 / #8 を同一 worktree・同一ブランチで 3 並列。git のインデックス競合 0 件、全員 1 回目のコミットで成功**<br>**CCPM に無い補強**: 「`git add -A` を使わず自分のファイルを明示パスで add せよ」。CCPM は「自分のスコープのファイルだけ作業せよ」と書くがステージング方法までは規定していない。素朴に `git add -A` を選べば隣のエージェントの書きかけを巻き込む |
| 5-4 | `gh issue edit <N> --add-assignee @me --add-label "in-progress"`（Step 4） | ⛔ gh❌ | **実施しなかった。** `gh` が使えず、MCP での代替も行っていない。GitHub 上の Issue は着手中も `open` のまま、担当者・`in-progress` ラベルは付いていない |
| 5-5 | `execution-status.md` の作成（Step 5） | ✅ | 成功 |
| 5-6 | 稼働中に `epic-status.sh` / `next.sh` を実行 | ⚠️ | **実行して誤結果**。`[0-9]*.md` グロブが `6-analysis.md` に一致し、**タスク数が 7 → 10 に水増し**。`next.sh` は名前が空の `#6-analysis` を「Ready」と表示<br>**代替**: 集計時に `-analysis` を除外して読む（スクリプトは修正していない） |
| 5-7 | 稼働中に `in-progress.sh` を実行 | ⚠️ | **実行して失敗**。3 エージェントが稼働中にもかかわらず「No active work items found」。原因は `updates/<N>/progress.md` の有無で判定するが、`execute.md` が作らせるのは `stream-<X>.md` であること<br>**代替**: `git log` と `git status` で直接観測 |
| 5-8 | #9 での結線 | ✅（CCPM 規定内で対処） | シームを実装呼び出しへ置換 → **#8 のテスト 24 件が失敗**。原因はシームの契約が関数シグネチャまでで、**流れるドキュメント型が未定義**だったこと。#9 のタスク仕様が「シグネチャを変えざるを得ない場合はテストも更新してよい」と定めていたため、その範囲内でテストを `store.Document` へ更新し解消 |

---

## 第 6 段階: Sync フェーズ（進捗コメント）

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 6-1 | issue-sync（CCPM: `updates/<N>/progress.md` を集約して `gh issue comment`） | ⛔ 🔍 gh❌ | **CCPM の issue-sync フローは実施していない。** `progress.md` を作っていないため前提を満たさない（作ったのは `stream-A.md`）<br>**代替**: 同期完了時と完了時に、`mcp__github__add_issue_comment` でエージェントが直接コメントを投稿した。Epic #3 に同期記録 1 件、タスク #4〜#10 に完了報告 7 件、Epic #3 に完了報告 1 件 |

---

## 第 7 段階: Close / Merge フェーズ

| # | 操作 | 分類 | 結果・代替 |
| --- | --- | --- | --- |
| 7-1 | タスクの frontmatter を `status: closed` に更新 | ✅ | 7 件成功 |
| 7-2 | エピック進捗の再計算（`conventions.md` の式） | ⚠️ | **実行して誤結果**。`total=10 closed=7 → 70%`。実際は 7/7 で 100%。原因は 5-1 の analysis ファイル<br>**代替**: `-analysis` を除外して算出し、`progress: 100%` を記録 |
| 7-3 | Epic 本文のタスクリストを `- [x]` に更新（ローカル `epic.md`） | ✅ | 成功 |
| 7-4 | Epic **Issue 本文**の `- [ ] #<N>` を `- [x] #<N>` に更新（CCPM close 手順 Step 4、`gh issue view` → `sed` → `gh issue edit`） | ⛔ gh❌ | **実施しなかった。** 前提が成立しない — CCPM の sync 手順は Epic 本文にタスクを `- [ ] #<N>` 形式で書くことを想定しているが、`epic.md` の `## Tasks Created` はファイル名（`001.md`）で書かれており、`#<N>` 形式のチェックリストが Epic Issue 本文に存在しない<br>**代替**: 対応表を Epic #3 のコメントとして投稿し、sub-issue 階層（GitHub が自動で完了数を表示）に委ねた |
| 7-5 | タスク Issue のクローズ（CCPM: `gh issue comment` → `gh issue close`） | 🔍 gh❌ | **代替**: `add_issue_comment` → `issue_write(method=update, state=closed, state_reason=completed)` を 7 件。全件成功 |
| 7-6 | Epic Issue のクローズ | 🔍 gh❌ | **代替**: 同上。#3 をクローズ |
| 7-7 | worktree でのテスト実行 → main へマージ（CCPM: `git merge --no-ff`） | ✅ | 215 件パスを確認後、`git merge epic/task-cli --no-ff` 成功。**ただし「main」は指定作業ブランチ `claude/ccpm-implementation-simulation-vl7yc5` に読み替えた** |
| 7-8 | `git worktree remove` | ✅ | 成功 |
| 7-9 | `git branch -d epic/task-cli` | ✅ | 成功（ローカル） |
| 7-10 | `git push origin --delete epic/<name>` | ⛔ | **実施しなかった。** epic ブランチはローカルのみで push していないため対象が存在しない。なお前回調査でクラウドからのリモートブランチ削除は 3 経路すべて不可と実測済み |
| 7-11 | `.claude/epics/task-cli` → `archived/` へ移動 | ✅ | 成功。**ただし直後の `status.sh` で完了エピックが集計から消え、`epic-list.sh` は一覧「(none)」と集計「Total epics: 1」が矛盾** |

---

## 4 つの問いへの直接の回答

### 問 1: CCPM に忠実に成功した箇所

| 区分 | 該当箇所 |
| --- | --- |
| Plan フェーズ | ブレスト手順、PRD スキーマと品質ゲート、Epic 変換（2-2〜2-5） |
| Structure フェーズ | 並列 Task エージェントによる分解、タスクファイル形式、`## Tasks Created` 追記（3-1、3-2） |
| 報告系スクリプト | `status` / `standup` / `prd-list` / `prd-status` / `epic-list` / `epic-status` / `next` / `blocked` — **GitHub に触れないため無改修で動く**（2-4、3-3） |
| Sync の一部 | リポジトリ安全チェック、frontmatter フィールド更新、`github-mapping.md`（4-1、4-8、4-10） |
| Execute フェーズ | analysis ファイル、stream ファイル、`execution-status.md`、**並列エージェントの起動と協調そのもの**（5-1〜5-3、5-5） |
| Merge フェーズ | worktree でのテスト → `--no-ff` マージ → worktree 削除 → ブランチ削除 → アーカイブ（7-7〜7-9、7-11） |

**総じて、GitHub API を経由しない部分は CCPM の記述どおりに動いた。**

### 問 2: CCPM に忠実に実行して失敗し、代替を使った箇所

| # | 箇所 | 失敗内容 | 代替手段 |
| --- | --- | --- | --- |
| 1-2 | `init.sh` | 全 GitHub 操作に失敗しつつ exit 0 で成功表示 | ラベル未作成のまま続行（4-4 で自動生成され実害なし） |
| 3-4 | `validate.sh`（sync 前） | 全依存を「missing」と誤警告 | 警告を無視。sync 後の再実行で原因を確定 |
| 4-2 | frontmatter 除去 sed | **8 ファイルすべてが 0 バイトに** | `sed '1{/^---$/!q}; 1,/^---$/d'` |
| 5-6 | `epic-status.sh` / `next.sh` | analysis ファイルを数え、7 → 10 に水増し | 集計時に `-analysis` を除外して読む |
| 5-7 | `in-progress.sh` | 3 エージェント稼働中に「No active work items found」 | `git log` / `git status` で直接観測 |
| 7-2 | 進捗計算式 | 7/7 完了を 70% と算出 | `-analysis` を除外して 100% を記録 |
| 7-11 | アーカイブ後の `status.sh` / `epic-list.sh` | 完了エピックが集計から消える／一覧と集計が矛盾 | なし（記録のみ） |

**別枠: 実行せずに回避した箇所（🔍）** — 4-7（リネーム sed のファイル全体置換）、4-9（main から worktree を切ると仕様ゼロになる）、1-1（symlink 配布）。いずれも記述を読んだ時点で不備が判明したため実行しておらず、**実害は発生していない**。

### 問 3: `gh` を用いて成功した箇所

**`gh` が成功したのは、インストールとバージョン確認だけである。**

| # | 操作 | 結果 |
| --- | --- | --- |
| 0-2 | `apt-get install gh` | ✅ 2.45.0 |
| 1-2 | `gh --version`（`init.sh` 内） | ✅ |
| 0-3 | `gh auth status` | △ 終了コード 0（が、トークンは無効。実質失敗） |

**GitHub API に到達する `gh` の操作は 1 つも成功していない。**

### 問 4: `gh` を用いてうまくいかず、代替を使った箇所

| # | `gh` の操作 | 失敗 | 代替手段 |
| --- | --- | --- | --- |
| 0-4 | `gh repo view --json` | 403（GraphQL） | `mcp__github__get_me` / `list_issues` で到達性を確認 |
| 0-5 | `gh issue list` | 403（GraphQL） | `mcp__github__list_issues` |
| 0-6, 0-7 | `gh api repos/{owner}/{repo}` ほか | 403（repo スコープ） | 同上 |
| 1-2 | `gh extension install yahsan2/gh-sub-issue` | 403 | `mcp__github__sub_issue_write` |
| 1-2 | `gh label create`（誤診によりそもそも未実行） | — | 不要だった（`issue_write` の `labels` で GitHub が自動生成） |

**以下は `gh` が使えないと 0-4〜0-7 で確定していたため、実行せずに最初から MCP を使った箇所である。**

| CCPM の指示 | 代替手段 | 実績 |
| --- | --- | --- |
| `gh issue create`（Epic） | `mcp__github__issue_write(method=create)` | #3 |
| `gh issue create`（タスク × 7） | 同上 | #4〜#10 |
| `gh sub-issue create --parent` | `mcp__github__sub_issue_write(method=add)` | 7 件、`total = 7` |
| `gh issue comment` | `mcp__github__add_issue_comment` | 9 件 |
| `gh issue close` | `mcp__github__issue_write(method=update, state=closed, state_reason=completed)` | 8 件 |
| `gh issue edit --add-assignee/--add-label` | **代替なし（未実施）** | — |
| `gh issue view` → `sed` → `gh issue edit`（Epic 本文のチェック） | **代替なし（前提不成立のため未実施）** | — |

---

## まとめ

- **CCPM のうち GitHub に触れない部分は、記述どおりに動く。** Plan / Structure / 報告系スクリプト / 並列実行の枠組みは無改修で通った
- **GitHub に触れる部分は、記述どおりには 1 度も通らない。** `gh` の高レベルサブコマンドが 403 であることに加え、CCPM 側にも既知バグ 2 件（存在しない `--json` フラグ、誤った sub-issue 構文）と本セッションで発見した frontmatter 除去の致命的バグがある
- **代替は一貫して GitHub MCP ツールである。** Issue の作成・コメント・クローズ・sub-issue 階層はすべて MCP で構成でき、**CCPM のスクリプト自体は 1 行も変えていない**
- **`gh` は結局インストールした意味がなかった。** API に届く操作は 1 つも成功していない
- **未実施が 3 件ある** — 着手時のアサイン／ラベル付与（5-4）、issue-sync フロー（6-1）、Epic 本文のチェックボックス更新（7-4）。いずれも運用上の追跡性に関わる部分で、埋めるなら MCP で代替できる
