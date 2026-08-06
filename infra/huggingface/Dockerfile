# Single-container deployment for Hugging Face Spaces (free, cardless
# hosting -- the substitute for Cloud Run, which requires a billing
# account). Runs all three backend services plus the built frontend
# behind one public port, matching what the local multi-terminal setup
# does, just packaged into one container.
#
# Deliberately NOT baked into the image: any GCP credential. The image
# itself contains no key, so the artifact is safe to publish or share.
#
# The running container CAN be given read-only BigQuery access at deploy
# time, by mounting a key as a volume and pointing
# GOOGLE_APPLICATION_CREDENTIALS at it (see README's Deployment section).
# That is what the live demo does, so the Observability dashboard shows
# real data to anyone who opens the public URL rather than an "isn't
# reachable" message. The key used is deliberately minimal --
# a dedicated service account with roles/bigquery.jobUser plus READER on
# only the `pact` dataset, so a leak exposes read access to negotiation
# logs and nothing else in the project. Without the mount, BigQuery
# access simply degrades gracefully (exactly as designed for PRD §27).
#
# Ollama/Gemma is local machine-only regardless -- the deployed
# version's Verification Agent runs the deterministic check alone (still
# fully correct; Gemma is an independent pre-screen, never
# authoritative), so Gemma spans only appear when running locally.

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
