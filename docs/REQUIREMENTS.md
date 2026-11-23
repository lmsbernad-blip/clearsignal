# ClearSignal: requirements

Version 1.0 · status: draft for approval · owner: Lorenzo Bernad

## 1. Purpose

ClearSignal helps an ad agency take over a client's ad reporting quickly and make it trustworthy. It collects Google Ads, Meta Ads and GA4 exports, checks the data every day, explains why the ad platforms and Google Analytics disagree, reports results and budget pacing, suggests budget shifts, and drafts the weekly client email.

The demo runs on a **seeded simulation** with planted problems. It contains no real client data.

## 2. Users

| User | Needs | Main screens |
|---|---|---|
| **Agency account manager** | Know whether a client's numbers can be shared today; send a clear weekly update | Header, Data health, Weekly client email |
| **Agency analyst** | Find and fix data problems; explain platform vs GA4 gaps; maintain mappings and the media plan | Data health, Do the numbers match?, Results, SQL, seeds |
| **Media buyer** | Know where to move budget and whether a client is over or under its plan | Results (pacing), Where to spend next |
| **Client (reads the email)** | Plain-language results, what is being fixed, one recommendation | Weekly client email / Claude draft |
| **Agency leadership** | See the value of an analyst plus ClearSignal | Value to your agency |

## 3. Functional requirements

Each requirement has a test that checks its acceptance criterion. "Demo data" means the output of `scripts/generate_data.py` with seed 7.

### 3.1 Data ingestion and modelling

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Load the three raw exports (Google Ads, Meta Ads, GA4) and three seeds (campaign mapping, media plan, clients) into a DuckDB warehouse, renamed to one shared set of column names | `build_warehouse.py` builds `stg_google_ads`, `stg_meta_ads_raw`, `stg_ga4` and the `seed_*` tables from demo data without errors |
| FR-02 | Convert Google Ads spend from `cost_micros` when `Cost` is empty | For every Home Services Google Ads row from Oct 1, `spend = cost_micros / 1,000,000` (to the cent) |
| FR-03 | Remove duplicate Meta rows from connector re-syncs, keeping the most recent sync | `fct_ads_daily` has exactly one row per date × client × platform × campaign |
| FR-04 | Parse GA4 `YYYYMMDD` dates and match GA4 paid traffic to campaigns through `utm_campaign` | Every row in `fct_ga4_paid_daily` has a valid date and a campaign from the mapping |
| FR-05 | Build a campaign × day mart with platform and GA4 conversions side by side, value (revenue for e-commerce; conversions × value per lead for lead gen) and the monthly budget | `mart_campaign_daily` total spend equals total deduplicated source spend to the cent; for a lead-gen row, `ga4_value = ga4_conversions × value_per_lead_usd` |
| FR-06 | Label campaigns that are missing from the mapping as `UNMAPPED` instead of dropping them | `DTC_GS_Holiday_US` appears in the mart with `campaign_type = 'UNMAPPED'` |

### 3.2 Data health checks (`qa_results`)

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-10 | Flag any Meta campaign × day delivered more than once | On demo data: one High `duplicate_rows` row each for `DTC_FB_Prospecting_US` and `DTC_FB_Retargeting_US` (DTC Skincare), 2 rows affected each, Nov 8–9; together the spend at risk is about $2,221 |
| FR-11 | Flag Google Ads spend that arrives in micros | On demo data: exactly one Medium `cost_in_micros` row, for Home Services |
| FR-12 | Flag ad campaigns that are missing from the campaign mapping | On demo data: exactly one High `unmapped_campaign` row, for `DTC_GS_Holiday_US` |
| FR-13 | Flag paid social traffic that GA4 recorded as a referral (missing UTMs) | On demo data: exactly one High `missing_utms` row, for B2B SaaS |
| FR-14 | Flag mapped campaigns with no matching GA4 traffic | On demo data: exactly one High `no_ga4_match` row, for `B2B_FB_Retargeting_US` |
| FR-15 | Flag a tracking break: spend continues but platform conversions are zero for 2+ days | On demo data: High `tracking_break` rows for both DTC Skincare Meta campaigns, covering Nov 15–17 (3 days each), and no other campaign |
| FR-16 | Flag month-to-date budget pacing outside the 85–110% band; High when more than 25% off | On demo data: Home Services is flagged High "ahead of budget"; a client pacing between 85% and 110% is not flagged |
| FR-17 | Flag a source whose latest date is behind the newest GA4 date | On demo data: no `freshness` rows. On a copy with a source missing its last day: one Medium row |
| FR-18 | Each check row has a plain-language title, detail and next step, a severity (High/Medium) and, where it applies, the spend affected | No null `title`, `detail`, `action` or `severity` in `qa_results` |
| FR-19 | On clean data the checks raise nothing | On a copy of the demo data with the six planted problems removed, checks FR-10 to FR-15 return zero rows |

### 3.3 Reconciliation (platform vs GA4)

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-20 | Compare platform and GA4 conversions per campaign per week for the last 8 weeks | `reconciliation_weekly` covers at most 8 weeks ending on the latest date |
| FR-21 | Give each campaign one status from a fixed list: *Matches (within 20%)*, *Normal: Meta also counts people who only saw an ad* (Meta, +15% to +70%), *Fix: not visible in Google Analytics*, *Fix: new campaign not set up in reporting*, *Fix: ad platform stopped counting*, *Needs a closer look* | Every `status` / `typical_status` value is in that list; on demo data, `B2B_FB_Retargeting_US` is "not visible" and `DTC_GS_Holiday_US` is "not set up" |

### 3.4 Dashboard (Streamlit app)

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-30 | Sidebar filters: client (3), time period (7 / 30 / 90 days), count results using GA4 or the platform's own numbers | Every tab renders without an exception for all 18 combinations |
| FR-31 | Header shows the client, business model, channels, data date and the number of High issues (or "Numbers checked and ready") | For DTC Skincare the pill reads "5 data issues to fix" on demo data |
| FR-32 | KPI cards: spend, value, return per $1 (ROAS), cost per result (CPA), results, each with change vs the previous period and a sparkline | ROAS = value ÷ spend, CPA = spend ÷ conversions, CTR = clicks ÷ impressions, all matching hand calculations on a small fixed dataset; a zero denominator shows "n/a" or "-", never "nan" or "inf" |
| FR-33 | Words match the business: "sales" / "sales revenue" for e-commerce, "leads" / "lead value" for lead gen | No lead-gen client screen shows "sales", and the e-commerce client's screens show no "leads" |
| FR-34 | Data health tab lists issue cards for this client or all clients, High first | Number of cards equals the number of matching `qa_results` rows; an empty list shows "Everything checks out" |
| FR-35 | "Do the numbers match?" tab shows the gap per campaign, the status table and a week-by-week chart | One bar and one table row per campaign in `reconciliation_summary` for the client |
| FR-36 | Results tab: weekly ROAS by channel, budget pacing against the media plan, campaign summary table | The pacing verdict uses the same 85–110% band as FR-16 |
| FR-37 | "Where to spend next": reallocate the same daily budget to maximize predicted value using diminishing-returns curves, with guardrails | Total recommended budget equals current total within $1; every channel stays within 70–150% of its current spend; brand-name search rises no more than 10% |
| FR-38 | Weekly client email tab: a plain-language summary of this week vs last, best and weakest channel, open High issues and one recommendation, downloadable as text | Uses the right words for the business (FR-33); never contains "nan" or "inf"; it is still produced when a channel has no measurable value |
| FR-39 | Prepare the Claude prompt from the summary and open issues, and let the user view and download it | The prompt contains the client name, the summary and every open issue for that client |
| FR-40 | Value to your agency tab: an ROI calculator whose inputs the user can change | Changing any input updates the results; no division-by-zero error at the input limits (for example 90% automated) |
| FR-41 | How it works tab explains the five steps and labels the data as a simulation | The text "realistic sample data" is present |

### 3.5 Claude drafting (script)

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-50 | `draft_client_note.py <client>` prints the Claude draft when `ANTHROPIC_API_KEY` is set, and otherwise prints the prompt and exits with code 0 | Run without a key, it prints the prompt and returns exit code 0 |
| FR-51 | The model is set by `CLAUDE_MODEL`, with a documented default | Setting `CLAUDE_MODEL` changes the model the API is called with |
| FR-52 | The prompt tells Claude to use only the facts provided and to say when a number is missing; data inside the prompt is treated as data, not instructions | The prompt text contains both rules, and the facts and issues sit inside clearly marked data blocks |

### 3.6 Demo data

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-60 | `generate_data.py` gives the same output on every run and plants the six documented problems | Two runs produce identical CSVs (byte for byte); the FR-10 to FR-16 criteria hold |

## 4. Non-functional requirements

| ID | Area | Requirement | Acceptance criterion |
|---|---|---|---|
| NFR-01 | Performance | Each page loads quickly on a laptop | Each app rerun (filter change) completes in under 3 s locally once the warehouse is built; a full build takes under 30 s |
| NFR-02 | Reliability | Missing, empty or broken input never produces a stack trace in the app | With a raw file deleted or emptied, the app shows a plain message saying which file and what to do |
| NFR-03 | Reliability | The build checks raw inputs before loading and checks outputs after loading | Build exits with a non-zero code and a readable message on a bad input or a failed data test |
| NFR-04 | Portability | Runs on Windows (local demo) and Linux (Streamlit Community Cloud), Python 3.11+ | App and tests pass on Windows and on the Linux CI runner |
| NFR-05 | Security | No secrets in the repo or its history; the API key comes only from an environment variable or `st.secrets` | Secret scan is clean; `.env` and `.streamlit/secrets.toml` are git-ignored |
| NFR-06 | Security | No user input reaches SQL unchecked; the app opens DuckDB read-only | Table names come from a fixed allowlist; every `duckdb.connect` in `app/` uses `read_only=True` |
| NFR-07 | Security | Every dynamic value inserted into HTML is escaped | All values passed to `unsafe_allow_html` markup go through `ui.esc` (or are fixed constants) |
| NFR-08 | Security | Dependency and code scans are clean | `bandit -r app scripts` has no unresolved high or medium findings; `pip-audit` has no known vulnerabilities |
| NFR-09 | Accessibility | Status is never shown by color alone | Every colored status (issue severity, reconciliation status, KPI change, budget change, pacing) also has a text label, sign or arrow |
| NFR-10 | Maintainability | Thresholds and paths are kept in one place; public functions have type hints and docstrings; code is lint-clean | `app/config.py` holds paths and thresholds; `ruff check` passes; tests cover at least 80% of the lines in `app/analytics.py` |
| NFR-11 | Maintainability | Automated tests and CI | `pytest` passes in under 60 s; CI runs lint, scans, build, data tests and pytest on every push and pull request |
| NFR-12 | Transparency | The simulation is clearly labeled | README, app sidebar and How it works tab all say the data is a sample or simulation |
| NFR-13 | Privacy | No real client or personal data, and no private notes, in the public repo | Repo review is clean; private notes are not tracked and not in history |

## 5. Out of scope

- Real client data, and live connector or API pulls (Supermetrics, Improvado, platform APIs)
- Writing anything back to ad platforms (budgets, campaigns, tags)
- Sending email automatically. The account manager always reviews and sends.
- Live Claude calls inside the deployed app (the app shows and downloads the prompt; the script calls the API)
- User accounts, login and multiple tenants
- Currencies other than USD, and time-zone conversion beyond weekly reconciliation
- Causal measurement (geo holdouts, MMM). The optimizer gives estimates, not guarantees.

## 6. Gaps: requirements the current code does not meet

Checked on 2026-11-22 by reading the code, building the warehouse from demo data and running the app through `streamlit.testing` for all 18 filter combinations.

| # | Req. | Gap | Severity |
|---|---|---|---|
| G-01 | NFR-04, FR-30 | **The app crashes on Windows at startup.** `f"{as_of:%b %-d, %Y}"` (`app/streamlit_app.py:88`, `app/analytics.py:142`) uses the Linux-only `%-d` code and raises `ValueError: Invalid format string`. It works on Streamlit Cloud (Linux) but not on the laptop used for the demo. | **High** |
| G-02 | FR-36 | Pacing band mismatch: the Results chart says "on track" for 90–110% and turns red above 110%, but the data check (and the KPI dictionary) uses 85–110%. A client at 87% is "fine" in Data health but "13% under budget" on the chart. | Medium |
| G-03 | NFR-02 | No friendly errors. If the warehouse is missing, the app runs the build through `subprocess(check=True)`, so a missing or broken CSV shows a raw stack trace. Malformed files are not detected. | Medium |
| G-04 | NFR-03, FR-19 | No input contracts and no post-build data tests; the build does not stop on bad data. | Medium |
| G-05 | FR-37, FR-38 | Edge cases can crash: `optimize_budget` fails on empty curves (a client with under 20 usable days); `weekly_summary` fails when no channel has value this week (`idxmax` of an empty table) and can print "$nan" when a week has zero conversions. Not hit by demo data. | Medium |
| G-06 | NFR-06 | `table()` builds SQL with an f-string table name. Today it is only called with constants, so it is not exploitable, but there is no allowlist. | Low (Phase 6) |
| G-07 | FR-52 | The prompt says "do not invent numbers" but does not mark facts and issues as data, so a campaign name containing instructions could be read as one. | Low (Phase 6) |
| G-08 | FR-33 | Hard-coded nouns in check text: `tracking_break` always says "Meta counted zero **sales**" and `missing_utms` always says "**leads** from Facebook", whatever the client's business. Correct for today's demo data, wrong for any other client. | Low |
| G-09 | NFR-10 | Thresholds are spread across SQL, `analytics.py` and the app (20%, 85/110%, 0.7/1.5, 1.10, 20 days, 60 days); no `config.py`; few type hints and docstrings; no lint setup. The optimizer runs twice per page (Where to spend next tab and Weekly client email tab). | Low |
| G-10 | NFR-11 | No tests, no CI, unpinned dependencies (`>=` only), no `.venv` set up. | Medium |
| G-11 | NFR-05 | `.gitignore` lacks `.env`, `.streamlit/secrets.toml` and `*.pyc`; there is no `.env.example`. | Low |
| G-12 | NFR-13 | Private working notes sat inside the project folder (never tracked by git). | Low (Phase 6) |
| G-13 | docs | `docs/04_CLAUDE_WORKFLOW.md` refers to a "Client update" tab; the tab is called "Weekly client email". | Cosmetic |

**Met today (verified):** FR-01 to FR-06, FR-10 to FR-18 and FR-20/21 on demo data (every planted problem detected as specified, with no duplicates in `fct_ads_daily`); FR-31 to FR-35, FR-39 to FR-41; NFR-01 (about 0.7 s per rerun, build in a few seconds); NFR-09 (every colored status also carries a text label, sign or arrow); NFR-12. Once G-01 was patched in a scratch copy, all 18 filter combinations rendered with no exception and no "nan" or "inf" on screen.
