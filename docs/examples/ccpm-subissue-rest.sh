#!/usr/bin/env bash
# ============================================================================
# ccpm-subissue-rest.sh
#
# CCPM の `gh sub-issue` 依存を置き換えるための REST 実装。
#
# 設計方針:
#   - GraphQL を一切使わない
#   - gh の高レベルサブコマンド（gh issue list / gh repo view など）も使わない
#     ※ これらは内部で GraphQL を叩くため、Claude Code cloud セッションの
#       GitHub プロキシに 403 で弾かれる（検証済み）
#   - 使うのは `gh api` の REST パスのみ
#   → ローカルでもクラウドセッションでも同一コードで動く
#
# 前提:
#   - gh がインストール済み（クラウドは setup script で `apt install -y gh`）
#   - repo スコープの REST が到達可能であること
#     クラウドセッションでは Claude GitHub App が org に接続されている必要がある。
#     未接続だと `repos/{owner}/{repo}/...` が 403 になる（docs/ccpm-addendum.md 3.7）
#
# 使い方:
#   ./ccpm-subissue-rest.sh check                  到達性の事前チェック
#   ./ccpm-subissue-rest.sh add    <親#> <子#>      子を親の sub-issue にする
#   ./ccpm-subissue-rest.sh remove <親#> <子#>      解除する
#   ./ccpm-subissue-rest.sh list   <親#>            sub-issue を一覧する
#   ./ccpm-subissue-rest.sh id     <#>              issue number → issue id
#   ./ccpm-subissue-rest.sh experiment              親子 Issue を作って紐づけ検証
#
# 環境変数:
#   CCPM_REPO   owner/repo を明示指定（省略時は origin から導出）
# ============================================================================

set -euo pipefail

# --- リポジトリの解決 -------------------------------------------------------
# `gh repo view` は GraphQL を使うので避け、git remote から導出する
resolve_repo() {
  if [[ -n "${CCPM_REPO:-}" ]]; then
    printf '%s\n' "$CCPM_REPO"
    return
  fi
  local url
  url=$(git remote get-url origin)
  sed -E 's#^(git@|ssh://git@|https://)([^:/]+)[:/]##; s#\.git$##' <<<"$url"
}

REPO="$(resolve_repo)"

api() { gh api -H "Accept: application/vnd.github+json" "$@"; }

# --- issue number -> issue id ----------------------------------------------
# sub-issues API は number ではなく内部 id を要求する
issue_id() {
  api "repos/${REPO}/issues/$1" --jq '.id'
}

# --- 操作 -------------------------------------------------------------------
cmd_add() {
  local parent="$1" child="$2" child_id
  child_id="$(issue_id "$child")"
  api --method POST "repos/${REPO}/issues/${parent}/sub_issues" \
      -F "sub_issue_id=${child_id}" --jq '"linked #\(.number) under #'"${parent}"'"'
}

cmd_remove() {
  local parent="$1" child="$2" child_id
  child_id="$(issue_id "$child")"
  api --method DELETE "repos/${REPO}/issues/${parent}/sub_issue" \
      -F "sub_issue_id=${child_id}" --jq '"unlinked #\(.number)"'
}

cmd_list() {
  api "repos/${REPO}/issues/$1/sub_issues" \
      --jq '.[] | "#\(.number)  [\(.state)]  \(.title)"'
}

# --- 到達性チェック ---------------------------------------------------------
# どの層で詰まっているかを切り分ける
cmd_check() {
  echo "repo: ${REPO}"
  printf '%-42s' "gh installed"
  command -v gh >/dev/null && gh --version | head -1 || { echo "MISSING"; return 1; }

  printf '%-42s' "REST user scope"
  if api user --jq '.login' 2>/dev/null; then :; else echo "FAIL"; fi

  printf '%-42s' "REST repo scope"
  if api "repos/${REPO}" --jq '.full_name' 2>&1 | head -1; then :; fi

  printf '%-42s' "REST sub_issues route"
  api "repos/${REPO}/issues/1/sub_issues" >/dev/null 2>&1 \
    && echo "reachable" \
    || echo "not reachable (Issue #1 が無いだけの 404 か、403 かを上の行で判断)"

  echo
  echo "repo scope が 403 の場合: Claude GitHub App を org に接続する"
  echo "  https://github.com/apps/claude"
}

# --- 実験 -------------------------------------------------------------------
# 親 Issue と子 Issue を作り、REST だけで親子リンクを張って確認する
cmd_experiment() {
  echo "== repo: ${REPO} =="

  echo "-- 親 Issue を作成"
  local parent
  parent=$(api --method POST "repos/${REPO}/issues" \
    -f title='[CCPM検証] 親 Epic' \
    -f body='REST のみで sub-issue を張れるかの検証用。検証後にクローズしてよい。' \
    --jq '.number')
  echo "   parent = #${parent}"

  echo "-- 子 Issue を作成"
  local child
  child=$(api --method POST "repos/${REPO}/issues" \
    -f title='[CCPM検証] 子タスク' \
    -f body='親 Epic の sub-issue になる想定。' \
    --jq '.number')
  echo "   child  = #${child}"

  echo "-- 子の内部 id を解決"
  local child_id
  child_id="$(issue_id "$child")"
  echo "   id     = ${child_id}"

  echo "-- REST で親子リンクを作成"
  api --method POST "repos/${REPO}/issues/${parent}/sub_issues" \
      -F "sub_issue_id=${child_id}" --jq '"   linked #\(.number)"'

  echo "-- 親から sub-issue 一覧を取得して確認"
  cmd_list "$parent"

  echo
  echo "成功。GraphQL を一切使わずに親子リンクが張れた。"
  echo "後片付け: gh api --method PATCH repos/${REPO}/issues/{${parent},${child}} -f state=closed"
}

# --- ディスパッチ -----------------------------------------------------------
case "${1:-}" in
  add)        shift; cmd_add "$@"        ;;
  remove)     shift; cmd_remove "$@"     ;;
  list)       shift; cmd_list "$@"       ;;
  id)         shift; issue_id "$@"       ;;
  check)      shift; cmd_check           ;;
  experiment) shift; cmd_experiment      ;;
  *)          sed -n '2,40p' "$0"; exit 1 ;;
esac
