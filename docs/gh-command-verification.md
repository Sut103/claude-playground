# `gh` コマンド検証レポート（Claude Code on the Web）

検証日: 2026-08-11 / 環境: Claude Code on the Web (remote container, Ubuntu 24.04)
制約: **MCP による代替は一切行わない**（`gh` / `curl` / `git` のみで検証）

## 結論

「`gh` コマンドが通らない」は**結論としては正しいが、理由が通説と違う**。

- `gh` は**未インストール**だが、`apt-get install gh` で**普通に入る**（Ubuntu universe に 2.45.0 がある）
- 認証は**壊れていない**。`GH_TOKEN` は本物の GitHub App installation token に proxy 側で差し替えられ、`gh api user` は **成功する**
- 真の原因は**エグレス proxy の API パス allowlist**。`repos/**` と GraphQL がブロックされる
- したがって**インストールしても実用的な `gh` サブコマンドは全滅**。gh のバージョンを上げても変わらない
- 一方で **`git` は完全に動く**（別の認証経路）

つまり「gh がない/認証がない」ではなく「**api.github.com のリポジトリ操作が proxy で塞がれている**」が本質。

## 各レイヤの検証結果

### 1. バイナリの有無

```
which gh / command -v gh / type gh  → すべて not found
/usr/bin/gh, /usr/local/bin/gh, /opt/gh → 存在しない
```

しかし apt には存在する:

```
$ apt-cache policy gh
  Candidate: 2.45.0-1ubuntu0.3   (noble-updates/universe)
$ apt-get install -y gh          → 成功
$ gh --version                   → gh version 2.45.0
```

**「gh が使えない」の一次要因は単なる未インストール。これは除去可能。**

### 2. 認証（ここが通説と最も違う）

```
GH_TOKEN=proxy-injected...
GITHUB_TOKEN=proxy-injected...
```

値は**プレースホルダ**で、実際の credential は `HTTPS_PROXY=http://127.0.0.1:44233` が注入する。

```
$ curl -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user
HTTP 200  → {"login": "Sut103", "id": 18696845, ...}

$ gh api user --jq .login
Sut103
```

レスポンスヘッダから注入されるトークンの正体が判明:

```
X-Oauth-Client-Id: Iv23liqTIFEtdIu6Vn1r
X-Ratelimit-Limit: 15000          ← GitHub App installation token の値
X-Github-Request-Id: 7C00:2A0644:...
Server: github.com
```

**認証は正常。GitHub App も接続済み。** Authorization ヘッダを外すと 403 になるので、
proxy はヘッダの存在を見て本物の credential に差し替えている。

### 3. REST API のパス allowlist

| パス | 結果 | メッセージ |
|---|---|---|
| `user` | **200** | — |
| `rate_limit` | **200** | — |
| `repos/Sut103/claude-playground` | 403 | GitHub access is not enabled for this session... |
| `repos/Sut103/claude-playground/issues` | 403 | 同上 |
| `repos/Sut103/claude-playground/labels` | 403 | 同上 |
| `repos/Sut103/claude-playground/pulls` | 403 | 同上 |
| `user/repos` | 403 | This GitHub API path is not available: sessions are bound to their configured repositories |
| `meta`, `octocat` | 403 | 同上 |

#### この 403 は GitHub ではなく proxy が生成している（重要）

成功した `/user` と、ブロックされた `repos/...` のヘッダを比較:

```
/user (200)            → Server: github.com, X-Github-Request-Id: ..., X-Ratelimit-*: ...  すべて有り
repos/... (403)        → Content-Type のみ。GitHub 由来ヘッダが一切無い
```

**`repos/**` へのリクエストは GitHub に到達していない。** proxy が手前で落としている。
エラー文の "An org admin must connect the Claude GitHub App" は**ミスリード**で、
実際には App は接続済み（§2 参照）。実体は proxy のパス制限。

なお owner の大文字小文字（`Sut103` / `sut103`）は無関係、両方 403。
`add_repo` を `access: "push"` で呼んでも `already_present` で状況は変わらなかった。

### 4. GraphQL は pinned set 以外すべて拒否

```
$ curl -X POST -d '{"query":"{viewer{login}}"}' https://api.github.com/graphql
HTTP 403
{"message":"This GraphQL query is not enabled for this session — only the pinned set
 of PR-review operations is served. Use REST via `gh api repos/{owner}/{repo}/...` instead."}
```

これが `gh auth status` が「トークンが無効」と誤報する原因:

```
$ GH_DEBUG=api gh auth status
* Request to https://api.github.com/graphql
> POST /graphql HTTP/1.1
> Authorization: token ████████
< HTTP/1.1 403 Forbidden
```

`gh auth status` は GraphQL で疎通確認するため、**REST が通る状況でも必ず「invalid」になる**。
CCPM のように preflight で `gh auth status` を見て中断する実装は、ここで必ず落ちる。

### 5. サブコマンド実測マトリクス

`R=Sut103/claude-playground`

| コマンド | 結果 | 失敗の層 |
|---|---|---|
| `gh api user` | **OK** | — |
| `gh auth status` | FAIL | GraphQL 403 |
| `gh api repos/$R` | FAIL | REST allowlist |
| `gh api repos/$R/issues` | FAIL | REST allowlist |
| `gh issue list` | FAIL | GraphQL 403 |
| `gh issue status` | FAIL | GraphQL 403 |
| `gh pr list` | FAIL | GraphQL 403 (`PullRequestList`) |
| `gh repo view` | FAIL | GraphQL 403 |
| `gh label list` | FAIL | GraphQL 403 |
| `gh release list` | FAIL | GraphQL 403 |
| `gh run list` | FAIL | REST allowlist |

実用上は `gh api user` / `gh api rate_limit` のみが生存。

### 6. gh のバージョンは無関係

公式リリースの gh 2.62.0 を取得して再検証（ダウンロード自体は HTTP 200 で成功）:

| コマンド | 2.45.0 | 2.62.0 |
|---|---|---|
| `gh api user` | OK | OK |
| `gh auth status` | FAIL | FAIL |
| `gh issue list` | FAIL | FAIL |
| `gh label list` | FAIL | FAIL |

新しい gh では一部サブコマンドが GraphQL から REST に移行しているが、
**REST の `repos/**` も塞がれているため救済にならない**。

### 7. `git` は完全に動作する

```
$ git ls-remote origin        → exit 0、全 ref を取得
$ git fetch origin main       → exit 0
```

git は api.github.com ではなく git proxy 経由で、別の credential 経路を使う。
`GIT_CONFIG_*` により `git@github.com:` → `https://github.com/` の書き換えも自動で入る。

**したがって「commit / push / branch 運用」は完全に可能。塞がれているのは Issue/PR のメタデータ操作だけ。**

## CCPM への含意

CCPM は Issue を単一の情報源として扱い、`gh issue create/edit/list`、sub-issue、
ラベル運用に依存する。上記の通りそれらは**すべて** proxy 層で 403 になるため、
`gh` をインストールしても CCPM のワークフローは成立しない。

障害の所在を正確に言うと:

1. ❌ `gh` が無いから → **違う**（インストール可能）
2. ❌ 認証されていないから → **違う**（GitHub App token が注入され `gh api user` は 200）
3. ❌ gh が古いから → **違う**（2.62 でも同じ）
4. ❌ ネットワークが無いから → **違う**（api.github.com に到達、github.com からファイル取得も可）
5. ✅ **エグレス proxy が `repos/**` REST と非 pinned GraphQL を拒否しているから**

これは session の egress policy 側の設定であり、コンテナ内の操作では回避できない
（README も「403/407 は回避せず報告せよ」と明示）。解消するには環境の
GitHub API 許可範囲を広げる必要がある。

## 再現用スニペット

```bash
# 1. インストールできることの確認
apt-get install -y gh && gh --version

# 2. 認証が生きていることの確認（200 が返る）
gh api user --jq .login
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user

# 3. repos/** が proxy で落ちることの確認（GitHub 由来ヘッダが無い 403）
curl -sS -D - -o /dev/null \
  -H "Authorization: Bearer $GH_TOKEN" \
  https://api.github.com/repos/Sut103/claude-playground

# 4. GraphQL が拒否されることの確認
curl -sS -X POST -H "Authorization: Bearer $GH_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"query":"{viewer{login}}"}' https://api.github.com/graphql

# 5. auth status が GraphQL で落ちていることの確認
GH_DEBUG=api gh auth status

# 6. git は動くことの確認
git ls-remote origin | head
```
