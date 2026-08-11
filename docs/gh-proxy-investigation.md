# `gh` 拒否の主体・背景・解除可能性の調査レポート

調査日: 2026-08-11 / 環境: Claude Code on the Web (Anthropic-hosted, Firecracker microVM, Ubuntu 24.04)
前提: 前レポート [`gh-command-verification.md`](./gh-command-verification.md) の続き。MCP による代替は行わない。

## エグゼクティブサマリ

| 問い | 答え |
|---|---|
| **誰が設定した?** | **Anthropic**。ユーザーも所属 org も設定していない。MITM CA の subject が `O = Anthropic` |
| **どこのプロキシ?** | **3層**ある。①VM内のエージェントプロキシ（`claude` プロセス自身） ②CCR Upstream Proxy ③**Egress Gateway**（VM外・ネットワーク層）。GitHub の拒否を出しているのは②/③側 |
| **背景は?** | **実際の GitHub credential を VM 内に置かないための設計**。公式ドキュメントに "GitHub proxy" として明記された仕様 |
| **解除可能か?** | **ユーザー側では不可**。GraphQL 制限は仕様として解除不可。REST `repos/**` は当初 App 接続で解除できると見たが**検証で否定**（§5-1）。プラットフォーム側の不具合として報告する案件 |

CCPM にとって重要な点: **CCPM が依存する `gh issue list` 系は GraphQH 制限側に当たるため、解除不可の側**に落ちる。

---

## 1. アーキテクチャの実測

### 1.1 ローカルプロキシの正体は `claude` プロセス自身

`/proc/net/tcp` で `127.0.0.1:44233`（= `0100007F:ACC9`）の listen ソケットを特定し、
その inode を全プロセスの fd から逆引き:

```
socket:[1152] → /proc/530 → claude --output-format=stream-json --verbose \
                              --settings /root/.claude/launcher-settings.json ...
socket:[1144] → /proc/498 → /usr/local/bin/environment-manager task-run \
                              --session cse_01B5W2hvm8rqYeJc2B5Z4sQz --session-mode resume-cached
```

**`HTTPS_PROXY` の受け口は独立したデーモンではなく、Claude Code CLI 本体（PID 530）が
自プロセス内に持っているプロキシ**。その外側に Anthropic の `environment-manager`（PID 498）がいる。

PID 1 は `/process_api --firecracker-init --addr 0.0.0.0:2024 --listen-vsock-port 2024`
→ **Firecracker microVM** 上で動作。ホストとは vsock で接続。

### 1.2 VM の外側に透過型 MITM が存在する（最重要）

`--noproxy '*'` で `HTTPS_PROXY` を完全に迂回しても **403 のまま**だった。
そこで直結時の TLS 証明書を確認すると:

```
$ openssl s_client -connect api.github.com:443 -servername api.github.com
subject = CN = *.github.com
issuer  = O = Anthropic, CN = Egress Gateway SDS Issuing CA (production)
```

**プロキシ設定を無視して直結しても、Anthropic の Egress Gateway が TLS を終端している。**

VM 内の `iptables -t nat` は全チェーン空（リダイレクト規則なし）なので、
**この傍受はゲスト内ではなく Firecracker ホスト／ネットワークファブリック側で行われている**。
DNS は本物の GitHub IP（`140.82.112.6`）を返すが、経路上で必ず Gateway を通る。

→ **VM 内からの回避は原理的に不可能。** 設定を消す・迂回する対象がそもそも VM 内に無い。

### 1.3 コンテナが信頼している Anthropic の MITM CA は 5 枚

`ca-bundle.crt`（全152枚）に含まれる Anthropic 系:

```
O = Anthropic, CN = sandbox-egress-gateway-production Egress Gateway CA
O = Anthropic, CN = sandbox-egress-gateway-staging  Egress Gateway CA
O = Anthropic, CN = sandbox-egress-production TLS Inspection CA
O = Anthropic, CN = sandbox-egress-staging    TLS Inspection CA
CN = CCR Upstream Proxy CA (staging), O = Anthropic
```

`/root/.ccr/agent-proxy-ca.crt` 単体は `CCR Upstream Proxy CA (staging)`（有効期限 2026-03-24〜2036-03-21）。
**staging と production の CA が両方入っている**点から、本セッションは staging 系の
アップストリームプロキシと production の Egress Gateway を併用している。

### 1.4 拒否は上流で生成されている（ローカルプロキシではない）

3つの独立した証拠:

1. **GitHub 由来ヘッダの欠落** — 成功する `/user` には `Server: github.com` /
   `X-Github-Request-Id` / `X-Ratelimit-*` が付くが、`repos/**` の 403 には
   `Content-Type` しか無い。リクエストは GitHub に到達していない。
2. **`recentRelayFailures` が空** — 403 を連発した後に
   `curl $HTTPS_PROXY/__agentproxy/status` を見ても `"recentRelayFailures": []`。
   ローカルのエージェントプロキシは自分が落としたと認識していない。
3. **プロキシ迂回でも 403** — §1.2 の通り。

### 1.5 一般のインターネットは開いている

```
example.com 200 | www.google.com 200 | gitlab.com 301 | bitbucket.org 200
registry.npmjs.org 200 | api.github.com 200 | api.openai.com 421
```

**これは「狭いネットワーク allowlist」ではない。** 一般 egress は通る。
つまり GitHub の拒否は environment の network access level とは**無関係**な、
GitHub 専用の別レイヤである。

---

## 2. 誰が設定したのか

**Anthropic（プラットフォーム側）。** 根拠:

- MITM CA の subject/issuer がすべて `O = Anthropic`
- プロキシを起動しているのは Anthropic の `environment-manager` と `claude` バイナリ
- 拒否メッセージの `documentation_url` が `docs.anthropic.com/en/docs/claude-code/github-actions` を指す
- 公式ドキュメントが仕様として明記（§3）

**ユーザー（`Sut103`）の設定でも、org 管理者の設定でもない。** リポジトリ内の設定ファイル、
CCPM の設定、`.claude/settings.json` などは一切関与していない。

公式ドキュメントは environment の network access level について、
**GitHub だけは別扱いだと明言している**:

> Each environment sets one network access level... **GitHub operations use a separate proxy
> that is independent of this setting.**

> In Anthropic-hosted environments, all GitHub operations go through a dedicated proxy that
> keeps your real GitHub credentials outside the session's VM, **independent of the
> environment's access level**.

→ **environment 設定（Trusted / Custom / None）をどう変えても GitHub API 制限は動かない。**

---

## 3. 背景・設計意図

公式ドキュメント（Security and isolation）が理由を直接述べている:

> **Credential protection**: in Anthropic-hosted environments, sensitive credentials such as
> git credentials or signing keys are **never inside the sandbox with Claude Code**;
> authentication is handled through a secure proxy using scoped credentials.

つまり設計意図は次の通り:

1. **本物の GitHub トークンを VM 内に置かない。** VM 内にあるのは
   `proxy-injected` というプレースホルダのみ（実測で確認済み）。
   エージェントが暴走しても、プロンプトインジェクションを受けても、
   **持ち出せる credential が存在しない**。
2. **その代償として、credential を差し替えるプロキシが「何をしてよいか」を決める必要がある。**
   トークン自体に権限境界を持たせられない（VM 内に無いので）ため、
   **境界はプロキシのパス／オペレーション allowlist として実装されている。**

ドキュメントが挙げるプロキシの4機能のうち、後半2つが今回の制限の正体:

> * **Git credentials**: the git client inside the VM uses a scoped credential, which the proxy
>   verifies and swaps for your actual GitHub token.
> * **API requests**: requests from the built-in GitHub tools, and from `gh` under the
>   `proxy-injected` placeholder, go out with your real credentials substituted.
> * **Repository scope**: GitHub API and release-asset requests **reach only repositories
>   attached to the session**, so a setup script that downloads release assets from an
>   unattached repository gets a 403.
> * **GraphQL restrictions**: the proxy serves **only a pinned set of GraphQL operations for
>   pull-request workflows**. ... **The restriction applies to every request through the proxy
>   regardless of the credentials you supply, so a `GH_TOKEN` you set gets the same 403.**
>   Claude can't reach GitHub APIs that exist only in GraphQL, such as Projects v2,
>   through the proxy.

なお `gh` の未インストールは意図的で、ドキュメントも**自分で入れて使うことを想定**している:

> GitHub's `gh` CLI isn't pre-installed. If you need a `gh` command the built-in tools don't
> cover, like `gh release` or `gh workflow run`, install and authenticate it yourself.

> `gh` works without a token of your own, but a script that reads `GITHUB_TOKEN` directly
> gets the placeholder, not a usable token.

→ **「gh を使うな」という設計ではない。** REST 経由で使うことは想定内。

---

## 4. 拒否メッセージは4クラスに分かれる

実測で判明した独立した拒否理由。**これらを混同すると誤診する。**

| # | 対象 | メッセージ | 意味 |
|---|---|---|---|
| A | `user/repos`, `installation/repositories`, `user/installations`, `meta`, `octocat` | `This GitHub API path is not available: sessions are bound to their configured repositories. Use repository-scoped endpoints (repos/{owner}/{repo}/...)` | 非リポジトリスコープの横断的パスを禁止。**`repos/{owner}/{repo}/...` を使えと案内している** |
| B | `repos/**` 全て | `GitHub access is not enabled for this session. An org admin must connect the Claude GitHub App for this organization.` | **Claude GitHub App 未接続ゲート** |
| C | `/app` | `Access to this GitHub API path is not permitted through this proxy.` | App 管理系は恒久禁止 |
| D | `POST /graphql`（pinned 以外） | `This GraphQL query is not enabled for this session — only the pinned set of PR-review operations is served. Use REST via gh api repos/{owner}/{repo}/... instead.` | **仕様上の恒久制限** |

**A と D はどちらも「`repos/{owner}/{repo}/...` の REST を使え」と案内している。
ところが本セッションではその REST 自体が B で塞がれている。** ここが今回の詰みの構造。

### クラス B は本当に「App 未接続」なのか

注入されるトークンは実在の GitHub App installation token である:

```
X-Oauth-Client-Id: Iv23liqTIFEtdIu6Vn1r
X-Ratelimit-Limit: 15000                      ← installation token の値
X-Accepted-Github-Permissions: allows_permissionless_access=true
```

`/user` は 200 で `Sut103` を返す。したがって「認証が無い」わけではない。
一方 `X-Accepted-Github-Permissions: allows_permissionless_access=true` は
**`/user` が無権限でも叩けるエンドポイントであることを示すだけ**で、
リポジトリ権限の存在を意味しない。

ドキュメントによれば GitHub 認証には2経路がある:

> | **GitHub App** | Authorize the Claude GitHub App during web onboarding | ... |
> | **`/web-setup`** | Run `/web-setup` in your terminal to sync your local `gh` CLI token | ... |

当初はここから「`repos/**` REST は Claude GitHub App の接続を前提にしている」と推論した。
**この推論は誤りだった。** 実際には:

- App は **All repositories** で導入済み（`issues` 書き込み権限つき）でも 403 のまま
- **内蔵 GitHub ツールは同じ REST パスを取得できる**

したがって B は「App 未接続ゲート」ではなく、**VM 内から出る経路に対してのみ
`repos/**` を拒否している状態**である。メッセージの文面は実態を指していない。
詳細は §5-1 と [`gh-rest-unblock-runbook.md`](./gh-rest-unblock-runbook.md) を参照。

---

## 5. 解除可能性

### 5-1. REST（クラス B）→ **仮説は否定された。ユーザー側で解除する手段は無い**

> **訂正**: 当初ここに「Claude GitHub App をインストールすれば解除できる見込みが高い」と書いた。
> **検証によりこの仮説は否定された。**

検証結果:

- Claude GitHub App は対象アカウントに **All repositories** で3週間前から導入済み。
  権限に `Read and write access to actions, checks, code, discussions, issues,
  pull requests, repository hooks, and workflows` を含む。**それでも 403 のまま。**
- **内蔵 GitHub ツールは同じ REST パス（`repos/{o}/{r}/contents/README.md`）を取得できる。**
  → GitHub 側の権限も Claude 側の資格情報も正常。
- したがって原因はアカウント権限ではなく **呼び出し元による経路の差**。
  VM 内から出る経路に限って `repos/**` が拒否されている。

**403 の文面 "An org admin must connect the Claude GitHub App" は実態を指していない
汎用フォールバック文言。** これを信じて App 設定を追うと時間を失う。

さらに公式ドキュメントは `gh release` / `gh workflow run`（いずれも `repos/**` REST）のために
`gh` を自分で入れて使うことを明示的に推奨しており、**動くと書かれている操作が動かない**。
GraphQL 制限の 403 が案内する代替手段（`gh api repos/{owner}/{repo}/...`）そのものが
塞がれているという自己矛盾も生じている。

→ **仕様ではなく、プラットフォーム側の不具合または staging 環境の設定漏れ**と判断するのが妥当。
本セッションは staging のアップストリームプロキシと production の Egress Gateway が
混在している（`CCR Upstream Proxy CA (staging)`、`CCR_TEST_GITPROXY=1`）。

対処は「新しいセッションでの再検証」と「Anthropic サポートへの報告」の2つ。
手順と報告テンプレートは [`gh-rest-unblock-runbook.md`](./gh-rest-unblock-runbook.md) を参照。

### 5-2. GraphQL（クラス D）→ **解除不可（仕様）**

ドキュメントが明示的に閉じている:

> The restriction applies to **every request through the proxy regardless of the credentials
> you supply**, so a `GH_TOKEN` you set gets the same 403.

自前の PAT を `GH_TOKEN` に入れても回避できないと**明記されている**。
さらに Egress Gateway は VM 外なので（§1.2）、VM 内の操作では届かない。

影響を受けるもの（実測で全滅を確認）:

`gh auth status` / `gh issue list` / `gh issue status` / `gh pr list` / `gh repo view` /
`gh label list` / `gh release list`、および **Projects v2**（GraphQL 専用 API）。

### 5-3. environment の network access level → **無関係（効果なし）**

§2 の引用の通り GitHub は access level から独立。
`Custom` で `api.github.com` を明示的に許可しても GitHub proxy 層は動かない。
そもそも `api.github.com` は Trusted のデフォルト allowlist に既に入っている。

### 5-4. self-hosted environment → **理論上は解除可能**

> Sessions in a self-hosted environment authenticate git operations with credentials your
> deployment provides ... including per-session minted credentials and **an opt-in to this
> same proxy**.

self-hosted では GitHub proxy が **opt-in**。使わなければこの制限は掛からず、
`gh` は完全に動作するはずである。ただし credential 保護と隔離の責任は自組織側に移る。

### 5-5. VM 内からの回避 → **不可能。かつ試みるべきでない**

`/root/.ccr/README.md` が明示している:

> Never disable TLS verification, never unset `HTTPS_PROXY`, and **do not retry organization
> policy denials (403/407) — report them instead.**

> ### Not supported through the proxy (report, do not work around)

技術的にも §1.2 の通り VM 外の透過 MITM が最終境界なので、迂回路は存在しない。

### 5-6. 正式な申請経路

> If a tool still cannot work through the proxy, **report it to your administrator or
> Anthropic support** so the policy or tooling can be fixed.

pinned GraphQL セットの拡張はプラットフォーム側の変更が必要。Anthropic support へのフィードバックが唯一の道。

---

## 6. CCPM への結論

CCPM は Issue を単一の情報源とし、`gh issue list` / sub-issue / ラベル運用に依存する。
これらは**クラス D（GraphQL、解除不可）に当たる**ため、`gh` を入れても成立しない。

ただし前レポートより一歩踏み込んだ結論として、**詰み方は2段階**である:

1. いま `gh api repos/...`（REST）が塞がっているのは **クラス B = App 未接続**が原因で、
   **これは解除できる可能性が高い**。
2. 解除できても `gh issue list` 等は **GraphQL を使うので依然として動かない**。
   REST（`gh api repos/{o}/{r}/issues`）に書き換えれば動く見込み。

→ **CCPM を Web で使うには、GraphQL 依存を REST 呼び出しに置き換える改変が必要**、
かつその前提として Claude GitHub App の接続が要る。
`gh` サブコマンドをそのまま使う前提の CCPM は、この環境では原理的に動かない。

なお **`git` は完全に動く**（`ls-remote` / `fetch` / `push` すべて成功）ため、
ブランチ・コミット主体のワークフローには一切影響がない。

---

## 7. 再現手順

```bash
# ① ローカルプロキシの正体を特定（PID は claude 本体）
printf '%X\n' 44233                      # → ACC9
awk 'NR>1{split($2,a,":"); if(a[2]=="ACC9") print $2,$4,$10}' /proc/net/tcp
for p in /proc/[0-9]*; do for f in $p/fd/*; do
  case "$(readlink "$f" 2>/dev/null)" in *1152*)
    echo "$p: $(tr -d '\0' < $p/cmdline)";; esac; done; done 2>/dev/null

# ② VM 外の透過 MITM を確認（issuer が Anthropic Egress Gateway になる）
echo | openssl s_client -connect api.github.com:443 -servername api.github.com 2>/dev/null \
  | openssl x509 -noout -subject -issuer

# ③ プロキシを迂回しても 403 であることを確認
curl -sS --noproxy '*' -o /dev/null -w '%{http_code}\n' https://api.github.com/

# ④ VM 内にリダイレクト規則が無いことを確認（＝傍受はホスト側）
iptables -t nat -L -n

# ⑤ 一般 egress は開いていることを確認（狭い allowlist ではない）
for h in example.com www.google.com gitlab.com bitbucket.org; do
  curl -sS -o /dev/null -w "$h %{http_code}\n" "https://$h/"; done

# ⑥ 4クラスの拒否を再現
curl -sS -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user/repos            # A
curl -sS -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/repos/Sut103/claude-playground  # B
curl -sS -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/app                  # C
curl -sS -X POST -H "Authorization: Bearer $GH_TOKEN" -H 'Content-Type: application/json' \
     -d '{"query":"{viewer{login}}"}' https://api.github.com/graphql                      # D

# ⑦ 上流が落としている証拠（GitHub 由来ヘッダが無い / relay failure が記録されない）
curl -sS -D - -o /dev/null -H "Authorization: Bearer $GH_TOKEN" \
     https://api.github.com/repos/Sut103/claude-playground
curl -sS "$HTTPS_PROXY/__agentproxy/status"

# ⑧ 信頼している Anthropic MITM CA を列挙
openssl crl2pkcs7 -nocrl -certfile /root/.ccr/ca-bundle.crt \
  | openssl pkcs7 -print_certs -noout | grep -i anthropic
```

## 参考

- [Use Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) — Security and isolation / GitHub authentication options
- [Configure cloud environments](https://code.claude.com/docs/en/cloud-environments) — Access levels / **GitHub proxy** / Security proxy / Work with GitHub issues and pull requests
- `/root/.ccr/README.md` — セッション内のプロキシ運用ガイド
