# Runbook

How to operate ClearSignal day to day. Commands are for PowerShell from the project folder with the virtual environment active (`.venv\Scripts\Activate.ps1`); on macOS or Linux use `source .venv/bin/activate`.

## 1. Refresh the data

**Demo data**: it's seeded, so this always gives the same files:

```powershell
python scripts/generate_data.py
python scripts/build_warehouse.py
```

**Real connector exports**: replace the files in `data/raw/` with exports in the same shape (column names in `app/contracts.py`), then run `python scripts/build_warehouse.py`. Read [SECURITY.md](../SECURITY.md) first: real data must never be committed to this public repo.

The build always runs in this order:

1. **Input contracts**: every file is checked (columns, types, dates, no negatives, USD). If anything fails, the build stops and lists every problem with row numbers.
2. **SQL** `01` → `05`, built into a temporary file.
3. **Data tests** (`sql/05_data_tests.sql`). If any test fails, the build stops.
4. Only then is `data/warehouse.duckdb` replaced. A failed build never touches the previous warehouse.

A running Streamlit app keeps the file open, and Windows won't replace an open file. If the build says *"it is open in another program"*, stop the app (Ctrl+C), rebuild, and start it again.

## 2. Rebuild and check everything

```powershell
python scripts/build_warehouse.py   # contracts + SQL + data tests
pytest                              # 94 tests, about 30 s
streamlit run app/streamlit_app.py
```

| The build says | What to do |
|---|---|
| `Input file is missing: data/raw/...` | Restore the file or run `generate_data.py` |
| `... missing a required column: X` | A connector renamed a column; fix the export, or update `app/contracts.py` and `sql/01_staging.sql` together |
| `... is negative in rows ...` / `... aren't valid dates` | Bad rows in the export; fix them at the source and re-export |
| `Currency must be one of USD` | A non-USD account; ClearSignal reports in USD only |
| `data test(s) failed after the build` | A pipeline problem (e.g. a duplicate mapping row). The message names the rule; the old warehouse is still in place |

## 3. Add a new client

1. **`data/seeds/clients.csv`**: add `client, business_model (ecommerce | leadgen), value_per_lead_usd (required for leadgen), ga4_timezone`.
2. **`data/seeds/media_plan.csv`**: add one row per month: `client, month (YYYY-MM), planned_budget_usd`.
3. **`data/seeds/campaign_mapping.csv`**: add one row per live campaign: `platform (Google Ads | Meta Ads), campaign_name, client, campaign_type, utm_campaign`.
   - `campaign_type` must be one of `config.CAMPAIGN_TYPES`. To add a new type, add it there and give it a readable label in `FRIENDLY` in `app/analytics.py`.
   - `utm_campaign` must match what GA4 reports in `sessionCampaignName`, or the *No GA4 match* check will fire, as it should.
4. **Name the accounts consistently** in the exports, because staging uses these names to find the client: Google Ads `Account name` = `<client> - Google Ads`, Meta `account_name` = `<client> - Meta`, GA4 `property` = `<client> GA4`.
5. Rebuild. The client appears in the sidebar automatically. Work through [the onboarding checklist](01_ONBOARDING_CHECKLIST.md) until there are no High issues left.

## 4. Add a new data-health check

1. **SQL**: add a `union all` block to `sql/03_qa_checks.sql` that returns the *failing* rows, with exactly these columns: `check_id, title, severity ('High' | 'Medium'), client, platform, object, rows_affected, usd_at_risk, detail, action`. Write `title`, `detail` and `action` in plain business language for account managers.
2. **Thresholds**: put any number in `app/config.py`, add it to `sql_variables()`, and read it in SQL with `getvariable('name')`. Never type the number into the SQL.
3. **Tests** (in `tests/test_pipeline.py`):
   - a positive test: the demo data (or a planted problem in `scripts/generate_data.py`) makes the check fire exactly as expected;
   - a negative test: `clean_root` (planted problems removed, see `tests/conftest.py`) returns zero rows for it.
4. Run `python scripts/build_warehouse.py` and `pytest`. The `qa_rows_complete` data test fails if the new rows have a missing title or detail, or an unknown severity.
5. The Data health tab shows new rows automatically. Add the check to the KPI dictionary and the README if it's client-facing.

## 5. Change a threshold

Edit `app/config.py` only (match tolerance, pacing band, optimizer guardrails, brand cap, fit window). The SQL, the app and the tests all read from it. Rebuild and run `pytest`: some tests pin today's values on purpose and will tell you which documented numbers to update.

## 6. Release a change

1. Branch from `main`, commit in small steps, push, and open a pull request (the template lists the checks).
2. Wait for CI to pass: ruff, bandit, pip-audit, data reproducibility, build, pytest with an 80% coverage gate.
3. Merge on your laptop (`git merge --no-ff`) and push `main`, so every commit carries your noreply email. Avoid merging with the GitHub button, unless "Keep my email addresses private" is on in your GitHub settings.
4. For a release: update `CHANGELOG.md`, then `git tag -a vX.Y.Z -m "..."`, `git push origin vX.Y.Z`, `gh release create vX.Y.Z`.
5. Streamlit Community Cloud redeploys `main` automatically within a minute or two.

**Dependabot** opens update pull requests every Monday (pip and GitHub Actions). Merge them only when CI is green. numpy 2.5+ is held back on purpose, because it needs Python 3.12.

## 7. If the deployed app fails

Live app: https://clearsignal-weehhlc3xrqohydemrycjr.streamlit.app/ · Manage it at [share.streamlit.io](https://share.streamlit.io).

| Symptom | Likely cause | Fix |
|---|---|---|
| "This app has gone to sleep" | No visitors for about 12 hours (free tier) | Click **Yes, get this app back up!** and wait about a minute. Before a demo, open it 5–10 minutes early. |
| Endless spinner on first load | Cold start: installing packages and building the warehouse | Wait up to 3–4 minutes. If it never loads, open **Manage app → Logs**. |
| Red box "ClearSignal can't load its data" | A data file is missing or broken in the deployed commit | The message names the file. Fix it in the repo (CI would have caught a contract failure), push, and the app redeploys. |
| "Error installing requirements" in the logs | A dependency pin broke, or the Python version changed | Check the app runs Python 3.11 (**Settings → General**); compare with the last green CI run; revert the bad `requirements.txt` change. |
| Python traceback on a page | A code bug that reached `main` | Reproduce locally with `pytest` and `streamlit run`. To roll back fast: `git revert <bad commit>` on a branch, then a PR, CI and push; or point the app at the last good tag. |
| Changes don't appear | The redeploy didn't trigger | **Manage app → Reboot app**. |

**Rollback**: every release is tagged (`v1.0.0`, …). `git revert` the bad change and push through the normal flow; never force-push `main`.

**Escalation**: for a security issue, follow [SECURITY.md](../SECURITY.md). If Streamlit Community Cloud itself is down, run the app locally for the demo (section 2).
