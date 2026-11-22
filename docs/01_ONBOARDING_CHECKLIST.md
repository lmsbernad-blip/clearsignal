# Client data onboarding checklist

Use one copy per new agency client. Target: trustworthy reporting live in **10 business days**.

| # | Step | Owner | Done when | Demo client status |
|---|---|---|---|---|
| 1 | Kickoff: confirm KPIs, conversion definitions, business model (e-commerce vs lead gen), value per lead | Analyst + account lead | KPIs signed off in the data dictionary | Done |
| 2 | Get access: Google Ads, Meta Business Manager, GA4, any CTV / programmatic seats | Client | Read access confirmed for every account | Done |
| 3 | Connect sources in Supermetrics / Improvado; one connector per source, consistent field set | Analyst | First full backfill landed | **Issue:** two Google Ads connectors (Cost vs cost_micros) |
| 4 | Record account time zones and currencies | Analyst | Listed in the data dictionary | Done (Meta PT, GA4 ET, USD) |
| 5 | Build the campaign mapping: platform campaign → client, campaign type, utm_campaign | Analyst | Every live campaign mapped | **Issue:** DTC_GS_Holiday_US launched unmapped |
| 6 | Audit UTMs on every live ad | Analyst → media buyer | Every campaign appears in GA4 under its own utm_campaign | **Issue:** B2B_FB_Retargeting_US has no UTMs |
| 7 | Run QA checks (`sql/03_qa_checks.sql`) until no High issues remain | Analyst | Zero High rows | 8 High open |
| 8 | Reconcile platform vs GA4 for 8 weeks; document expected gaps | Analyst | Every campaign has a status | Done, see reconciliation tab |
| 9 | Load the media plan; confirm pacing rules with the media buyer | Analyst + buyer | Monthly budgets in `media_plan.csv` | Done |
| 10 | Launch the dashboard and weekly client update; walk the client through definitions | Analyst | Client meeting held | Ready |

**Daily after launch:** review the QA table each morning, fix or explain every High issue the same day.
