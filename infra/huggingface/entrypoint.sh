#!/bin/sh
# Starts the two vendor services in the background (internal-only --
# never exposed outside this container), waits for them to be ready,
# then runs pact-core in the foreground on the public port. pact-core
# also serves the built frontend as static files (see pact/main.py).
set -e

cd /app/backend

uvicorn vendors.aws_vendor.app:app --host 127.0.0.1 --port 9001 &
uvicorn vendors.azure_vendor.app:app --host 127.0.0.1 --port 9002 &

for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:9001/.well-known/agent.json >/dev/null 2>&1 \
     && curl -sf http://127.0.0.1:9002/.well-known/agent.json >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

exec uvicorn pact.main:app --host 0.0.0.0 --port "${PORT:-7860}"
