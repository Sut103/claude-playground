#!/usr/bin/env bash
# Smoke test for the Docker setup in a Claude Code on the web session.
# Exits non-zero on the first failure so it can gate other work.
set -uo pipefail

pass=0
fail=0

check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  ok   %s\n' "$name"; pass=$((pass + 1))
  else
    printf '  FAIL %s\n' "$name"; fail=$((fail + 1))
  fi
}

echo "docker smoke test"

check "dockerd responds"            docker info
check "can run a container"         docker run --rm alpine:3.20 true
check "can build an image"          bash -c 'echo -e "FROM alpine:3.20\nRUN true" | docker build -q -t smoke:build - '
check "container DNS resolves"      docker run --rm alpine:3.20 nslookup github.com
check "cgroup memory limit applies" bash -c '[ "$(docker run --rm --memory=64m alpine:3.20 cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || docker run --rm --memory=64m alpine:3.20 cat /sys/fs/cgroup/memory.max)" = "67108864" ]'

# In-container HTTPS only verifies once the egress-proxy CA is present.
if [ -r /root/.ccr/ca-bundle.crt ]; then
  check "in-container HTTPS verifies (with CA)" \
    docker run --rm -v /root/.ccr/ca-bundle.crt:/etc/ssl/certs/ca-certificates.crt:ro \
      alpine:3.20 wget -q -T 10 -O /dev/null https://pypi.org/
fi

echo "  --"
printf '  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
