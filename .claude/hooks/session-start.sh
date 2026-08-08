#!/bin/bash
# SessionStart hook: make Docker usable in Claude Code on the web.
#
# The web session's microVM ships the Docker binaries but no init system, so
# nothing starts dockerd. This hook starts it and stages the egress-proxy CA
# into every build context, then warms the image cache.
set -euo pipefail

# Local sessions typically have their own Docker Desktop / daemon already.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

bash scripts/docker-bootstrap.sh

# Pre-pull the base images this repo builds on. The container snapshot is
# cached after the hook finishes, so later sessions start with a warm
# /var/lib/docker instead of re-pulling.
for img in python:3.12-slim postgres:16-alpine redis:7-alpine; do
  docker image inspect "$img" >/dev/null 2>&1 && continue
  echo "[session-start] pre-pulling $img"
  docker pull --quiet "$img" >/dev/null || echo "[session-start] warning: pull failed for $img"
done

echo "[session-start] Docker ready: $(docker version --format '{{.Server.Version}}')"
