# Claude Code on the Web における「リポジトリ共通設定」の検証結果

対象アカウント: 個人プラン（Pro/Max 相当）／ 検証日: 2026-08-08
検証環境: 実際のクラウドセッション VM（Claude Code v2.1.226, Ubuntu 24.04 x86_64）

---

## 0. 結論（先に要約）

**ご懸念は半分正しく、半分は回避可能です。**

- **正しい部分**: claude.ai/code の「クラウド環境（Cloud environment）」に設定する
  **ネットワークアクセス / 環境変数 / セットアップスクリプト**の 3 つは、
  個人アカウントに紐づく**個人設定**です。リポジトリ側から指定する手段は無く、
  メンバーごとに再作成が必要です。**個人プランではここが最大の穴**になります。
- **回避可能な部分**: それ以外のほぼ全ての設定
  （指示・ルール・hooks・権限・MCP・スキル・サブエージェント・プラグイン）は
  **リポジトリにコミットすれば全員・全セッションに共通で効きます**。
  特に **SessionStart hook** を使えば、セットアップスクリプトの役割の大半を
  リポジトリ側に移せます。
- **組織アカウント（Team / Enterprise）なら穴も塞げます**:
  **組織共有環境（Organization-shared environments）** により、セットアップ
  スクリプトと環境変数そのものを管理者が一元配布できます。加えて
  **サーバー管理設定（Server-managed settings）** で組織全体のポリシーを強制できます。

---

## 1. クラウドセッションの実測データ

実際のセッション VM 内で確認した値:

```
CLAUDE_CODE_REMOTE=true
CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=cloud_default   # = Default 環境で稼働中
CLAUDE_CODE_VERSION / claude --version = 2.1.226
GH_TOKEN=proxy-injected            # 実トークンは VM 内に存在しない（GitHub プロキシ経由）
HOME=/root
```

設定レイヤーの実在確認:

| 確認項目 | 結果 | 意味 |
| --- | --- | --- |
| `~/.claude/settings.json` | **存在しない** | ユーザー設定はクラウドに来ない（実証） |
| `~/.claude/remote-settings.json` | **存在しない** | 個人プランのためサーバー管理設定なし（実証） |
| `/etc/claude-code/managed-settings.json` | **存在しない** | MDM 由来の設定はクラウドに届かない（実証） |
| `~/.claude/skills/` | **存在する**（docx, pdf, pptx, xlsx, skill-creator 等） | claude.ai で各自が有効化したスキルが同期される = **個人差が出る経路** |
| `~/.claude/launcher-settings.json` | 存在する | プラットフォーム側が注入する hook（git identity 等） |

診断ログ上の設定読み込み:

```
settings_load_completed  source_count: 4, error_count: 0
setup_hooks_captured     (セッション開始時に 1 回)
hook_spawn_started/completed  hook_event_name: SessionStart, exit_code: 0
```

### 実証した重要な制約

セッション開始**後**に `.claude/settings.json` を新規作成し、PostToolUse hook を
仕込んで Write ツールを 2 回実行したが、**hook は発火しなかった**。
診断ログ上も `settings_load` はセッション開始時の 2 回のみで、再読み込みは発生していない。

> **hooks はセッション開始時（clone 直後）にキャプチャされる。**
> したがってリポジトリ共通設定は「コミット済みであること」が前提であり、
> 検証は必ず**新しいセッションを開始して**行う必要がある。

---

## 2. リポジトリにコミットすれば共通化できるもの（公式表 + 実測）

| 対象 | クラウドセッションに届くか | 備考 |
| --- | --- | --- |
| `CLAUDE.md` | ✅ | clone に含まれる |
| `.claude/rules/` | ✅ | 同上 |
| `.claude/settings.json` の hooks | ✅ | **セットアップスクリプト代替の本命** |
| `.claude/settings.json` の permissions / env | ✅ | 権限ルールは各スコープでマージされる |
| `.claude/skills/`, `.claude/agents/`, `.claude/commands/` | ✅ | 同上 |
| `.mcp.json`（MCP サーバー） | ✅ | `claude mcp add --scope project` で生成しコミット |
| `extraKnownMarketplaces` / `enabledPlugins` | ✅ | セッション開始時にマーケットプレイスから自動インストール（要ネットワーク） |
| `~/.claude/CLAUDE.md`（ユーザー） | ❌ | マシン上にありリポジトリに無い |
| `~/.claude/skills/`, `agents/`, `commands/` | ❌ | 同上。`.claude/` にコミットして代替 |
| ユーザー設定の `enabledPlugins` | ❌ | リポジトリの `.claude/settings.json` に宣言し直す |
| `claude mcp add`（local / user スコープ） | ❌ | `~/.claude.json` に書かれるため。`--scope project` を使う |
| `.claude/settings.json` の `env` のうち通信系 | ❌ | `NODE_EXTRA_CA_CERTS` や mTLS 変数はホスト側が管理するため無視される |
| 静的な API トークン・認証情報 | ❌ | 専用のシークレットストアが未提供 |
| AWS SSO 等の対話的認証 | ❌ | ブラウザログインが不可能 |
| MDM 配布の managed-settings | ❌ | VM は Anthropic 管理のため届かない |

### セットアップスクリプト vs SessionStart hook

これが本件の核心です。

| | セットアップスクリプト | SessionStart hook |
| --- | --- | --- |
| 設定場所 | claude.ai/code の環境ダイアログ（**個人設定・共通化不可**） | リポジトリの `.claude/settings.json`（**共通化可**） |
| 実行タイミング | Claude Code 起動**前**、キャッシュ未構築時のみ | Claude Code 起動**後**、毎セッション（resume 含む） |
| 実行対象 | クラウドセッションのみ | ローカル + クラウド両方 |
| キャッシュ | あり（約 7 日、FS スナップショット） | なし（毎回実行 → 起動レイテンシ増） |
| 制約 | 終了コード 0 必須 / 約 5 分以内 | タイムアウト既定 600 秒 |

**使い分けの指針**:

- **VM 自体のプロビジョニング**（プリインストールされていないツールチェーン。
  例: .NET SDK、`gh` CLI、`apt install`）→ セットアップスクリプトが本来の場所。
  ただし共通化できないため、**組織共有環境**が使えないなら
  「README に手順を書いて各自に設定してもらう」しかない。
- **プロジェクトのセットアップ**（`npm install`、`pip install`、DB 起動、環境変数の
  注入）→ **SessionStart hook に寄せるべき**。リポジトリで共通化でき、ローカルにも効く。

`CLAUDE_CODE_REMOTE` 環境変数（クラウドで `"true"`、ローカルでは決して `"true"` に
ならない）で分岐すれば、クラウド専用処理も安全に書けます。
`$CLAUDE_ENV_FILE` に `export` 行を追記すれば、以降の全 Bash コマンドに環境変数を
渡せるため、**環境変数ボックスの代替にもなります**（シークレット以外）。

このリポジトリの `.claude/hooks/session-start.sh` が実装例です。ローカル / クラウド
両モードで実行し、終了コード 0・妥当な JSON 出力・`CLAUDE_ENV_FILE` への書き込みを
確認済みです。

---

## 3. リポジトリ側から「環境そのもの」を指定できるか

部分的に可能です。設定キー `remote.defaultEnvironmentId` が存在します。

- Anthropic ホスト環境の ID（`env_...`）は**通常の設定precedenceに従う**ため、
  リポジトリの `.claude/settings.json` に書けば、各自が `/remote-env` で選んだ
  ユーザー設定を**上書きできます**。
- ただし効くのは **CLI 由来のクラウドセッション**（`claude --cloud`）です。
  Web UI / モバイル / デスクトップから開始する場合はセレクタの選択が使われ、
  未選択時に効くのは「組織のデフォルト環境」（管理者設定）です。
- セルフホスト環境の ID（`ccpool_...`）は**ユーザー設定・managed 設定・`--settings`
  フラグからのみ**honorされ、リポジトリの project / local 設定に書くと警告付きで
  無視されます（チェックインしたファイルで勝手にセルフホストへ誘導させない安全策）。

さらに、**ネットワーク許可ドメインには組織レベルの一括配布が存在しません**。
公式ドキュメントに明記があります: 「各環境が独自の allowed-domains リストを持ち、
管理者が全メンバーの環境にプッシュできる組織レベルの allowlist は無い。
サーバー管理設定はクラウドセッション内でも効くが、環境のネットワーク allowlist に
ドメインを追加するものは一つも無い。」

→ **許可ドメインを共通化する唯一の方法は「組織共有環境」を使うこと**です。

---

## 4. 組織アカウント（Team / Enterprise）で使える追加手段

こちらが「個人プランでは塞げない穴」に対する答えです。

### 4-1. 組織共有環境（Organization-shared environments）★最重要

- Team / Enterprise の **Owner / Admin** が作成でき、**組織の全メンバーの環境
  セレクタに出現**します。
- 共有できるのは **名前・ネットワークアクセスレベル・環境変数（.env 形式）・
  セットアップスクリプト** — つまり**個人プランで共通化できなかった 3 要素すべて**。
- 管理画面: `claude.ai/admin-settings` の **Cloud environments** ページ。
- **組織のデフォルト環境**は別途 `claude.ai/admin-settings/claude-code` で指定。
  これを設定すると、メンバーが環境を選んでいない場合の既定として効きます。
- 注意: 共有環境も**シークレットストアではありません**。値は全メンバーが読めます。
- 共有環境はメンバーの個人環境を**置き換えるのではなく追加**されます
  （個人環境を作る自由は残る＝強制力は無い）。

### 4-2. サーバー管理設定（Server-managed settings）

- Team / Enterprise 限定。`claude.ai/admin-settings/claude-code` → Managed settings。
- **クラウドセッションにも届きます**（MDM 由来の設定は届かないのと対照的）。
  公式に「Claude Code on the web を使う組織はサーバー管理設定も構成すべき」と明記。
- `settings.json` のほぼ全キーが使え、**最高優先度**（CLI 引数でも上書き不可）。
- 特に有用な managed 専用キー:
  - `claudeMd` — **組織全体に CLAUDE.md 相当の指示を注入**
  - `allowManagedPermissionRulesOnly` — ユーザー / プロジェクト設定の権限ルールを無効化
  - `allowedMcpServers` / `deniedMcpServers` / `allowManagedMcpServersOnly` — MCP の許可制御
  - `strictKnownMarketplaces` / `disableSideloadFlags` — プラグイン供給元の制限
  - `forceRemoteSettingsRefresh` — 取得失敗時に起動させない fail-closed 運用
  - `hooks` — 組織全体に hook を強制（監査スクリプト等）
- 制約: **組織内で一律**（グループ別設定は未対応）。`managed-mcp.json` は配布不可。
  `policyHelper` など OS ポリシー限定キーは無効。
- セキュリティ上の位置づけ: クライアントサイド制御であり、**セキュリティ境界ではない**
  （管理外端末では回避可能）。

### 4-3. セルフホスト環境（Self-hosted environments）

- Team / Enterprise の**パブリックベータ**、既定で無効。
  `claude.ai/admin-settings/cloud-environments` で **Allow self-hosted environments** を有効化。
- 自社インフラ上の **runner** がセッションを実行。**runner イメージを組織が管理する**ため、
  ツールチェーン・内部 CLI・社内 CA・`~/.claude/` のシードまで完全に統制できます。
- ネットワークも自社境界内 → 社内レジストリ・DB・内部 Git ホストに到達可能。
  許可ドメインの問題が構造的に消えます。
- 制約: ZDR 有効組織は不可、推論は Anthropic API 固定（Bedrock 等へ迂回不可）、
  Claude Tag / Code Review はまだ非対応。運用負荷は自社持ち。
- 補足: セルフホストでは runner イメージ内の managed-settings ファイルも読まれますが、
  **サーバー管理設定が 1 つでもキーを配信している場合はそちらが優先**されます。

### 4-4. その他の組織向けレバー

- **GitHub Enterprise Server** 対応（Team / Enterprise のみ）。
- **Quick web setup（`/web-setup`）の無効化** — Owner が
  `claude.ai/admin-settings/claude-code` でトグル可能。
- **`allow_remote_sessions` ポリシー** — クラウドセッション自体の有効 / 無効。
- **監査ログ** — 設定変更の監査イベントを compliance API / エクスポートで取得可能。
- **Claude Tag（Slack）** — チャンネルセッションは**共有環境のみ**を使う。
- **プラグインマーケットプレイス** — 組織用マーケットプレイスを立て、
  リポジトリの `extraKnownMarketplaces` + `enabledPlugins`、または managed 設定の
  `strictKnownMarketplaces` で配布・制限。

---

## 5. 推奨アーキテクチャ

### 個人プラン（現状）でできる最善

1. **共通化できるものは全部リポジトリへ**
   `CLAUDE.md` / `.claude/rules/` / `.claude/settings.json` / `.claude/hooks/` /
   `.claude/skills/` / `.claude/agents/` / `.claude/commands/` / `.mcp.json`
2. **セットアップスクリプトの中身を SessionStart hook に移植**
   `CLAUDE_CODE_REMOTE` で分岐し、`$CLAUDE_ENV_FILE` で環境変数を注入。
   → 残るのは「pre-install されていないツールチェーンの導入」だけ。
3. **残った個人設定は README 化**
   許可ドメイン一覧と、どうしても必要なセットアップスクリプトの内容を
   リポジトリに文書として置き、各メンバーが自分の環境にコピペできるようにする。
   （プログラム的な強制はできないため、手順書化が唯一の手段）
4. **`.claude/settings.local.json` は各自の個人差分**（自動的に gitignore される）。

### Team / Enterprise へ移行した場合

1. **組織共有環境**を 1 つ作り、セットアップスクリプト・環境変数・許可ドメインを集約。
2. それを**組織のデフォルト環境**に指定（`claude.ai/admin-settings/claude-code`）。
3. **サーバー管理設定**で組織ポリシー（`claudeMd`、権限 deny、MCP 許可制、
   プラグイン供給元制限）を強制。
4. リポジトリ側は引き続き**プロジェクト固有**の設定のみを持つ（責務分離）。
5. 社内リソースへの到達が必要なら**セルフホスト環境**を検討。

### 責務の分離（推奨）

| レイヤー | 担当 | 置き場所 |
| --- | --- | --- |
| 組織ポリシー（強制） | Owner / Admin | サーバー管理設定 |
| 実行基盤（ツール・NW・環境変数） | Owner / Admin | 組織共有環境 / セルフホスト runner イメージ |
| プロジェクト設定 | リポジトリ管理者 | リポジトリの `.claude/` |
| 個人の好み | 各開発者 | `~/.claude/`（ローカルのみ）/ `.claude/settings.local.json` |

---

## 6. 検証手順（このリポジトリで再現するには）

1. このブランチを default ブランチにマージする。
2. **新しい**クラウドセッションを開始する（既存セッションでは反映されない）。
3. セッション冒頭に SessionStart hook の `additionalContext`
   （"Repository bootstrap complete. / Surface: cloud ..."）が入ることを確認。
4. `echo $PROJECT_ROOT` を実行し、`$CLAUDE_ENV_FILE` 経由の環境変数が
   効いていることを確認。
5. `/status` で読み込まれた設定ソースを確認。

---

## 7. 出典

- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments)
- [Configure server-managed settings](https://code.claude.com/docs/en/server-managed-settings)
- [Settings reference](https://code.claude.com/docs/en/settings)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Self-hosted environments](https://code.claude.com/docs/en/self-hosted-environments)
- [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
