# REST `repos/**` 解除手順（クラスB の解消）

対象: Claude Code on the Web のセッションで `gh api repos/{owner}/{repo}/...` が
`GitHub access is not enabled for this session. An org admin must connect the Claude GitHub App
for this organization.` で 403 になる状態。

背景と根拠は [`gh-proxy-investigation.md`](./gh-proxy-investigation.md) を参照。
**GraphQL 制限（クラスD）はこの手順では解除されない。** 解除されるのは REST のみ。

## 前提の確認

解除前の状態を記録しておく:

```bash
./scripts/verify-gh-proxy.sh
```

期待される未解除時の出力: `[2]` が全て **クラスB**、終了コード 1。

`[2]` が既に HTTP 200 なら解除済みなので、この手順は不要。
`[2]` が **クラスA**（`sessions are bound to their configured repositories`）だった場合は
原因が別（リポジトリが session に attach されていない）なので、この手順では解決しない。

## 手順（GitHub 側での操作）

1. https://github.com/apps/claude を開く
2. **Install**（既に導入済みなら **Configure**）を選択
3. インストール先アカウントとして対象の owner を選ぶ
   - 個人リポジトリなら自分のアカウント。403 の文面は "organization" と言うが、
     personal account でも同じゲートが掛かる
4. リポジトリの範囲を選ぶ
   - **All repositories**、または **Only select repositories** で対象リポジトリを明示的に追加
   - 既に導入済みの場合、**対象リポジトリがリストに含まれているか**を必ず確認する。
     App がアカウントに入っていても、当該リポジトリが選択されていなければゲートは開かない
5. **Install** / **Save** で確定

### 代替経路

claude.ai の onboarding をやり直し、GitHub 連携を **GitHub App** 認可で行っても同じ結果になる。
`/web-setup`（`gh` トークン同期）経路は App のインストールを伴わないため、
このゲートの解消には**ならない可能性がある**。

## 手順（解除後の検証）

セッションの GitHub credential はセッション開始時に払い出されるため、
**App を入れた後は新しいセッションで確認する**のが確実。
403 の文面が "not enabled for **this session**" と言っている点がその根拠。

```bash
# gh はプリインストールされていないので必要なら入れる
command -v gh >/dev/null || sudo apt-get install -y gh

./scripts/verify-gh-proxy.sh
```

### 解除成功時に期待される出力

```
[2] REST repos/** ← 今回解除を狙っている対象
  repos/<owner>/<repo>                       HTTP 200  -
  repos/<owner>/<repo>/issues                HTTP 200  -
  repos/<owner>/<repo>/labels                HTTP 200  -
  repos/<owner>/<repo>/pulls                 HTTP 200  -
...
=== 判定 ===
  ✅ REST repos/** が開通した。
```

`[3]`（`user/repos` 等）と `[4]`（GraphQL）は**解除後も 403 のままが正常**。
これらは App の有無とは無関係な恒久制限。

## 解除後にできるようになること / ならないこと

| 操作 | 解除後 |
|---|---|
| `gh api repos/{o}/{r}` | ✅ |
| `gh api repos/{o}/{r}/issues`（一覧・作成・更新） | ✅ |
| `gh api repos/{o}/{r}/labels` | ✅ |
| `gh api repos/{o}/{r}/pulls` | ✅ |
| `gh issue list` / `gh pr list` / `gh repo view` / `gh label list` | ❌ GraphQL 依存のまま |
| `gh auth status` | ❌ 常に invalid と誤報（GraphQL で疎通確認するため） |
| Projects v2 | ❌ GraphQL 専用 API |

`gh` の**サブコマンド**ではなく `gh api` の **REST 呼び出し**に書き換える必要がある、というのが要点。

## `gh` をセッションごとに入れ直さない方法

`gh` はプリインストールされていないため、環境の **setup script** に追記しておくと
毎セッションで自動的に入る（claude.ai の Cloud environments 設定）:

```bash
sudo apt-get install -y gh
```
