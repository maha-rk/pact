# Single-container deployment for Hugging Face Spaces (free, cardless
# hosting -- the substitute for Cloud Run, which requires a billing
# account). Runs all three backend services plus the built frontend
# behind one public port, matching what the local multi-terminal setup
# does, just packaged into one container.
#
# Deliberately NOT included: GCP credentials for BigQuery. Embedding a
# long-lived service account key in a public-facing container is a real
# security risk this build avoids -- BigQuery logging gracefully degrades
# here (exactly as designed for PRD §27) and only runs when the system is
# run locally with the operator's own gcloud auth. Ollama/Gemma is local
# machine-only for the same reason -- the deployed version's Verification
# Agent runs the deterministic check alone (still fully correct; Gemma is
# an independent pre-screen, never authoritative).

# ---- Stage 1: build the frontend ----
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty VITE_API_BASE -> relative paths -> same-origin as pact-core in
# the single-container deployment (see frontend/src/api.ts).
ENV VITE_API_BASE=""
RUN npm run build

# ---- Stage 2: python runtime ----
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/pact ./backend/pact
COPY backend/vendors ./backend/vendors
WORKDIR /app/backend
RUN pip install --no-cache-dir .

COPY --from=frontend-builder /app/frontend/dist ./static

COPY infra/huggingface/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# HF Spaces' default Docker SDK port.
EXPOSE 7860
ENV PORT=7860

CMD ["/app/entrypoint.sh"]
