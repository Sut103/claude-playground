# REST `repos/**` 403 の切り分け結果と報告手順

> **重要な訂正**: 本ドキュメントは当初「Claude GitHub App の未接続が原因」という仮説に基づく
> 解除手順書だった。**この仮説は検証により否定された。** App は導入済みでも 403 は解消しない。
> 以下は確定した切り分け結果と、プラットフォーム側への報告手順に差し替えたもの。

対象の症状: Claude Code on the Web のセッション内で `gh api repos/{owner}/{repo}/...` および
同等の `curl` が以下で 403 になる。

```
GitHub access is not enabled for this session.
An org admin must connect the Claude GitHub App for this organization.
```

背景となるアーキテクチャ調査は [`gh-proxy-investigation.md`](./gh-proxy-investigation.md)、
最初の実測は [`gh-command-verification.md`](./gh-command-verification.md) を参照。

## 結論

GitHub 側の App 設定・Claude 側の資格情報はいずれも正常で、
**VM 内から出る経路に限って `repos/**` REST が拒否されている。**

> **更新**: 当初ここに「ユーザー側で解除する手段は無い」と書いたが、
> 既知問題調査で**未試行の公式手順が1つ見つかった** —
> claude.ai 側の「リンク」操作（`claude.ai/admin-settings/github` の **Unlinked accounts** → **Link**）。
> GitHub 側の App インストールとは別の手順で、本件の 403 文面と正確に対応する。
> **まずこれを試す。** 詳細は [`known-issues-survey.md`](./known-issues-survey.md) を参照。

それでも解消しない場合は、公式ドキュメントの記述と矛盾する状態であるため
**プラットフォーム側の不具合または staging 環境の設定漏れ**として報告するのが妥当。
同系統の Open な issue として
[#76248](https://github.com/anthropics/claude-code/issues/76248) がある。

### 403 のエラーメッセージは実態を指していない

文面は "An org admin must connect the Claude GitHub App" と言うが、
**App が All repositories で導入済み・issues 書き込み権限付きでも 403 のまま**だった。
この文言を信じて App 設定を追いかけると時間を失う。**汎用のフォールバック文言として扱うべき。**

## 確定した切り分け表

| 層 | 経路 | 結果 | 判定 |
|---|---|---|---|
| GitHub 側の権限 | Claude GitHub App（`github.com/apps/claude`） | All repositories / `Read and write: issues, pull requests, code, ...` | ✅ 正常 |
| Claude 側の資格情報 | 内蔵 GitHub ツール → `repos/{o}/{r}/contents/README.md` | **成功**（ファイル取得） | ✅ 正常 |
| セッションのリポジトリスコープ | JWT クレーム `sources` | `['Sut103/claude-playground']` | ✅ 正常 |
| git 経路 | JWT クレーム `ccr:git_via_engine: true` / `git ls-remote` `fetch` `push` | すべて成功 | ✅ 正常 |
| 静的コンテンツ経路 | `raw.githubusercontent.com` / `codeload.github.com` | 200 / 200 | ✅ 正常 |
| API 識別系 | `api.github.com/user`, `/rate_limit` | 200 / 200 | ✅ 正常 |
| **API リポジトリ系** | **VM 内 `gh` / `curl` → `api.github.com/repos/**`** | **403** | ❌ **ここだけ壊れている** |

**同一の REST パスを内蔵ツールは読めて VM 内の `gh`/`curl` は読めない。**
したがって原因はアカウント権限ではなく、**呼び出し元による経路の差**にある。

### 内蔵ツールとの比較についての留保

公式ドキュメントは内蔵 GitHub ツールと `gh` が「同じ GitHub proxy」を通ると記述している。
ただし内蔵ツールの応答は `[Resource from github at repo://...]` という形で返り、
**VM 外（Anthropic ホスト側）で取得されている可能性が高い**。
その場合「同じプロキシ」は資格情報の扱いを指し、ネットワーク経路は別物である。
この点は VM 内からは確認できないため、**未確定**として扱う。

いずれにせよ運用上の結論は変わらない: **VM 内の `gh` からは `repos/**` に到達できない。**

## ドキュメントとの矛盾（報告の根拠）

公式ドキュメント [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) は
`gh` の利用を明示的に想定している:

> GitHub's `gh` CLI isn't pre-installed. If you need a `gh` command the built-in tools don't
> cover, **like `gh release` or `gh workflow run`, install and authenticate it yourself.**

> If you set neither and the GitHub proxy is handling authentication for your session, both
> variables read as the placeholder string `proxy-injected` ... **`gh` works without a token
> of your own.**

`gh release` / `gh workflow run` はいずれも `repos/{owner}/{repo}/...` REST を叩く。
**ドキュメントが動くと明言している操作が動かない。** これは仕様ではなく不具合である。

さらに GraphQL 制限の 403 は代替として REST を案内する:

> ... **Use REST via `gh api repos/{owner}/{repo}/...` instead.**

**案内された代替手段そのものが塞がっている**という自己矛盾した状態になっている。

## 本セッションが staging である点

原因候補として最有力。以下は VM 内からの実測値:

```
/root/.ccr/agent-proxy-ca.crt  subject = CN = CCR Upstream Proxy CA (staging), O = Anthropic
環境変数                        CCR_TEST_GITPROXY=1
ca-bundle.crt 内               sandbox-egress-gateway-staging / sandbox-egress-staging TLS Inspection CA
                               （production 版も同梱）
api.github.com の TLS 発行者    O = Anthropic, CN = Egress Gateway SDS Issuing CA (production)
```

**staging のアップストリームプロキシと production の Egress Gateway が混在している。**
staging 側が本番のアカウント連携情報（App インストール記録）を保持していない場合、
今回の症状と整合する。

## 残っている確認手段

### 1. 新しいセッションで再検証

```bash
command -v gh >/dev/null || sudo apt-get install -y gh
./scripts/verify-gh-proxy.sh
```

`[2]` が 200 になれば本セッション固有（staging 環境固有）の問題と確定する。
403 のままなら恒常的な不具合。

判定に使う環境差分:

```bash
openssl x509 -in /root/.ccr/agent-proxy-ca.crt -noout -subject   # staging か production か
env | grep -i ccr_test                                            # CCR_TEST_GITPROXY の有無
```

### 2. Anthropic サポートへの報告

`/root/.ccr/README.md` が指示する経路:

> If a tool still cannot work through the proxy, **report it to your administrator or
> Anthropic support** so the policy or tooling can be fixed.

> do not retry organization policy denials (403/407) — **report them instead.**

報告に含めるべき内容:

- 症状: VM 内の `gh` / `curl` から `api.github.com/repos/{owner}/{repo}` 系がすべて 403。
  文面は `GitHub access is not enabled for this session. An org admin must connect the
  Claude GitHub App for this organization.`
- Claude GitHub App は対象アカウントに **All repositories** で導入済み、
  権限に `Read and write access to ... issues, pull requests ...` を含む
- **内蔵 GitHub ツールは同じ REST パス（`repos/{o}/{r}/contents/README.md`）を取得できる**
- `git`（clone / fetch / push）、`raw.githubusercontent.com`、`codeload.github.com`、
  `api.github.com/user`、`/rate_limit` はいずれも正常
- 403 に GitHub 由来ヘッダ（`Server: github.com` / `X-Github-Request-Id` / `X-Ratelimit-*`）が無く、
  `curl $HTTPS_PROXY/__agentproxy/status` の `recentRelayFailures` も空
  → GitHub に到達せず上流で落とされている
- セッション ID: JWT クレームの `session_id`（例 `cse_...`）
- 環境が staging 混在（上記「本セッションが staging である点」の実測値）
- ドキュメントとの矛盾（上記「ドキュメントとの矛盾」の引用）

再現コマンドは [`../scripts/verify-gh-proxy.sh`](../scripts/verify-gh-proxy.sh) をそのまま添付できる。

## 解除できたとしても残る制約

仮に `repos/**` REST が開通しても、**GraphQL 制限（クラスD）は仕様として残る。**

| 操作 | REST 開通後 |
|---|---|
| `gh api repos/{o}/{r}/issues` 等の REST | ✅ |
| `gh issue list` / `gh pr list` / `gh repo view` / `gh label list` / `gh release list` | ❌ GraphQL 依存 |
| `gh auth status` | ❌ 常に invalid と誤報 |
| Projects v2 | ❌ GraphQL 専用 API |

CCPM を動かすには **REST 呼び出しへの書き換えが別途必要**。この結論は変わらない。
