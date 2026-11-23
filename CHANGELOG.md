# Changelog

All notable changes to ClearSignal are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Live demo link in the README (Streamlit Community Cloud).
- First-glance clarity: a "Start here" panel (what you're looking at, whether the report can go to the client today, and how to read it), a plain-language headline sentence, a one-line meaning on each KPI card, captions on the five steps, and numbered tabs.
- Dependabot: weekly pip and GitHub Actions update pull requests (numpy held below 2.5 while the project targets Python 3.11).
- `docs/RUNBOOK.md`: refreshing data, rebuilding, adding a client or a check, releasing, and what to do if the deployed app fails.
- Requirements gap list now records how each gap was resolved.

## [1.0.0] - 2026-11-23

First public release.

### Included
- **Collect:** Google Ads, Meta Ads and GA4 connector-style exports staged into DuckDB under one vocabulary (`sql/01_staging.sql`), with Meta re-sync deduplication and Google Ads `cost_micros` conversion (`sql/02_model.sql`).
- **Check:** eight daily data-health checks written for account managers: duplicate days, spend in micros, unmapped campaigns, missing UTMs, no GA4 match, tracking breaks, budget pacing (85–110% band) and freshness (`sql/03_qa_checks.sql`).
- **Compare:** weekly platform vs GA4 reconciliation over 8 weeks, with every gap labeled *matches*, *normal* or *fix* (`sql/04_reconciliation.sql`).
- **Report:** a Streamlit dashboard with seven tabs: KPI readouts, data health, reconciliation, results and pacing, budget optimizer, weekly client email and agency ROI. Words follow the business ("sales" or "leads").
- **Advise:** a budget optimizer (diminishing-returns curves, 70–150% guardrails, brand-name search capped at +10%) and a Claude prompt for the weekly client email (`app/prompts.py`, `scripts/draft_client_note.py`).
- **Demo data:** a seeded simulation of three clients with six planted problems (`scripts/generate_data.py`); byte-identical on every run and every OS.
- **Data validation:** input contracts before the build (`app/contracts.py`) and 9 post-build data tests (`sql/05_data_tests.sql`). The build is atomic: a failure keeps the previous warehouse.
- **Configuration** in one place (`app/config.py`); the SQL reads the same thresholds through DuckDB variables.
- **Tests:** 94 pytest tests (unit, pipeline, validation, security, app smoke); 99% line coverage of `app/analytics.py`.
- **CI:** GitHub Actions running ruff, bandit, pip-audit, a demo-data reproducibility check, the warehouse build and pytest with an 80% coverage gate.
- **Security:** an allowlist for table reads, read-only database access from the app, HTML escaping of all data, prompt data kept in delimited blocks, secrets only in the environment or Streamlit Secrets, `SECURITY.md` and a threat model.
- **Design:** a "noise to signal" visual language with short entrance animations; status is never shown by color alone, and motion stops when the system asks for reduced motion.
- **Docs:** requirements with acceptance criteria, architecture and threat model, onboarding checklist, KPI dictionary, discrepancy case study and the Claude workflow.

### Fixed during hardening (before release)
- The app crashed on Windows at startup (Linux-only `%-d` date format).
- Budget recommendations changed between rebuilds (row order wasn't fixed before taking "the last 30 days").
- A failed build could leave a half-built warehouse that the app then crashed on.
- A build pointed at another folder could silently read the project's own data.
- The pacing chart used a 90–110% band while the data check used 85–110%.

[1.0.0]: https://github.com/lmsbernad-blip/clearsignal/releases/tag/v1.0.0
