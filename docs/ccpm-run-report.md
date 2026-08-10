# CCPM をクラウドセッションで通しで動かした記録

**2026-08-10 / 対象: [automazeio/ccpm](https://github.com/automazeio/ccpm) @ `7d7e462`**

前回の調査（[`ccpm-cloud-guide.md`](https://github.com/Sut103/claude-playground/blob/claude/ccpm-verification-check-lfny0d/docs/ccpm-cloud-guide.md)）は、冒頭でこう断っていた。

> **本調査では CCPM 自体を一度も起動していません。** インストールもしておらず、`/pm:init` も `epic-sync` も実行していません。

本セッションはそこを埋めた。**CCPM を実際に導入し、PRD から実装・マージまでを 1 本通した。** 題材はタスク管理 CLI（`taskcli`）で、Issue [#3](https://github.com/Sut103/claude-playground/issues/3)（Epic）と [#4〜#10](https://github.com/Sut103/claude-playground/issues/4)（タスク）が実際に作られ、クローズされている。

本文書に書くのはすべて**実行して観測した結果**である。推論は推論と明記する。

---

## 1. 結論

**CCPM はクラウドセッション単体で通しで動く。ただし CCPM のドキュメントどおりに実行すると壊れる。**

前回の推奨は「同期はローカルで、実行だけクラウドで」という配置だった。本セッションの結果は**それより踏み込める**ことを示している。`gh` を使う代わりに GitHub MCP ツールで同じ操作を構成すれば、`init` から `epic-merge` まで**すべてクラウド内で完結する**。ローカル環境は要らなかった。

一方で、**CCPM 本体の記述には実際に踏み抜いた不具合が 8 件あった**（うち 1 件は致命的）。これはクラウド固有の問題ではなく、**どの環境でも同じように踏む**。前回把握していた既知バグ 2 件とは別である。

| 前回 §10 の未確定事項 | 本セッションの結果 |
| --- | --- |
| #1 ローカルで CCPM が通しで動くか | **クラウドで通しで動いた**（ローカルは未検証のまま） |
| #2 分離配置が通しで機能するか | **分離不要と判明**。クラウド単体で完結した |
| #3 1 epic ブランチへの並行コミットは安定するか | **安定した。競合 0 件**（ただし別のコストが出た。§5） |
| #4 `gh api repos/{owner}/{repo}` が 200 を返す環境は実在するか | **本環境も 403。付録 A のルートは不成立** |
| #5 保護ブランチでの挙動 | 未検証（本リポジトリは保護なし） |

---

## 2. 環境の再測定

| 項目 | 結果 |
| --- | --- |
| `gh` CLI の導入（`apt-get install gh`） | ✅ 成功（2.45.0） |
| `gh auth status` | 「Failed to log in... token is invalid」だが**終了コードは 0** |
| `gh api repos/Sut103/claude-playground` | ❌ 403 |
| `gh issue list` / `gh repo view`（GraphQL） | ❌ 403 |
| `gh extension install yahsan2/gh-sub-issue` | ❌ 403（スコープ外リポジトリ） |
| GitHub MCP ツール（Issue 作成・更新・コメント・sub-issue） | ✅ すべて成功 |
| `pip install pytest` | ✅ 成功（9.1.1） |
| skill を `.claude/skills/ccpm/` に実ファイル配置 | ✅ **セッション再起動なしに認識された** |

前回の予測（付録 A.2「403 なら付録の内容はすべて不可能」）が的中した。**`gh` 経路は使えない。** 使えるのは MCP ツールだけである。

---

## 3. CCPM 本体で踏んだ不具合

すべて本セッションで実際に発生させ、原因を特定したものである。

### 3.1 【致命的】frontmatter 除去コマンドがファイル全体を消す

`conventions.md` と `sync.md` が指定するコマンド:

```bash
sed '1,/^---$/d; 1,/^---$/d' <file> > /tmp/body.md
```

GNU sed 4.9（Ubuntu 24.04）での実測:

```
入力:  ---\nname: x\nstatus: open\n---\n\n# Title\n\n本文1\n本文2\n
出力:  （空）
```

**このコマンドはファイル全体を削除する。** 手順どおりに `epic-sync` を実行すると、**作られる GitHub Issue の本文がすべて空になる。**

正しくは次のように書く必要がある。

```bash
sed '1{/^---$/!q}; 1,/^---$/d' <file>
```

macOS の BSD sed では通る可能性があり、それが見逃されている理由かもしれない。**本環境では検証できていないため、これは推測である。**

### 3.2 `init.sh` が全 GitHub 操作に失敗しながら「初期化完了」を報告する

実行結果（クラウドセッション、終了コード **0**）:

| チェック | 実際に起きたこと | `init.sh` の表示 |
| --- | --- | --- |
| `gh auth status` | トークン無効 | **✅ GitHub authenticated** |
| `gh extension install` | 403 で失敗 | エラーを出すが続行（Extensions: 0） |
| `gh repo view` | 403 | **ℹ️ Not a GitHub repository** |
| ラベル作成 | 実行されず | （無言でスキップ） |
| 総合 | 全滅 | **✅ Initialization Complete!** |

問題は 3 つある。

1. **`gh auth status` の判定が終了コードだけを見ている。** 無効なトークンでも 0 が返るため、認証チェックが偽陽性になる。スクリプト末尾では同じコマンドの出力から「Auth: Not authenticated」と表示しており、**同一スクリプト内で自己矛盾している**
2. **`gh repo view` の失敗を「GitHub リポジトリではない」と誤診する。** 実際には GitHub リポジトリであり、失敗の原因は API ゲートである。この誤診により `epic` / `task` ラベルが無言でスキップされる
3. **すべてに失敗しても exit 0 で成功バナーを出す。** 利用者は初期化が成功したと信じて次に進む

ラベルが作られていないため、後段の `gh issue create --label "epic,..."` は本来そこでも落ちる。

### 3.3 タスク番号のゼロ埋め規約が未定義

`structure.md` のテンプレートは `depends_on: []` としか書かず、**中身がゼロ埋め（`001`）か素の整数（`1`）かを規定していない。**

一方、CCPM 自身の実装は**ゼロ埋めを前提にしている**。

- `validate.sh` の依存チェックは `$epic_dir/$dep.md` の存在を見る → `depends_on: [1]` に対し `1.md` を探すが、実ファイルは `001.md`
- `sync.md` のリネーム手順は `sed "s/\b001\b/<new>/g"` と書く → 素の整数には一致しない

本セッションでは素の整数を採用したため、sync 前の `validate.sh` が**全依存関係を「missing」として警告した**。sync 後（ファイル名が `4.md`、`depends_on: [4]`）は全件パスしたので、原因はこの不一致で確定している。

**これは単純なバグというより仕様の穴である。** 規約が書かれていないため、テンプレートを素直に読むと `validate.sh` が使えなくなる — しかも sync 前という、一番検証したいタイミングで。

### 3.4 リネーム手順の sed がファイル全体を置換する

`sync.md` の指示:

```bash
sed -i.bak "s/\b001\b/<new_num_1>/g" <file>
```

`-i` でファイル全体を対象にするため、**本文中でタスク番号に言及していると壊れる。** 本セッションのタスクファイルは「003 / 004 / 005 と並行して実装できる」のように本文で番号を多用しており、この手順をそのまま適用すれば散文が破壊されていた。

置換すべきは frontmatter の `depends_on` / `conflicts_with` 行だけである。

### 3.5 【影響大】`<N>-analysis.md` が CCPM 自身の集計を壊す

`execute.md` は、Issue に着手する前に `.claude/epics/<name>/<N>-analysis.md` を作れと指示する。

ところが CCPM の全スクリプトは、タスクを `[0-9]*.md` というグロブで走査する。**`6-analysis.md` はこのグロブに一致する。**

実測（タスク 7 本、うち 3 本に analysis ファイルを作成後）:

```
$ bash epic-status.sh task-cli
  Total tasks: 10        ← 実際は 7
  🔄 Available: 4        ← analysis ファイルが「着手可能なタスク」として現れる

$ bash next.sh
  ✅ Ready: #6-analysis -     ← 名前が空のタスクが一覧に出る
```

エピック完了後、`conventions.md` の進捗計算式をそのまま適用した結果:

```
CCPM の式そのまま:      total=10 closed=7 progress=70%
analysis を除外した実際: total=7  closed=7 progress=100%
```

**7 本すべて完了しているエピックが、CCPM の式では 70% と報告される。** CCPM が「作れ」と指示するファイルが、CCPM の進捗計算を狂わせている。

### 3.6 `in-progress.sh` は execute フェーズの作業を検出できない

`execute.md` の Step 2 は、着手時に `updates/<N>/stream-<X>.md` を作れと指示する。

`in-progress.sh` は `updates/<N>/progress.md` の有無だけで判定する。`progress.md` は `sync.md` の issue-sync フローでしか作られない。

実測: **3 エージェントが実際に稼働している最中に「No active work items found」と表示された。**

規定どおりに着手した作業は、issue-sync を回すまで in-progress として見えない。

### 3.7 `validate.sh` が CCPM 自身の生成物を警告する

`sync.md` は `github-mapping.md` を frontmatter **なし**で作れと指示する。`validate.sh` はそれを「⚠️ Missing frontmatter」と警告する。

同じ出力の集計行も矛盾している。

```
  Errors: 0
  Warnings: 0
  Invalid files: 1
```

### 3.8 アーカイブすると完了エピックが集計から消える／数だけ残る

`sync.md` の epic-merge 手順に従って `.claude/epics/<name>` を `archived/` へ移動した後:

```
$ bash status.sh
  📚 Epics: Total: 0      ← 完了したエピックが消える
  📝 Tasks: Total: 0

$ bash epic-list.sh
  ✅ Completed: (none)    ← 一覧には出ない
  📊 Summary
     Total epics: 1       ← が、集計には数えられている
     Total tasks: 10
```

一覧と集計が同じ出力の中で食い違う。

### 3.9 前回把握していた既知バグ（本セッションでも確認）

- `gh issue create --json number -q .number` — `gh issue create` に `--json` フラグは存在しない（[#1024](https://github.com/automazeio/ccpm/issues/1024)）
- `gh sub-issue create --parent` の構文が誤り（[#1022](https://github.com/automazeio/ccpm/issues/1022)）

**3.1・3.9 を合わせると、`sync.md` の手順は 3 か所すべてで失敗する** — Issue 作成コマンドが存在しないフラグを使い、仮に通っても本文が空になり、sub-issue の構文も誤っている。**`epic-sync` はドキュメントどおりには 1 度も成功しない。**

---

## 4. `gh` を MCP に置き換える

`gh` が使えないため、GitHub 操作を MCP ツールで構成した。**CCPM のスクリプトは 1 行も変えていない。** 変えたのは「GitHub を叩く手段」だけである。

| CCPM の記述 | 代替 | 結果 |
| --- | --- | --- |
| `gh issue create` | `issue_write(method=create)` | ✅ |
| `gh sub-issue create --parent` | `sub_issue_write(method=add)` | ✅ |
| `gh issue comment` | `add_issue_comment` | ✅ |
| `gh issue close` | `issue_write(method=update, state=closed)` | ✅ |
| `gh label create` | **手段なし**（MCP に作成ツールが無い） | ⚠️ 不要だった |

**ラベルは Issue 作成時に自動生成された。** `epic` / `epic:task-cli` / `feature` / `task` はいずれも事前に存在しなかったが、`issue_write` の `labels` に渡すと既定色（`ededed`）で作られた。`init.sh` のラベル作成が失敗していても実害はない — ただし色と説明は付かない。

### MCP 経路固有のコスト

**`sub_issue_write` は呼び出しごとに親 Issue の本文全体を応答に含める。** Epic 本文が 9KB あったため、タスク 7 本を紐づけるだけで約 60KB がコンテキストに流れ込んだ。

`gh` なら 1 行の出力で済むところである。**タスク数 × Epic 本文長でコンテキストを消費するため、大きなエピックでは無視できない。** 本セッションでは途中からサブエージェントに委譲して回避した（サブエージェントは独立コンテキストを持つため、親には要約だけが返る）。

---

## 5. 並列実行 — 実際に走らせて分かったこと

前回 §10 #3 の「1 つの epic ブランチに複数エージェントが同時コミットする形は安定するか」に答える。

**構成**: worktree `../epic-task-cli`（ブランチ `epic/task-cli`）に対し、Issue #6（ストア層）/ #7（表示層）/ #8（コマンド層）を 3 エージェントで同時実行。書き込み先ファイルは完全に分離。

### 結果 1: git の競合は起きなかった

**3 エージェントとも 1 回目のコミットで成功した。`index.lock` のリトライは 0 回。**

効いた要因は明確で、各エージェントに「自分のファイルだけを明示パスで `git add` し、**`git add -A` を使うな**」と指示したことである。`git add -A` を使えば、隣のエージェントが書きかけのファイルを巻き込んでコミットしていた。

**CCPM の `execute.md` にはこの指示がない。** 「Each agent works only on files in its assigned stream scope」とは書いてあるが、ステージングの方法までは踏み込んでいない。エージェントが素朴に `git add -A` を選べば、並列実行は静かに壊れる。

### 結果 2: 統合時に 24 件のテストが壊れた

こちらが実際のコストだった。

Issue #8（コマンド層）は、まだ存在しない `store.py` / `render.py` に触れないよう、`cli.py` 内に**シーム**（`_load` / `_save` / `_tasks` …）を置く設計にした。ファイル分離は完璧に機能した。

しかし **#9 で実装へ結線した瞬間、#8 のテスト 24 件が落ちた。**

原因は、シームの契約が「関数のシグネチャ」までしか定めていなかったことである。**シームを流れるドキュメントの型が契約に入っていなかった。** #8 のテストはプレースホルダ実装の `list[Task]` に依存しており、実物の `store.Document` に差し替わった時点で `AttributeError` になった。

```
_tasks(doc) → doc.tasks     # Document なら通る、list なら AttributeError
```

**教訓は具体的である。並列化の境界を切るとき、「触るファイルが重ならない」だけでは足りない。境界を流れる型まで先に固定しなければ、統合時に手戻りが出る。** 本件は #9 のタスク仕様が「シグネチャを変えざるを得ない場合はテストも更新してよい」と事前に逃げ道を用意していたため吸収できたが、それが無ければ #8 の担当へ差し戻しになっていた。

### 結果 3: worktree を main から切ると仕様が入らない

`sync.md` の手順:

```bash
git checkout main && git pull origin main
git worktree add ../epic-<name> -b epic/<name>
```

タスク仕様は作業ブランチ上の `.claude/epics/` にある。**`.claude/` を main にマージしていなければ、この手順で作った worktree には仕様が 1 つも入らない。** エージェントは「Read full task from: .claude/epics/<epic>/<N>.md」と指示されるが、そのファイルが存在しない。

CCPM が暗黙に想定しているのは「main で直接作業するワークフロー」である。ブランチを切って作業する運用（本環境のように作業ブランチが指定される場合を含む）では、この手順は成立しない。現在のブランチから切って回避した。

---

## 6. 成果物 — CCPM は仕様どおりのものを作れたか

CCPM のワークフローの是非とは別に、**出てきたコードの質**も記録しておく。

| 指標 | 結果 |
| --- | --- |
| テスト | **215 件パス**（単体 199 + E2E 16）、失敗 0・skip 0 |
| Success Criteria | **6 項目すべて合格、未達 0 件** |
| 実行時依存 | 標準ライブラリのみ（`ast` による集合演算で機械的に確認） |
| 実ターミナルでの通し実行 | 全ステップ `$? = 0` |
| NFR-4（1000 件で 1 秒以内） | 0.069 秒（要求の約 1/14） |

受け入れ確認（Issue #10）は**限界も正直に記録している**。

- US-2 の「GitHub 上でチェックリストとしてレンダリングされる」は自動検証できておらず、目視に頼っている。合格に繰り上げず「部分的」とした
- NFR-4 に対応する自動テストが存在しなかった。実測で合格を確認したが、**回帰を検出する手段は無いまま**

**仕様が文書として存在していたことの効果は、はっきり観測できた。** 3 エージェントが互いを見ずに書いた `store.py` / `render.py` / `cli.py` は、結線時に**型の不一致 1 件を除いて噛み合った**。AD-5（「今日」を注入可能にする）のような細かい設計判断も、独立に実装された 2 か所で一貫していた。仕様に書いてあったからである。

---

## 7. 実際にやるなら

### 7.1 CCPM を入れる前に当てるパッチ

**§3.1 は必須。** これを直さずに `epic-sync` を実行すると、本文が空の Issue が量産される。

```bash
# conventions.md / sync.md の frontmatter 除去
- sed '1,/^---$/d; 1,/^---$/d' <file>
+ sed '1{/^---$/!q}; 1,/^---$/d' <file>
```

次いで §3.5。`analysis` ファイルを集計から外す。

```bash
# 全スクリプトのタスク走査
- for task_file in "$epic_dir"/[0-9]*.md; do
+ for task_file in "$epic_dir"/[0-9]*.md; do
+   case "$task_file" in *-analysis.md) continue;; esac
```

§3.2 の `init.sh` は、クラウドで使うなら**丸ごと使わない**のが早い。やっていることはディレクトリ作成と `CLAUDE.md` の雛形生成で、`mkdir -p` で足りる。

### 7.2 並列実行の指示に足すこと

`execute.md` のエージェントプロンプトに 2 行足す。

```
- 自分のファイルだけを明示パスで git add すること。git add -A / git add . を使わない
- 隣のストリームと共有する型・データ構造は、着手前に確定させて記載する
```

前者が無いと git が壊れ、後者が無いと統合が壊れる。**本セッションで実際に起きたのは後者だけだが、それは前者を先回りして指示していたからである。**

### 7.3 配置

**クラウド単体で完結する。** ローカル環境は要らなかった。前回の推奨（同期はローカル）は、`gh` を使う前提での結論であり、MCP で置き換えれば不要になる。

ただし条件が 2 つある。

1. **GitHub 操作をモデルから呼ぶことになる。** `gh` のように bash から叩けないため、CCPM が「決定的処理は LLM を通さず bash で」と定めた原則からは外れる。Issue を 10 件作るループがモデルの手番になる
2. **ブランチの削除だけは依然としてできない。** 前回の実測どおり。「Automatically delete head branches」を有効にするのが現実的

### 7.4 そもそも入れるべきか

前回のガイドが挙げた「費用対効果」の疑問（§9 最終行）に、実行してみた立場から答える。

**CCPM が実際に効いたのは、並列実行を成立させる仕様の粒度である。** 3 エージェントに独立して作業させて噛み合わせるには、「何を作るか」だけでなく「どのファイルを触るか」「どの型でやり取りするか」まで書かれた仕様が要る。CCPM のタスクファイル形式（`depends_on` / `parallel` / `conflicts_with` + 受け入れ基準）は、まさにそれを書かせる型になっている。

**逆に、CCPM が足していない部分も明確だった。** GitHub Issue との同期は、並列実行そのものには寄与していない。エージェントが読んだのはリポジトリ内のファイルであって Issue ではない。Issue が効くのは**人間が後から経緯を追うとき**である。

したがって判断はこう分かれる。

- **並列実行のための仕様粒度が欲しいだけなら** — CCPM のタスクファイル形式だけ借りて `docs/` に置く運用で足りる。同期の不具合を踏まずに済む
- **人間のレビューと監査証跡が要るなら** — Issue 同期に価値がある。ただし §7.1 のパッチは必須

**小さな変更に PRD と Epic は過剰である。** 本セッションの題材（7 タスク・23 時間見積もり）はちょうど下限あたりで、これより小さければ儀式のコストが上回る。

---

## 8. 本セッションで検証していないこと

- **ローカル環境での CCPM の動作**（前回 §10 #1 は依然として未検証）。本セッションはクラウドのみ
- **保護ブランチでの挙動**（前回 §10 #5）
- **§3.1 が BSD sed（macOS）でも壊れるか。** GNU sed 4.9 でのみ確認
- **5 本以上の並列**。本セッションは 3 本まで
- **複数エージェントが同一ファイルを触る場合**。本セッションは意図的に完全分離した。CCPM の `execute.md` が想定する「共有ファイルは 1 ストリームが担当し、他はその後 pull」は未検証
- **レート制限の消費量**。計測していない

---

## 関連文書

- [`ccpm-cloud-guide.md`](https://github.com/Sut103/claude-playground/blob/claude/ccpm-verification-check-lfny0d/docs/ccpm-cloud-guide.md) — 前回の環境調査（CCPM 未起動）
- [`ccpm-addendum.md`](https://github.com/Sut103/claude-playground/blob/claude/ccpm-verification-check-lfny0d/docs/ccpm-addendum.md) — 検証の経緯と訂正の記録
- [`ccpm-evidence-review.md`](https://github.com/Sut103/claude-playground/blob/claude/ccpm-verification-check-lfny0d/docs/ccpm-evidence-review.md) — 出典の突き合わせ

**実行環境:** Claude Code クラウドセッション（Ubuntu 24.04 / x86_64 / Python 3.11.15 / GNU sed 4.9 / gh 2.45.0）。GitHub 到達は MCP サーバ経由。
