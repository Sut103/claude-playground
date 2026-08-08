#!/bin/bash
# Claude Code on the web でセッションが始まるたびに走り、
# typecheck / lint / test / screenshot がすぐ実行できる状態を作る。
set -euo pipefail

# ローカルの CLI セッションでは何もしない（手元の環境を勝手に触らない）
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# コンテナには Chromium が同梱されているので、postinstall での再取得を止める。
# CLAUDE_ENV_FILE に書いた分はセッション中のシェルにも引き継がれる。
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1' >> "$CLAUDE_ENV_FILE"
  echo 'export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers' >> "$CLAUDE_ENV_FILE"
fi

echo "==> installing npm dependencies"
npm install --no-audit --no-fund

echo "==> ready: npm run verify / npm run dev / npm run screenshot"
