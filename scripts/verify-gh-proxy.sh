#!/usr/bin/env bash
# GitHub proxy の許可範囲を判定する。
#
# Claude Code on the Web のセッション内で実行する。Claude GitHub App の接続前後で
# 走らせて差分を見る用途。詳細な背景は docs/gh-proxy-investigation.md を参照。
#
#   usage: scripts/verify-gh-proxy.sh [owner/repo]
#
# 終了コード: 0 = REST の repos/** が開通, 1 = まだ塞がれている

set -uo pipefail

REPO="${1:-Sut103/claude-playground}"
API="https://api.github.com"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 403 の文面から拒否クラス（docs/gh-proxy-investigation.md §4）を判定する
classify() {
  case "$1" in
    *"sessions are bound to their configured repositories"*) echo "クラスA: 非リポジトリスコープのパス禁止" ;;
    # 文面は App 接続を要求するが実態を指していない。App を All repositories で導入済みでも
    # この 403 は出る（docs/gh-rest-unblock-runbook.md 参照）。
    *"An org admin must connect the Claude GitHub App"*)     echo "クラスB: repos/** 拒否（文面はApp未接続だが実態は別）" ;;
    *"not permitted through this proxy"*)                    echo "クラスC: 恒久禁止パス" ;;
    *"GraphQL"*"not enabled for this session"*)              echo "クラスD: GraphQL 制限（仕様・解除不可）" ;;
    "") echo "-" ;;
    *) echo "その他: $(printf '%s' "$1" | head -c 60)" ;;
  esac
}

probe() {
  local label="$1" path="$2"
  local code
  code=$(curl -sS -o "$TMP/body" -w '%{http_code}' \
    -H "Authorization: Bearer ${GH_TOKEN:-}" \
    -H 'Accept: application/vnd.github+json' \
    "$API/$path" 2>/dev/null)
  local msg
  msg=$(python3 -c "
import json,sys
try:
    d=json.load(open('$TMP/body'))
    print(d.get('message','') if isinstance(d,dict) else '')
except Exception:
    print('')
" 2>/dev/null)
  printf '  %-42s HTTP %-4s %s\n' "$label" "$code" "$(classify "$msg")"
  [ "$code" = "200" ]
}

echo "=== GitHub proxy 検証: $REPO / $(date -u +%FT%TZ) ==="
echo
echo "[0] 環境"
printf '  %-42s %s\n' "GH_TOKEN" "${GH_TOKEN:-(未設定)}"
printf '  %-42s %s\n' "HTTPS_PROXY" "${HTTPS_PROXY:-(未設定)}"
printf '  %-42s %s\n' "gh" "$(command -v gh >/dev/null 2>&1 && gh --version | head -1 || echo '未インストール')"
echo "  api.github.com の TLS 発行者:"
echo | openssl s_client -connect api.github.com:443 -servername api.github.com 2>/dev/null \
  | openssl x509 -noout -issuer 2>/dev/null | sed 's/^/    /'

echo
echo "[1] 常に通るはずの識別系エンドポイント"
probe "user"       "user"       || true
probe "rate_limit" "rate_limit" || true

echo
echo "[2] REST repos/** ← 今回解除を狙っている対象"
rest_ok=0
probe "repos/$REPO"        "repos/$REPO"        && rest_ok=1
probe "repos/$REPO/issues" "repos/$REPO/issues" || true
probe "repos/$REPO/labels" "repos/$REPO/labels" || true
probe "repos/$REPO/pulls"  "repos/$REPO/pulls"  || true

echo
echo "[3] 恒久的に塞がれている想定のもの（対照群）"
probe "user/repos"              "user/repos"              || true
probe "installation/repositories" "installation/repositories" || true

echo
echo "[4] GraphQL（仕様上解除不可）"
gql_code=$(curl -sS -o "$TMP/g" -w '%{http_code}' -X POST \
  -H "Authorization: Bearer ${GH_TOKEN:-}" -H 'Content-Type: application/json' \
  -d '{"query":"{viewer{login}}"}' "$API/graphql" 2>/dev/null)
gql_msg=$(python3 -c "
import json
try: print(json.load(open('$TMP/g')).get('message',''))
except Exception: print('')
" 2>/dev/null)
printf '  %-42s HTTP %-4s %s\n' "POST /graphql" "$gql_code" "$(classify "$gql_msg")"

if command -v gh >/dev/null 2>&1; then
  echo
  echo "[5] gh サブコマンド実測"
  for c in "api user --jq .login" "api repos/$REPO --jq .full_name" \
           "issue list -R $REPO -L 1" "pr list -R $REPO -L 1"; do
    printf '  %-42s ' "gh $c"
    if out=$(eval "gh $c" 2>&1); then
      printf 'OK   %s\n' "$(printf '%s' "$out" | head -1 | head -c 40)"
    else
      printf 'FAIL %s\n' "$(classify "$out")"
    fi
  done

  # gh auth status は GraphQL で疎通確認するため、トークンが有効でも「invalid」と報告し、
  # かつ終了コード 0 を返す。出力の文面で判定する。
  printf '  %-42s ' "gh auth status"
  auth_out=$(gh auth status 2>&1)
  case "$auth_out" in
    *"invalid"*|*"Failed to log in"*) echo "FAIL 誤報（GraphQL 疎通確認のため必ず invalid になる）" ;;
    *) echo "OK   $(printf '%s' "$auth_out" | tr '\n' ' ' | head -c 40)" ;;
  esac
fi

echo
echo "=== 判定 ==="
if [ "$rest_ok" = "1" ]; then
  echo "  ✅ REST repos/** が開通した。gh api repos/{owner}/{repo}/... が利用可能。"
  echo "     GraphQL 依存のサブコマンド（gh issue list 等）は引き続き不可。"
  exit 0
else
  echo "  ❌ REST repos/** は依然 403。"
  echo "     Claude GitHub App の導入では解消しないことが確認済み。"
  echo "     docs/gh-rest-unblock-runbook.md の報告手順を参照。"
  exit 1
fi
