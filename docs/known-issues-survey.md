# 既知問題の調査結果

調査日: 2026-08-11
対象症状: Claude Code on the Web のセッションで `api.github.com/repos/{owner}/{repo}/...` が
403（`GitHub access is not enabled for this session. An org admin must connect the Claude GitHub App
for this organization.`）になる。`git` / `raw` / `codeload` / `/user` は正常。

前提の実測は [`gh-command-verification.md`](./gh-command-verification.md)、
アーキテクチャ調査は [`gh-proxy-investigation.md`](./gh-proxy-investigation.md)。

## 結論

**既知問題である。** ただし報告状況は良くない:

- **同系統の Open な issue が存在する**（#76248）。公式回答は付いていない
- **類似報告は多数あるが、大半が `duplicate` / `not planned` でクローズ**されており、修正されていない
- **本件と完全に一致する変種の報告は見つからなかった**（後述の差分）
- **未試行の公式手順が1つ見つかった** — claude.ai 側の「リンク」操作（後述）

## 最も近い既知 issue

### #76248 — 本件と同系統（Open・公式回答なし）

[Cloud/Cowork sessions: git proxy now blocks all pushes — "not in this session's authorized
repository set"; PAT pass-through no longer works (CCR_TEST_GITPROXY rollout?)](https://github.com/anthropics/claude-code/issues/76248)

一致点が多い:

| 項目 | #76248 | 本件 |
|---|---|---|
| `api.github.com` の REST が proxy に遮断される | ✅ | ✅ |
| `documentation_url` が `claude-code/github-actions` | ✅ | ✅ |
| 環境変数 `CCR_TEST_GITPROXY=1` | ✅ | ✅ |
| 自前 PAT でも回避不可 | ✅ | ✅（ドキュメント記載とも一致） |
| サーバ側ロールアウトによる回帰 | 2026-07-10 に突然発生 | 不明 |

報告されている REST のエラー:

```json
{"message":"GitHub access to this repository is not enabled for this session.
 Use add_repo to request access.","documentation_url":"https://docs.anthropic.com/en/docs/claude-code/github-actions"}
```

**ステータス: Open。公式回答・回避策なし。**

#### 本件との差分（重要）

| | #76248 | 本件 |
|---|---|---|
| `git push` | **失敗**する | **成功**する |
| 403 の文面 | `... to this repository ... Use add_repo to request access.` | `... An org admin must connect the Claude GitHub App for this organization.` |
| 環境 | Cowork desktop | Web セッション（staging 混在） |

**403 の文面が別の分岐**であり、`git` が生きている点も異なる。
つまり同じゲート機構の別ブランチを踏んでいる。**本件の変種そのものは未報告。**

## 「個人アカウント + App 導入済みでも見えない」系統（多数・ほぼ未修正）

本件のアカウントは**個人アカウント**（`M.E (Sut103)` / "Your personal account"）であり、
この系統に強く一致する。

| Issue | 内容 | ステータス |
|---|---|---|
| [#68517](https://github.com/anthropics/claude-code/issues/68517) | App を **All repositories** で導入済みなのに個人の private repo にアクセス不可。報告者は「backend indexing/sync issue」と結論 | **Closed（duplicate）** |
| [#65601](https://github.com/anthropics/claude-code/issues/65601) | App を All repositories で導入済みなのに個人 repo が `claude.ai/code` の picker に出ない（"No repos match."）。他 owner の repo は出る | **Closed（not planned / duplicate）** |
| [#18467](https://github.com/anthropics/claude-code/issues/18467) | 個人アカウントの repo が Claude web で見えず、org の repo だけ動く | — |
| [#70474](https://github.com/anthropics/claude-code/issues/70474) | CCR routine セッションが内部 proxy 経由で GitHub に到達できない。有効なトークンでも repo アクセス段階で 403/404 | **Closed（not planned）** |

#68517 が挙げる重複先: #33875, #12839, #18467, #27155。
#65601 が挙げる重複先: #57396, #57161, #60493, #27155, #40238。

**同一の根本原因（個人アカウントの App インストールがバックエンドに反映されない）が
繰り返し報告され、いずれも修正されずクローズされている。**

#70474 の報告者の結論は本件の実測と完全に符合する:

> Since the identical token worked every time when tested from outside the sandbox, I believe
> the sandbox's network egress/credential-handling for GitHub is broken or misconfigured,
> independent of whatever token is supplied.

## 仕様として確定しているもの（バグではない）

| Issue / Doc | 内容 | ステータス |
|---|---|---|
| [#57641](https://github.com/anthropics/claude-code/issues/57641) | cloud セッションは **App がインストールされた repo しか**アクセスできない。public repo を user OAuth で読めるようにする要望 | **Closed（not planned）** |
| 公式ドキュメント | GraphQL は pinned な PR-review 操作のみ。**供給する資格情報に関係なく**適用される | 仕様 |

→ **GraphQL 制限（クラスD）は既知の仕様であり、issue を立てる対象ではない。**

#57641 の記述は本件の前提確認としても有用:

> Claude Code on the web (cloud sessions) currently injects only the first-party GitHub MCP,
> and that integration authenticates through the Claude GitHub App. The App must be installed
> on each account or organization whose repositories you want to use — even for public,
> open-access repositories.

## 別原因として除外できたもの

| Issue | 内容 | 本件との差 |
|---|---|---|
| [#36363](https://github.com/anthropics/claude-code/issues/36363) | sandbox proxy の TLS MITM で `gh`（Go バイナリ）が証明書検証に失敗 | 本件は `SSL_CERT_FILE` 設定済みで **TLS は成功**。403 は TLS 後のレイヤ |
| [#61189](https://github.com/anthropics/claude-code/issues/61189) | proxy の OAuth トークンに `workflow` スコープが無く `.github/workflows/` を push 不可 | 本件は push 自体が成功 |
| [#30318](https://github.com/anthropics/claude-code/issues/30318) | 地域制限・VPN 環境で Anthropic API が 403 | 本件は Anthropic API は正常 |
| [#80874](https://github.com/anthropics/claude-code/issues/80874) | GitHub Integration connector で読みは通るが write が `403 Resource not accessible by integration` | 本件は**読みも 403**、かつ文面が別 |

## 未試行の公式手順（最有力の残り手段）

公式ドキュメント [Configure GitHub access](https://claude.com/docs/claude-tag/admins/configure-github)
に、**GitHub 側の App インストールとは別の「Claude 側のリンク」手順**が記載されている。
このページは Claude Code と共有である旨が明記されている:

> Open [`claude.ai/admin-settings/github`](https://claude.ai/admin-settings/github).
> **This page is shared with Claude Code; one connection serves both products.**

> After authorizing, the page shows two sections: **Connected GitHub accounts** lists
> organizations already linked, and **Unlinked accounts** lists organizations where
> **the Claude GitHub App is installed but not yet linked.**

> If your organization is under **Unlinked accounts**, click **Link** next to it.

**「App はインストール済みだがリンクされていない」という状態が公式に定義されており、
本件の 403 文面（"An org admin must connect the Claude GitHub App"）と正確に対応する。**

同ページのトラブルシュート表も 403 の一次切り分けとしてこの確認を挙げている:

> When Claude replies ... or reports that GitHub returned a `403`, check the two levels in order.
> | The GitHub organization that owns the repository shows **Connected** under
> **Connected GitHub accounts** | `claude.ai/admin-settings/github` |

`Needs permissions` 表示の場合はインストールが承認待ちで、**Review permissions** から
github.com 側で承認する必要があるとも記載されている。

### 留保

- このドキュメントは Claude Tag の管理者向けページであり、**個人アカウント（Pro/Max）で
  `admin-settings` が利用できるかは未確認**。検索結果には
  `claude.ai/admin-settings/claude-code/github` という異なるパスの言及もあった
- リンク操作が本件の 403 を解消するかは**未検証**。文面の対応関係から有力と判断しているだけで、
  確定ではない（一度「App インストールで解決する」と誤診しているため、同じ轍を踏まないよう明記する）

## 推奨アクション

1. **`claude.ai/admin-settings/github` を開き、`Sut103` が Unlinked accounts に居ないか確認する。**
   居れば **Link**、`Needs permissions` なら **Review permissions**。
   その後 **新しいセッション**で `scripts/verify-gh-proxy.sh` を実行して判定する
2. 既に `Connected` だった場合、本件は「個人アカウント + App 導入済みでも
   バックエンドが認識しない」既知系統（#68517 / #65601 / #18467 / #70474）に該当する。
   これらは修正されずクローズされているため、**Open な #76248 に本件の変種として情報を追記する**か、
   新規 issue を立てるのが妥当。報告内容は
   [`gh-rest-unblock-runbook.md`](./gh-rest-unblock-runbook.md) のテンプレートを使う
3. **GraphQL 制限については報告不要**（仕様として確定）

## 出典

- [#76248 Cloud/Cowork sessions: git proxy now blocks all pushes (CCR_TEST_GITPROXY rollout?)](https://github.com/anthropics/claude-code/issues/76248) — Open
- [#70474 CCR routine sessions can't reach GitHub — broken internal proxy](https://github.com/anthropics/claude-code/issues/70474) — Closed (not planned)
- [#68517 Claude can't access a private personal GitHub repo despite App full access](https://github.com/anthropics/claude-code/issues/68517) — Closed (duplicate)
- [#65601 Personal GitHub repo never appears in claude.ai/code repo picker](https://github.com/anthropics/claude-code/issues/65601) — Closed (not planned)
- [#18467 Personal account repositories not visible in Claude web](https://github.com/anthropics/claude-code/issues/18467)
- [#57641 Allow read access to public GitHub repositories via user OAuth](https://github.com/anthropics/claude-code/issues/57641) — Closed (not planned)
- [#80874 GitHub Integration connector: write operations fail with 403](https://github.com/anthropics/claude-code/issues/80874)
- [#61189 git push and GitHub MCP refuse changes under .github/workflows/](https://github.com/anthropics/claude-code/issues/61189)
- [#36363 Sandbox network proxy causes TLS failures for gh CLI](https://github.com/anthropics/claude-code/issues/36363)
- [#72856 Claude GitHub integration needs org-installation-only mode](https://github.com/anthropics/claude-code/issues/72856)
- [Configure GitHub access（Claude Tag admins・Claude Code と共有）](https://claude.com/docs/claude-tag/admins/configure-github)
- [Configure cloud environments — GitHub proxy / GraphQL restrictions](https://code.claude.com/docs/en/cloud-environments)
- [Use Claude Code on the web — Security and isolation](https://code.claude.com/docs/en/claude-code-on-the-web)
