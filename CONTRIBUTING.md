# Contributing

This is a solo competition build (AI Agent Builder Series 2026), but the
usual flow applies if you'd like to extend it:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/improvement`).
3. Make your change.
4. Run the checks below.
5. Open a pull request describing what changed and why.

## Before you open a PR

```bash
# Backend
cd backend && source .venv/bin/activate
pytest tests/

# Frontend
cd frontend
npm run lint
npm run build   # runs tsc -b, then the production build
```

## What to preserve

Changes should preserve the invariants the whole project is built
around — described in detail in the README's
[Safety by Design](README.md#safety-by-design) and
[Evidence & Policy Gates](README.md#evidence--policy-gates)
sections:

- the deterministic concession-curve math (no LLM ever sets a price);
- the independent verification gate (a vendor claim is checked against
  real external data before it can affect the outcome);
- the compliance policy gate (a verified offer can still be rejected on
  policy grounds); and
- the human approval boundary (nothing is ever finalized without an
  explicit, recorded approval action, and approval never executes an
  external transaction).

See `docs/PRD.md` for the full functional requirements and acceptance
criteria this project is held to.
