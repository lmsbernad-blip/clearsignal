# KPI definitions, data dictionary and reporting standards

## KPIs

| KPI | Definition | Source of truth | Notes |
|---|---|---|---|
| Spend | Media cost in USD, as billed by the platform | Ad platform | Google Ads `Cost`, or `cost_micros / 1,000,000` |
| Impressions, clicks | As reported by the platform | Ad platform | Meta clicks = `inline_link_clicks` |
| Conversions (reported) | Purchases or leads attributed to paid media | **GA4** | One de-duplicated number across channels |
| Platform conversions | What each ad platform claims | Ad platform | Used for in-platform optimization only, never summed across platforms |
| Value | E-commerce: GA4 purchase revenue. Lead gen: GA4 conversions × agreed value per lead | GA4 + `clients.csv` | Value per lead agreed with the client at kickoff |
| ROAS | Value ÷ Spend | Derived | Shown with the conversion source it uses |
| CPA | Spend ÷ Conversions | Derived | |
| Pacing | Month-to-date spend ÷ (monthly plan × days elapsed ÷ days in month) | Derived | Flag outside 85%–110% |

## Reporting standards

1. **One source of truth for results:** GA4 for cross-channel reporting; platform numbers stay inside platform-level views and are labeled "self-reported".
2. **Expected gaps are documented, not "fixed":** set an expected range per platform at onboarding from the first 8 weeks of reconciliation. In these accounts Meta (7-day click / 1-day view) runs about 40–50% above GA4 and Google Ads about 15% above.
3. **Compare platforms to GA4 weekly, not daily:** Meta accounts report in Pacific time, GA4 in Eastern time, so roughly the last three hours of each Pacific day land on the next GA4 day.
4. **Every live campaign must be in `campaign_mapping.csv`** with its type and utm_campaign before it appears in client reports.
5. **UTM convention:** `utm_source` = platform, `utm_medium` = cpc / paid_social, `utm_campaign` = lowercase campaign name.
6. **Campaign naming:** `CLIENT_CHANNEL_OBJECTIVE_GEO`, e.g. `DTC_GS_NonBrand_US` (GS = Google Search, GSH = Shopping, FB = Meta, PMAX = Performance Max).
7. **No High QA issue goes into a client report unexplained.**

## Tables

| Table | Grain | Built in | Purpose |
|---|---|---|---|
| `stg_google_ads`, `stg_meta_ads_raw`, `stg_ga4` | source row | `01_staging.sql` | Rename to common vocabulary, fix types |
| `fct_ads_daily` | date × campaign | `02_model.sql` | Deduplicated spend and platform conversions |
| `fct_ga4_paid_daily` | date × campaign | `02_model.sql` | GA4 paid traffic joined through utm_campaign |
| `mart_campaign_daily` | date × campaign | `02_model.sql` | Platform vs GA4 side by side, value, budget |
| `qa_results` | issue | `03_qa_checks.sql` | Morning checks; one row per failure |
| `reconciliation_weekly`, `reconciliation_summary` | week × campaign | `04_reconciliation.sql` | Platform vs GA4 gap with status |
