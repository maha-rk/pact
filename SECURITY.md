# Security

## Reporting a vulnerability

This is a solo competition build (AI Agent Builder Series 2026). If you
find a genuine security issue, please open a GitHub issue on this repo
rather than a public pull request describing the exploit.

## What this build actually does

- **No payment or card information is required anywhere.** The
  deployment path (Docker + ngrok — see the README's
  [Deployment](README.md#deployment) section) was deliberately chosen
  over billing-gated infrastructure for this reason.
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
