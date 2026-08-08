# 自律型AIエージェント開発プラットフォーム vs CLI由来クラウド開発環境

**調査日: 2026-08-08 / 対象: Google Jules 型プラットフォーム と Claude Code on the Web**

---

## 0. 結論

1. **両者は「同じものの別実装」ではない。「制御を人間からエージェントに渡す単位」が違う。**
   Jules 型は**タスク単位**で丸ごと委譲する（発注 → 計画承認 → 非同期実行 → PR）。Claude Code は**セッション単位**で連続的に共同作業する。on the Web はその共同作業モデルを実行場所ごとクラウドに移しただけで、思想は CLI のままである。

2. **「ローカル + Claude Code は手放せない」という所感は正しい。ただし理由は「on the Web が未熟だから」ではない。**
   Claude Code on the Web は仕様として、リソース上限（4 vCPU / 16 GB / 30 GB）、egress 制限、ローカル設定の非継承、シークレットストア不在、GitHub 前提という境界を持つ。これらは成熟で消える類のものではなく、「隔離されたクラウド VM」という選択の裏返しである。

3. **したがって取るべき戦略は「主軸を on the Web に移す」ではなく「作業の種類でルーティングする」。**
   移行の本体は環境の乗り換えではなく、**リポジトリをエージェント可読にする投資**である。この投資はローカル・クラウド・将来の他社エージェントすべてに効く。

---

## 1. 二つの起点

### 1.1 Jules 型 —— 「完全自律を前提に、後から人間の介入口を足す」

Jules は編集画面に組み込まれたアシスタントではなく、**リポジトリに紐づく非同期エージェント**として設計されている。タスクを渡すと、専用の Google Cloud VM にリポジトリをクローンし、計画を提示し、承認後に自律実行して、PR を返す。人間の既定の役割は「発注者兼レビュアー」であり、ラップトップを閉じてよい。

設計上の帰結:

| 要素 | Jules 型での扱い |
| --- | --- |
| 実行単位 | **タスク**。開始と終了が明確で、成果物は PR に収束する |
| 人間の介入点 | 主として**計画の承認**と**PR レビュー**。実行中の割り込みは可能だが主作用ではない |
| 環境定義 | **プラットフォーム側**に置く（環境変数設定、依存導入を固めた Environment Snapshot） |
| 拡張 | MCP は審査済みリスト中心。統制を優先し、任意のツール接続は絞られる |
| 対話 | 非同期が既定。要件を自己完結したブリーフとして書く必要があり、対話で詰める文化とは相性が悪い |

弱点として繰り返し指摘されるのも、この設計から素直に導かれる: 要件が曖昧だとエージェントが「壊れている」の意味を推測して 1 本の PR を出してしまう、実 DB を要する統合テストなどサンドボックス外の依存で詰まる、タイトな反復には往復が重い、といったもの。

### 1.2 Claude Code on the Web —— 「対話型ランタイムを、そのままクラウドに置く」

Claude Code on the Web は新しい製品ではなく、**同じ Claude Code を Anthropic 管理の VM（Ubuntu 24.04 / x86_64）で動かしたもの**である。セッション、permission、`/compact`、`/context`、subagent、skills、hooks といった CLI の概念がそのまま持ち込まれ、UI が claude.ai に変わっているにすぎない。

設計上の帰結:

| 要素 | Claude Code on the Web での扱い |
| --- | --- |
| 実行単位 | **セッション**。会話が続く限り生き、休止で VM が回収されても再開時に履歴ごと復元される |
| 人間の介入点 | 会話の任意の時点。差分ビューに**インラインコメント**を書いて次のメッセージに載せられる |
| 環境定義 | **リポジトリ側**が主。`CLAUDE.md` / `.claude/settings.json` / `.claude/skills` / `.claude/agents` / `.claude/commands` / `.mcp.json` はクローンに含まれる。プラットフォーム側は「Cloud environment」（ネットワーク許可レベル・環境変数・setup script）だけを持つ |
| 拡張 | ローカルと同じ MCP・skills・hooks・plugins。ただし**リポジトリにコミットされたものだけ**が届く |
| 成果物 | PR に限らない。調査結果、差分、レビューコメント、Slack への報告など会話の産物すべて |
| ローカルとの連続性 | `claude --cloud` で送り、`claude --teleport` でブランチと会話履歴ごとローカルに引き戻せる |

---

## 2. 軸別比較

| 軸 | Jules 型（自律前提プラットフォーム） | Claude Code on the Web（CLI 由来） |
| --- | --- | --- |
| 委譲の単位 | タスク | セッション（会話） |
| 既定の人間の役割 | 発注者 / レビュアー | 共同作業者（必要に応じて発注者にも回れる） |
| 介入の粒度 | 計画承認と PR レビュー（粗い） | 任意のターン、任意の差分行（細かい） |
| 設定の所在 | プラットフォームの管理画面 | **リポジトリ**（= バージョン管理・レビュー・再現可能） |
| 設定の移植性 | プラットフォームに固着 | Git にあるので他サーフェスにそのまま効く |
| 曖昧な要件 | 推測して 1 本の PR にする | 途中で聞き返せる／plan mode で先に詰められる |
| 出力 | PR に収束 | PR、調査、差分、コメント、任意の副産物 |
| 並列実行 | プラットフォームの中核ユースケース | 複数セッション / routines で可能（レート制限を消費） |
| 到達範囲 | 隔離 VM の中 | 隔離 VM の中（ただし self-hosted 環境と Remote Control という抜け道がある） |
| 中断からの復帰 | タスク再実行 | セッション再開、または teleport してローカル続行 |

**この表で最も重要な行は「設定の所在」である。** Jules 型は環境をプラットフォームに置くので、設定はレビューできず、diff も取れず、そのベンダーから外に出せない。Claude Code はエージェントの振る舞いを規定するものを可能な限りリポジトリに置く。結果として、**ローカルでもクラウドでも Slack でも routines でも、同じリポジトリなら同じ振る舞いになる**。チーム移行を考えるなら、この性質が資産の蓄積先を決める。

---

## 3. いま業界は「両方持つ」方向に収斂している

この点は判断に直結するので明示しておく。

- **Jules** は当初 Web 完結だったが、後から **Jules Tools（CLI）と公開 API** を追加した。ターミナルと CI/CD への接続を求められたためである。
- **Devin** は「委譲するクラウドエージェント」単体から、**Devin Desktop（IDE）/ Devin Cloud / Devin CLI / Devin Review** の 4 面構成になった。
- **Google Antigravity** はエージェント優先の IDE として、Editor View と Manager View（複数エージェントの管理ダッシュボード）を併置する。
- **Claude Code** は逆方向、CLI から web / mobile / routines / Slack / self-hosted 環境へ広がった。

つまり **「自律クラウド型」と「対話ローカル型」のどちらが正しいかという競争は 2026 年時点でほぼ決着しており、答えは『両方を、切り替え可能な形で持つ』である。** 「on the Web を主軸にする」という問いの立て方自体を、「どの作業をどちらに流すか」に置き換えるべきである。

---

## 4. ローカル + Claude Code を手放せない具体的理由

所感の裏付けとして、公式ドキュメントで確認できる制約を挙げる。「使ってみた印象」ではなく仕様である。

### 4.1 計算資源

Anthropic ホスト環境のセッションは概ね **4 vCPU / 16 GB RAM / 30 GB ディスク**。大規模ビルドやメモリを食うテストは VM 側で停止されうる。モノレポの全体ビルド、ネイティブコンパイル、大きなデータセットを扱うテストはここで頭を打つ。

### 4.2 到達範囲（ネットワーク）

Cloud environment の egress は **None / Trusted（既定の許可リスト）/ Full / Custom** の 4 段階。既定の Trusted はパッケージレジストリと GitHub 等に限られる。社内 API、社内パッケージレジストリ、VPN 内のステージング環境に触るには Custom で明示的に開ける必要があり、それでも「社内ネットワークの中から」ではない。

> 実例: **この調査そのものが egress 制限に当たった。** 本レポートを書いている Claude Code cloud セッションから `jules.google` と `developers.googleblog.com` は許可リスト外で `EGRESS_BLOCKED` となり、一次情報に直接到達できなかった（Jules に関する記述が二次情報中心なのはこのため）。制約は抽象論ではなく日常的に効く。

### 4.3 認証とシークレット

- **専用のシークレットストアがまだ無い。** 環境変数と setup script は環境設定に平文で置かれ、その環境を使う全員から読める。
- **AWS SSO のようなブラウザ経由の対話的認証は不可。**
- GitHub 認証はプロキシ経由で行われ、`GITHUB_TOKEN` は既定でプレースホルダ `proxy-injected` として見える。トークンを直接読むスクリプトは動かない。

### 4.4 ローカル設定は継承されない

| 継承される | 継承されない |
| --- | --- |
| リポジトリの `CLAUDE.md` | 個人の `~/.claude/CLAUDE.md` |
| リポジトリの `.claude/skills`, `.claude/agents`, `.claude/commands` | `~/.claude/` 配下の個人 skills / agents / commands |
| リポジトリの `.mcp.json`（project scope） | `claude mcp add` の local / user scope で入れた MCP |
| リポジトリの `.claude/settings.json` の hooks | user 設定でだけ有効化した plugins |
| 組織の server-managed settings | MDM 配布のデバイス設定 |

チームが各自のローカルに積み上げてきたノウハウは、**リポジトリにコミットしない限りクラウドセッションでは存在しない**。これは移行作業の実体そのもの（後述 Phase 1）。

### 4.5 プラットフォーム前提

- クローンと PR 作成は **GitHub 前提**。GitLab / Bitbucket はローカルバンドルとして送れるが、**結果を push で戻せない**。
- GitHub プロキシは GraphQL を限定オペレーションのみ許可するため、**GraphQL にしか存在しない API（Projects v2 など）には到達できない**。
- 組織で **IP allowlist** を有効にしていると、Anthropic ホストのクラウドセッションは認証エラーで全滅する（例外申請が必要）。
- **Zero Data Retention** 組織はクラウドセッション機能そのものが使えない。

### 4.6 対話の粒度とフィードバックループ

探索・設計・デバッグのように「数十秒ごとに方向を変える」作業は、ブラウザ越しの往復とコンテナ起動のオーバーヘッドが効いてくる。動いている UI を見る、デバッガを当てる、プロファイラを回す、実機やシミュレータを触る、といった作業は本質的にローカル側にある。`/plugin` や `/resume` のようにターミナル専用のコマンドも残る。

### 4.7 ただし逃げ道は用意されている（ここが Jules 型との差）

- **Remote Control** — ローカルで動く Claude Code セッションを claude.ai / モバイルから操作する。実行とファイルアクセスはローカルのまま、ローカル MCP もローカルツールも生きたまま、外から steering できる。「重い処理はローカル、指示は電車の中から」が成立する。
- **Self-hosted environments** — Team / Enterprise 向けに、クラウドセッションを**自社インフラの runner** で動かす。リソース上限も egress 境界も自社の裁量になる。4.1〜4.2 の制約はここで実質的に解消できる。
- **teleport** — クラウドで走らせた作業を、ブランチと会話履歴ごとローカルに引き取って続行できる。

**Jules 型プラットフォームにはこの「同じエージェント・同じ設定のまま実行場所だけを移す」経路が無い。** ローカルを手放せないという直感が正しいのと同じくらい、「だから Claude Code を選ぶ」という結論も同じ事実から出てくる。

---

## 5. 逆に、クラウドに寄せるべき作業

- **並列で回したい退屈で定義の明確な作業** — 依存更新、テスト追加、lint 修正、flaky test の潰し込み、リネーム/大規模リファクタ。`claude --cloud "..."` を複数投げてセッションごとに独立実行できる。
- **CI への追従** — Auto-fix PR。CI 失敗とレビューコメントの webhook を受けて、明確な修正は push、曖昧なものは質問して止まる。
- **定期・イベント駆動の自動化（Routines）** — スケジュール / API POST / GitHub イベント（PR・Release）をトリガに、ラップトップを閉じたまま動く。夜間のバックログ整理、デプロイ後のスモーク、docs drift の追跡、アラート起点の調査 PR など。
- **手元にクローンしていないリポジトリへの単発作業**。
- **オンボーディングとクリーンルーム再現** — 「自分のマシンでは動く」問題の切り分けに、毎回新品の VM は効く。
- **モバイルからの起動と確認**。

---

## 6. 推奨する移行戦略

### 6.1 原則: ルーティングを設計する

「主軸を移す」ではなく、**作業の性質でどちらに流すかを決め、その判断をチームの共通言語にする**。

| 作業の性質 | 流す先 |
| --- | --- |
| 要件が曖昧・設計判断を含む | ローカル（plan mode で詰める） |
| 要件が明確・自己完結・退屈 | クラウド（`--cloud` / routines） |
| 重いビルド・重いテスト・実機/GPU | ローカル（または self-hosted 環境） |
| 社内ネットワーク・社内 DB・SSO が要る | ローカル（または self-hosted 環境） |
| 並列で 3 本以上同時に走らせたい | クラウド |
| CI 追従・PR レビュー対応 | クラウド（Auto-fix） |
| 定期実行・イベント駆動 | クラウド（Routines） |
| デバッグ・プロファイリング・UI 目視 | ローカル |
| 外出中・移動中の steering | Remote Control（実行はローカル）またはクラウド |

**推奨する既定パターン: 「ローカルで計画、クラウドで実行」。** plan mode で方針を詰め、計画を `docs/` にコミットして push し、`claude --cloud "Execute the migration plan in docs/xxx.md"` で自律実行に渡す。曖昧さの解決を人間の得意な場所で済ませてから委譲するので、Jules 型の弱点（曖昧な要件を推測される）を構造的に回避できる。

### 6.2 段階ロードマップ

順序に意味がある。特に Phase 1 を飛ばすと、以降がすべて空回りする。

**Phase 1 — リポジトリをエージェント可読にする（最重要・両環境に効く）**

これが移行作業の本体である。各自のローカルに散っている暗黙知を、リポジトリの資産に変換する。

- `CLAUDE.md` — ビルド・テスト・lint のコマンド、ディレクトリ規約、やってはいけないこと
- `.claude/skills/`, `.claude/agents/`, `.claude/commands/` — 各自の `~/.claude/` にあるものをチーム資産として棚卸しし、リポジトリへ移す
- `.mcp.json` — MCP は `claude mcp add --scope project` で project scope にしてコミットする
- **SessionStart hook** — `npm install` のような「ローカルでもクラウドでも毎回必要な準備」はここに置く。ローカルとクラウドの両方で走る
- **setup script（Cloud environment 側）** — pre-install されていないツールチェーン（.NET SDK など）の導入。VM をプロビジョニングする性質のものだけをここに置く。5 分以内に終わり、exit 0 すること。結果はスナップショットとしてキャッシュされ、以降のセッションでは再実行されない（約 7 日で失効、内容変更時も再構築）
- **`git clone` 直後にテストと lint がワンコマンドで通る状態**にする。これが満たされないと、クラウドセッションの失敗の大半が「環境が組めなかった」になる

Phase 1 の副次効果として、新メンバーのオンボーディングと CI の安定性も同時に改善する。

**Phase 2 — 低リスク作業をクラウドに出す**

依存更新、テスト追加、docs 更新、flaky test 修正から始める。ここで測るのは「速さ」ではなく **「クラウドセッションが環境問題ではなく本質的な理由で失敗する率」**。前者が残っているうちは Phase 1 に戻る。

**Phase 3 — チーム運用に組み込む**

- 自分が作った PR には Auto-fix を有効化する運用を標準にする
- Routines を導入する（PR レビューのチェックリスト適用、夜間のバックログ整理、デプロイ後検証など）
- ただし **Routines は個人アカウントに属し、チーム共有されない**。GitHub 上のコミットや PR、connector の操作は**作成者本人として現れる**。チーム運用に載せるなら誰の名義で動いているかを明示すること

**Phase 4 — 制約が痛くなってから拡張する**

- リソース上限や社内ネットワーク到達が繰り返しボトルネックになるなら **self-hosted environments** を検討する（Team / Enterprise）
- IP allowlist や ZDR の運用があるなら、そもそもクラウドセッションの可否を先に確認する

### 6.3 見るべき指標

- クラウドセッションのうち、**環境起因で失敗した割合**（Phase 1 の完成度の代理指標）
- クラウド発の PR の **手戻り率**（曖昧な委譲をしていないか）
- **ローカルに teleport で引き戻した回数と理由**（ルーティング表を更新する材料になる）
- レート制限の消費（並列実行はアカウントの利用枠を比例して食う）

### 6.4 アンチパターン

- **Phase 1 を飛ばして人数分のクラウドセッションを配る** — 各自のローカル設定が届かないので、全員が「手元より賢くない」という体験をして定着しない
- **ローカルを禁止する** — 4 章の制約に日常的にぶつかる
- **`--cloud` を「速い委譲」だと思う** — 委譲のコストは実行時間ではなくレビューに現れる。曖昧なまま投げると PR レビューで払う
- **run が緑だったから成功とみなす** — Routines の緑ステータスは「インフラエラー無しで終了した」の意味であって、タスクの成否ではない。transcript を読む必要がある

---

## 7. Jules 等を併用する意味はあるか

**主軸を Claude Code に置いたうえでの限定併用は成立するが、既定では不要。**

併用のコスト:
- 環境定義の二重化（Jules はプラットフォーム側、Claude Code はリポジトリ側に設定を持つため、Phase 1 の資産が Jules には効かない）
- レビュー導線の分散
- タスク枠がユーザ単位で、チームでプールできない

意味があるケース:
- 使い捨ての大量並列タスクを、別のレート制限枠で回したい
- Gemini 系モデルの出力を「別の意見」として得たい（同じ課題に別モデルをぶつけるのは有効な使い方ではある）
- Google Cloud に密着した運用をしている

実務的な結論としては、**Claude Code を対話的エンジニアリングの主軸に据え、長時間の使い捨て並列作業だけ第二の実行系を検討する**という構成が妥当。実際、複数のエージェントを併走させるチームでもこの分担が一般的である。

---

## 8. 導入時に注意すべきリスク

| リスク | 内容 |
| --- | --- |
| 環境変数の可視性 | Cloud environment の env vars と setup script は、その環境を使う全員が読める。専用シークレットストアはまだ無い |
| Auto-fix と comment 起点の自動化 | Claude は**あなたの GitHub アカウントで**レビューコメントに返信する。`issue_comment` で発火する Atlantis / Terraform Cloud / 自作 Actions がある リポジトリでは、インフラ操作を誘発しうる。該当リポジトリでは Auto-fix を切る |
| セッション共有 | Pro / Max の共有は既定で「公開」（claude.ai ログインユーザ全員）かつリポジトリアクセス検証が既定オフ。プライベートリポジトリのコードや資格情報が載っている可能性を前提に確認する。Team / Enterprise は Private / Team で検証が既定オン |
| GitHub App の権限誤解 | GitHub App のインストール範囲は**セッションのアクセス制御ではない**。接続した GitHub アカウントが見えるリポジトリにはすべて到達できる。絞りたいなら GitHub 側で絞る |
| Auto-fix とマージコンフリクト | base branch 進行によるコンフリクトは webhook が飛ばないため Auto-fix は自力で反応できない。セッションを開いて rebase を指示する必要がある |
| レート制限 | クラウドセッションはアカウントの利用枠を他の Claude 利用と共有する。並列実行は比例して消費する（VM 自体への追加課金は無い） |

---

## 9. まとめ

| | Jules 型 | Claude Code on the Web | ローカル Claude Code |
| --- | --- | --- | --- |
| 委譲の単位 | タスク | セッション | セッション |
| 最も得意なこと | 定義の明確な作業の大量並列 | 明確な作業の並列 + 会話による軌道修正 | 探索・設計・デバッグ・重い処理 |
| 設定の置き場 | プラットフォーム | リポジトリ | リポジトリ + ローカル |
| 到達範囲 | 隔離 VM | 隔離 VM（self-hosted で拡張可） | マシンとネットワークのすべて |
| 逃げ道 | なし | teleport / Remote Control / self-hosted | — |

**あなたの所感への回答:** ローカル + Claude Code は手放せない。ただしそれは on the Web の欠点ではなく、隔離クラウド VM という選択の必然的な裏面であり、Anthropic 自身がその前提で teleport・Remote Control・self-hosted environments という接続経路を用意している。**「移行」を「乗り換え」と定義すると失敗する。「同じリポジトリ資産の上で、実行場所を作業に応じて選べる状態」と定義すれば、それは達成可能で、しかも投資のほとんど（Phase 1）は実行場所に依存しない。**

---

## 参考

**一次情報（Claude Code 公式ドキュメント）**
- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments)
- [Automate work with routines](https://code.claude.com/docs/en/routines)
- [Remote Control](https://code.claude.com/docs/en/remote-control)

**Jules / 他プラットフォーム（二次情報中心 — `jules.google` は本セッションの egress 制限により直接参照不可）**
- [Jules: Google's autonomous AI coding agent (Google Blog)](https://blog.google/innovation-and-ai/models-and-research/google-labs/jules/)
- [Jules introduces new tools and API for developers (Google Blog)](https://blog.google/innovation-and-ai/models-and-research/google-labs/jules-tools-jules-api/)
- [Google's Jules coding agent adds CLI, API (InfoWorld)](https://www.infoworld.com/article/4070496/googles-jules-coding-agent-adds-cli-api.html)
- [Google's Jules enters developers' toolchains (TechCrunch)](https://techcrunch.com/2025/10/02/googles-jules-enters-developers-toolchains-as-ai-coding-agent-competition-heats-up/)
- [Jules: Google's Coding Agent Explained (morphllm)](https://www.morphllm.com/comparisons/jules-google-coding-agent)
- [Google Jules: Gemini Async Coding Agent Guide 2026 (digitalapplied)](https://www.digitalapplied.com/blog/google-jules-gemini-async-coding-agent-guide)
- [Google Jules First Look: Not Ready for Prime Time (Hyperdev)](https://hyperdev.matsuoka.com/p/google-jules-first-look-not-ready)
- [Top AI Coding Agents and Development Platforms in 2026 (MarkTechPost)](https://www.marktechpost.com/2026/06/10/ai-coding-agents-development-platforms-2026/)
- [Build with Google Antigravity (Google Developers Blog)](https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/)
