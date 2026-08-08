#!/bin/bash
# Repository-common session bootstrap for Claude Code.
#
# Registered in .claude/settings.json (SessionStart). Because it lives in the
# repo, every collaborator gets it automatically - unlike the cloud environment
# "Setup script", which is configured per user at claude.ai/code.
#
# Runs on both local and cloud sessions. Guard cloud-only work with
# CLAUDE_CODE_REMOTE, which the cloud VM sets to "true" and is never "true"
# locally.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

notes=()

# --- Cloud-only dependency installation -------------------------------------
# The cloud VM is a fresh Ubuntu 24.04 machine with common toolchains already
# present, but project dependencies are not installed. Keep this idempotent:
# the hook runs on every startup AND resume.
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  if [ -f package.json ] && [ ! -d node_modules ]; then
    npm install --no-audit --no-fund || notes+=("npm install failed")
  fi
  if [ -f requirements.txt ]; then
    pip install --quiet -r requirements.txt || notes+=("pip install failed")
  fi
  if [ -f Gemfile ]; then
    bundle install --quiet || notes+=("bundle install failed")
  fi
fi

# --- Session-scoped environment variables -----------------------------------
# Anything appended to $CLAUDE_ENV_FILE is exported for every subsequent Bash
# command in the session. This is the repo-committed equivalent of the cloud
# environment's per-user "Environment variables" box.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo 'export PROJECT_ROOT="'"$PROJECT_DIR"'"'
    echo 'export LANG=C.UTF-8'
  } >> "$CLAUDE_ENV_FILE"
fi

# --- Context injection ------------------------------------------------------
# stdout of a SessionStart hook is added to the conversation before the first
# prompt. Emitting JSON lets us set additionalContext explicitly.
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
surface="local"
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && surface="cloud (Claude Code on the web)"

context="Repository bootstrap complete.
- Surface: ${surface}
- Branch: ${branch}
- Config source: repository-committed .claude/ (shared by all collaborators)"

if [ ${#notes[@]} -gt 0 ]; then
  context="${context}
- Warnings: ${notes[*]}"
fi

jq -n --arg ctx "$context" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'

exit 0
