## What this changes

<!-- One or two sentences: what and why. Link the issue if there is one. -->

## How it was checked

<!-- e.g. new or updated tests, a screenshot of the affected tab, a rebuild of the warehouse -->

## Checklist

- [ ] Tests pass locally (`pytest`), and CI is green
- [ ] `ruff check` and `ruff format --check` are clean
- [ ] No secrets, API keys, `.env` files or real client data in the diff
- [ ] If thresholds changed, they changed in `app/config.py` only
- [ ] If SQL changed, the data tests still pass (`python scripts/build_warehouse.py`)
- [ ] App wording is still plain business language, and status is never shown by color alone
- [ ] Docs updated (README, CHANGELOG, KPI dictionary or architecture, as needed)
