# Security policy

## Reporting a problem

If you find a security issue, please **don't open a public issue**. Use GitHub's private vulnerability reporting instead: **Security → Report a vulnerability** on this repository. Include what you found, how to reproduce it, and what impact you expect.

You should get a reply within 5 business days. Fixes are released as a new tagged version, with a note in `CHANGELOG.md`.

## What data ClearSignal handles

- **Demo data only.** Everything in `data/` is a seeded simulation (`scripts/generate_data.py`): three fictional agency clients with made-up campaigns and numbers. There is **no real client data and no personal data** (no names, emails, user IDs or IP addresses) in this repository.
- **The warehouse** (`data/warehouse.duckdb`) is built from those files, git-ignored, and opened **read-only** by the app.
- **Claude API key (optional).** It's used only by `scripts/draft_client_note.py`, read from the `ANTHROPIC_API_KEY` environment variable or a local `.env` file (git-ignored; see `.env.example`). The deployed app makes **no** API calls and needs no key. If you add one on Streamlit Community Cloud, store it in the app's **Secrets**, never in the repository.
- **Nothing is written back** to Google Ads, Meta or Google Analytics, and nothing is sent to a client automatically; a person reviews every draft.

## If you use real client data

The pipeline is built so connector exports can replace the demo CSVs. If you do that:

- Keep real exports out of git. Add `data/raw/` and `data/seeds/` to `.gitignore` and use a private repository.
- Deploy only behind authentication (Streamlit Community Cloud apps are public by default).
- Check the client's data agreement before sending any of their numbers to an external AI service.

## How the code is protected

The [threat model in docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#7-threat-model) lists the protections. In brief: an allowlist of readable tables, read-only database reads, HTML escaping of every data value, prompt data kept in delimited blocks, input contracts, and CI that runs `bandit`, `pip-audit` and the test suite on every push.
