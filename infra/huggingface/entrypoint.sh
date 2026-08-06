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

# Real Pub/Sub-based decoupling of negotiation execution (worker +
# standalone Compliance and Verification Agent services) -- off by
# default, same as AUTH_REQUIRED. Only started if PACT_DISTRIBUTED=true
# and real GCP credentials for Pub/Sub/Firestore are present;
# internal-only, like the vendor services above (see docs/ARCHITECTURE.md).
if [ "${PACT_DISTRIBUTED:-false}" = "true" ]; then
  uvicorn pact.services.compliance_agent.app:app --host 127.0.0.1 --port 9101 &
  uvicorn pact.services.verification_agent.app:app --host 127.0.0.1 --port 9102 &
  for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:9101/.well-known/agent.json >/dev/null 2>&1 \
       && curl -sf http://127.0.0.1:9102/.well-known/agent.json >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
  python -m pact.worker.negotiation_worker &
fi

exec uvicorn pact.main:app --host 0.0.0.0 --port "${PORT:-7860}"
