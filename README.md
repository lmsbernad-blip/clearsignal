# ClearSignal · ad results you can trust

[![CI](https://github.com/lmsbernad-blip/clearsignal/actions/workflows/ci.yml/badge.svg)](https://github.com/lmsbernad-blip/clearsignal/actions/workflows/ci.yml)

**ClearSignal helps an ad agency take over a client's reporting fast: it collects the data, checks it every morning, explains why ad platforms and Google Analytics disagree, and turns the numbers into budget advice and a weekly client email.**

_Under the hood: a repeatable data onboarding kit (SQL + Python + Streamlit + Claude)._

**Live demo:** [open ClearSignal on Streamlit Community Cloud](https://clearsignal-weehhlc3xrqohydemrycjr.streamlit.app/) _(free hosting: if the app has been idle, click "wake up" and give it about a minute)_

![Data QA](docs/data_qa.png)

| Reconciliation | Budget optimizer | Agency ROI |
|---|---|---|
| ![](docs/reconciliation.png) | ![](docs/optimizer.png) | ![](docs/agency_roi.png) |

## Why this exists

When an agency onboards a client, the first weeks go to the same problems every time: a connector double-loads a day, cost arrives in micros, a campaign goes live without UTMs, Meta and GA4 disagree by 40%. Until those are found, every dashboard is wrong.

This kit makes onboarding the same five steps for every client, so an analyst produces trustworthy reporting in days instead of weeks:

| Step | What it does | Where |
|---|---|---|
| **1. Connect** | Lands Google Ads, Meta Ads and GA4 exports (Supermetrics / Improvado style) in DuckDB, renamed to one vocabulary | `sql/01_staging.sql` |
| **2. Validate** | Eight SQL checks: duplicates, cost in micros, unmapped campaigns, missing UTMs, no GA4 match, tracking breaks, budget pacing, freshness | `sql/03_qa_checks.sql` |
| **3. Reconcile** | Platform vs GA4 conversions by campaign and week, each gap labeled *expected*, *within tolerance* or *fix* | `sql/04_reconciliation.sql` |
| **4. Report** | Dashboard: KPIs, campaign scorecard, pacing vs media plan, GA4 vs platform toggle | `app/` |
| **5. Recommend** | Budget optimizer (diminishing-returns curves, brand-search cap) and a Claude-drafted weekly client update | `app/analytics.py`, `app/prompts.py` |

Documentation an analyst owns is included: [onboarding checklist](docs/01_ONBOARDING_CHECKLIST.md), [KPI & data dictionary with reporting standards](docs/02_KPI_DATA_DICTIONARY.md), [a worked discrepancy investigation](docs/03_DISCREPANCY_CASE_STUDY.md) and [the Claude workflow](docs/04_CLAUDE_WORKFLOW.md). Engineering docs: [requirements](docs/REQUIREMENTS.md), [architecture and threat model](docs/ARCHITECTURE.md) and [security policy](SECURITY.md).

## What it found in the demo onboarding

- **A "zero-lead" campaign that was actually one of the best:** a Meta retargeting campaign ran without UTMs, so GA4 filed its 104 leads under `facebook.com / referral`. Credited correctly, its ROAS goes from 0 to about 4.7. [Full investigation →](docs/03_DISCREPANCY_CASE_STUDY.md)
- **Double-counted spend:** a connector re-sync loaded two days of Meta data twice ($2,221 counted twice).
- **A pixel outage** hidden as a "performance drop": Meta purchases fell to zero for 3 days while GA4 kept recording sales.
- **Cost in micros** from a second Google Ads connector, an **unmapped holiday campaign**, and a client **on track to overspend its monthly plan by 66%**.
- **Expected gaps documented, not "fixed":** Meta reports about 40–50% more conversions than GA4 (7-day click / 1-day view), Google about 15%.

## Data

Client ad data is confidential, so the demo uses a **seeded simulation** of three agency clients (DTC e-commerce, B2B SaaS, home services) with exports in each platform's **native column names** (`cost_micros`, `purchases_7d_click_1d_view`, `sessionSourceMedium`, YYYYMMDD GA4 dates, Pacific vs Eastern time zones). See `scripts/generate_data.py` for the six planted problems. To use real data, replace the three CSVs in `data/raw/` with connector exports in the same shape; the build checks every file against its contract first. Read [SECURITY.md](SECURITY.md) before you do.

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py     # demo exports (seeded: the same files every time)
python scripts/build_warehouse.py   # checks inputs, runs sql/01-05 into data/warehouse.duckdb
streamlit run app/streamlit_app.py
```

Optional, for a Claude-written client email: `pip install anthropic`, copy `.env.example` to `.env`, add your key, then run `python scripts/draft_client_note.py "B2B SaaS"`. Without a key, the script prints the prompt so you can paste it into Claude yourself.

## Run tests

```powershell
pip install -r requirements-dev.txt
pytest                                   # 94 tests, about 30 seconds
pytest --cov=app --cov-report=term-missing
ruff check app scripts tests; ruff format --check app scripts tests
bandit -r app scripts -q; pip-audit -r requirements.txt
```

The tests build their own warehouse in a temporary folder, so they never touch `data/`.

## Quality and security

| | What runs | Where |
|---|---|---|
| **Tests** | 94 pytest tests: KPI math on hand-made data, optimizer guardrails (same total budget, 70–150% per channel, brand-name search capped at +10%), every planted problem detected exactly, a clean-data negative test, and every tab rendered for every client, period and counting option | `tests/` |
| **Data checks** | *Before the build:* input contracts (required columns, types that parse, dates in range, no negative spend, impressions or clicks, USD only). *After the build:* 9 data tests (one row per date × client × platform × campaign, spend preserved to the cent, no null keys, known campaign types and statuses). Any failure stops the build and keeps the previous warehouse. | `app/contracts.py`, `sql/05_data_tests.sql` |
| **CI** | On every push and pull request: ruff, bandit, pip-audit, a check that the demo data is reproducible, the warehouse build, and pytest with an 80% coverage gate | `.github/workflows/ci.yml` |
| **Security** | No secrets in the repo (the key lives in the environment or Streamlit Secrets); an allowlist for table reads; read-only database access from the app; every data value HTML-escaped; prompt data kept in delimited blocks; a threat model | [SECURITY.md](SECURITY.md), [threat model](docs/ARCHITECTURE.md#7-threat-model) |
| **Accessibility** | Status is never shown by color alone (text labels, arrows, signed numbers, signal-bar glyphs); animations switch off when the system asks for reduced motion | `app/ui.py` |

## Structure

```
data/raw/            Google Ads, Meta Ads, GA4 exports (connector-style)
data/seeds/          campaign mapping, media plan, client settings (maintained by the analyst)
sql/                 01 staging → 02 model → 03 QA checks → 04 reconciliation → 05 data tests
scripts/             generate demo data, build warehouse, draft client note with Claude
app/                 streamlit_app.py (entry), analytics, ui, prompts, config (thresholds and paths),
                     contracts (input checks), warehouse (build and read-only access)
tests/               unit, pipeline, validation, security and app smoke tests
docs/                checklist, data dictionary, case study, Claude workflow, requirements, architecture
.github/             CI workflow, pull request template
```

## Next steps

- Swap the CSVs for live Improvado / Supermetrics feeds into BigQuery or Snowflake; the SQL ports with small changes
- Post the morning QA table to Slack
- Add CTV and programmatic (impressions, completion rate, reach) to the same model
- Validate optimizer recommendations with geo holdout tests

Built by **Lorenzo Bernad** · [LinkedIn](https://www.linkedin.com/in/lorenzo-bernad-a8a8831a1)
