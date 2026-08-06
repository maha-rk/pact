# Security

## Reporting a vulnerability

This is a solo competition build (AI Agent Builder Series 2026). If you
find a genuine security issue, please open a GitHub issue on this repo
rather than a public pull request describing the exploit.

## What this build actually does

- **No payment or card information is required for the core system.**
  The default configuration (Gemini Developer API + Docker/ngrok — see
  the README's [Deployment](README.md#deployment) section) needs no card
  anywhere. The *optional* Vertex AI fallback requires a billing-enabled
  GCP project — Google's real $300/90-day free trial was used for this,
  needing a card for identity verification only (a temporary hold, never
  an actual charge unless someone manually upgrades to a paid account).
- **Real JWT authentication** (`pact/api/gateway.py`), off by default
  (`AUTH_REQUIRED=false` — no end-user accounts exist yet to protect),
  but genuinely implemented and tested, not a placeholder.
- **Real rate limiting**, always on: 20 requests/minute per client on
  every negotiation-mutating endpoint.
- **Real, application-level AES-256-GCM field encryption**
  (`pact/security/field_encryption.py`), on top of BigQuery's own
  encryption at rest, for the budget ceiling, final price, and reasoning
  fields written to BigQuery. Off by default (`PACT_FIELD_ENCRYPTION_KEY`
  unset falls back to plaintext with a loud warning), but genuinely
  implemented and verified end to end against the live project, not a
  placeholder.
- **Vendor pricing data is public by construction** — both live pricing
  sources (AWS Price List Bulk API, Azure Retail Prices API) are public,
  keyless APIs; no private or credentialed vendor data is accessed.
- **No end-user personal data is required** for the core negotiation
  flow — a requirement is a business specification (budget, capacity,
  contract terms), not personal information (PRD §26).
- **API credentials are server-side only.** `GEMINI_API_KEY` is loaded
  from a gitignored `.env` file, never exposed to the frontend or logged
  in plaintext.
- **CORS is restricted** to the known local frontend origins
  (`localhost:5173`, `localhost:3000`).

## What this build does not claim

No formal security certification, penetration testing, or compliance
audit has been performed on this codebase, and none is claimed — see
`docs/PRD.md` §26 and §32.
