#!/usr/bin/env bash
# Demo-day resilience: keeps the live container and ngrok tunnel up.
#
# This is operational tooling for the operator's machine during the
# live judged demo -- not part of the tested application, and not
# meant to run continuously in normal development. If the deploy
# container crashes, hangs, or stops responding, or the ngrok tunnel
# drops, this restarts the affected piece within CHECK_INTERVAL seconds
# instead of the public demo URL silently going dark.
#
# Usage: nohup ./infra/watchdog.sh > /tmp/pact-watchdog.log 2>&1 &
# Stop with: pkill -f infra/watchdog.sh
#
# Requires: a real GEMINI_API_KEY in backend/.env, the pact-deploy:latest
# image already built, and (optionally) a BigQuery read-only credential
# at $PACT_BQ_CREDENTIAL for the Observability dashboard -- see the
# README's Deployment section for what these are and why.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="pact-deploy:latest"
CONTAINER="pact-deploy-run"
PORT="${PACT_DEPLOY_PORT:-7860}"
CRED_MOUNT="${PACT_BQ_CREDENTIAL:-$HOME/.pact-secrets/pact-dashboard-reader-key.json}"
RUNTIME_ENV="/tmp/pact-deploy-runtime.env"
CHECK_INTERVAL="${PACT_WATCHDOG_INTERVAL:-30}"

log() { echo "$(date -u +%FT%TZ) $*"; }

build_runtime_env() {
    # Regenerated fresh from the gitignored .env each restart, written to
    # /tmp rather than kept as a permanent copy of the secret.
    : > "$RUNTIME_ENV"
    if [ -f "$REPO_ROOT/backend/.env" ]; then
        grep '^GEMINI_API_KEY=' "$REPO_ROOT/backend/.env" >> "$RUNTIME_ENV" || true
    fi
    echo "GCP_PROJECT_ID=pact-hackathon" >> "$RUNTIME_ENV"
    if [ -f "$CRED_MOUNT" ]; then
        echo "GOOGLE_APPLICATION_CREDENTIALS=/secrets/pact-dashboard-reader-key.json" >> "$RUNTIME_ENV"
    fi
    chmod 600 "$RUNTIME_ENV"
}

start_container() {
    log "starting $CONTAINER..."
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    build_runtime_env
    if [ -f "$CRED_MOUNT" ]; then
        docker run -d --name "$CONTAINER" -p "$PORT:$PORT" \
            --env-file "$RUNTIME_ENV" \
            -v "$CRED_MOUNT:/secrets/pact-dashboard-reader-key.json:ro" \
            "$IMAGE" >/dev/null
    else
        docker run -d --name "$CONTAINER" -p "$PORT:$PORT" \
            --env-file "$RUNTIME_ENV" \
            "$IMAGE" >/dev/null
    fi
    shred -u "$RUNTIME_ENV" 2>/dev/null || rm -f "$RUNTIME_ENV"
    log "container started"
}

start_ngrok() {
    log "starting ngrok..."
    pkill -f "ngrok http $PORT" 2>/dev/null || true
    sleep 1
    nohup ngrok http "$PORT" --log=stdout > /tmp/pact-ngrok.log 2>&1 &
    disown
    log "ngrok started"
}

container_healthy() {
    local state
    state=$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo "false")
    [ "$state" = "true" ] && curl -sf -m 5 "http://localhost:$PORT/openapi.json" >/dev/null 2>&1
}

ngrok_healthy() {
    curl -sf -m 5 "http://localhost:4040/api/tunnels" 2>/dev/null | grep -q '"public_url"'
}

log "watchdog started (checking every ${CHECK_INTERVAL}s, container=$CONTAINER port=$PORT)"

while true; do
    if ! container_healthy; then
        log "container unhealthy or down -- restarting"
        start_container
        sleep 5
    fi
    if ! ngrok_healthy; then
        log "ngrok tunnel down -- restarting"
        start_ngrok
        sleep 5
    fi
    sleep "$CHECK_INTERVAL"
done
