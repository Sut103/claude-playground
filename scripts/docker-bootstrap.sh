#!/usr/bin/env bash
# Bring up the Docker daemon inside a Claude Code on the web session.
#
# The session runs in a Firecracker microVM as root with (almost) full
# capabilities, and dockerd/containerd/runc are pre-installed — but nothing
# starts the daemon, because there is no init system. This script does.
#
# Idempotent: safe to run on every session start and any number of times after.
set -euo pipefail

CA_SRC="${CCR_CA_BUNDLE:-/root/.ccr/ca-bundle.crt}"
DOCKERD_LOG="${DOCKERD_LOG:-/var/log/dockerd.log}"
READY_TIMEOUT="${READY_TIMEOUT:-60}"

log() { printf '[docker-bootstrap] %s\n' "$*"; }

if ! command -v dockerd >/dev/null 2>&1; then
  log "dockerd not present in this image; nothing to do."
  exit 0
fi

# ---------------------------------------------------------------------------
# Daemon config.
#
# Deliberately NO "proxies" block. The session's HTTPS_PROXY points at a
# loopback agent proxy whose port changes over the life of a session; baking
# that port into daemon.json makes every pull fail with "proxyconnect ...
# connection refused" as soon as it moves. Registry traffic egresses fine
# without it — the transparent egress gateway handles the policy, and its CA is
# already in the VM's system trust store.
# ---------------------------------------------------------------------------
install -d /etc/docker
if [ ! -f /etc/docker/daemon.json ]; then
  cat > /etc/docker/daemon.json <<'JSON'
{
  "storage-driver": "overlay2",
  "features": { "buildkit": true },
  "log-level": "info"
}
JSON
  log "wrote /etc/docker/daemon.json"
fi

# ---------------------------------------------------------------------------
# Start dockerd detached.
#
# setsid matters: a plain background job stays in the tool call's process
# group, so the daemon is killed the moment that call is interrupted or ends.
# ---------------------------------------------------------------------------
if docker info >/dev/null 2>&1; then
  log "daemon already running (v$(docker version --format '{{.Server.Version}}'))"
else
  log "starting dockerd ..."
  setsid dockerd >>"$DOCKERD_LOG" 2>&1 </dev/null &
  disown || true

  for _ in $(seq 1 "$READY_TIMEOUT"); do
    docker info >/dev/null 2>&1 && break
    sleep 1
  done

  if ! docker info >/dev/null 2>&1; then
    log "ERROR: dockerd did not become ready in ${READY_TIMEOUT}s. Last log lines:"
    tail -n 20 "$DOCKERD_LOG" >&2 || true
    exit 1
  fi
  log "daemon ready (v$(docker version --format '{{.Server.Version}}'))"
fi

# ---------------------------------------------------------------------------
# Stage the egress-proxy CA for build contexts.
#
# Egress TLS is re-terminated by the gateway. The VM trusts it, but a fresh
# container does not, so any in-container HTTPS (pip, npm, curl, cargo, go)
# fails with "certificate verify failed" until this bundle is installed in the
# image. Copy it next to each Dockerfile that needs it, and COPY it in.
# ---------------------------------------------------------------------------
if [ -r "$CA_SRC" ]; then
  while IFS= read -r ctx; do
    cp -f "$CA_SRC" "$ctx/ca-bundle.crt"
    log "staged CA bundle -> $ctx/ca-bundle.crt"
  done < <(find . -name Dockerfile -not -path './.git/*' -printf '%h\n' 2>/dev/null | sort -u)
else
  log "note: no CA bundle at $CA_SRC (in-container HTTPS may fail cert verification)"
fi

log "done."
