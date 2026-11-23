-- 05 DATA TESTS: checks on the BUILT warehouse. One row per test; failures = 0 means it passed.
-- app/warehouse.py runs this last and refuses to publish the warehouse if any test has failures > 0.
-- (Different from 03_qa_checks.sql: QA checks find problems in the client's data and report them;
--  data tests find problems in OUR pipeline, and stop the build.)

create or replace table data_test_results as

-- 1. Grain: one row per date x client x platform x campaign after the Meta dedupe
select 'fct_ads_daily_unique_grain' as test_name,
       count(*) as failures,
       'fct_ads_daily must have one row per date, client, platform and campaign' as description
from (select date, client, platform, campaign_name from fct_ads_daily group by all having count(*) > 1)

union all
-- 2. Mart grain matches the fact table (a duplicate mapping or GA4 row would multiply rows)
select 'mart_rows_match_facts',
       abs((select count(*) from mart_campaign_daily) - (select count(*) from fct_ads_daily)),
       'mart_campaign_daily must have exactly one row per fct_ads_daily row'

union all
-- 3. Spend is preserved to the cent from the deduplicated sources into the mart
select 'spend_preserved_to_the_cent',
       case when abs((select coalesce(sum(spend), 0) from mart_campaign_daily)
                   - (select coalesce(sum(spend), 0) from stg_google_ads)
                   - (select coalesce(sum(spend), 0) from int_meta_ads)) < 0.005 then 0 else 1 end,
       'total spend in mart_campaign_daily must equal Google Ads + deduplicated Meta spend'

union all
-- 4. No nulls in key columns
select 'no_null_keys',
       (select count(*) from mart_campaign_daily
        where date is null or client is null or platform is null or campaign_name is null
           or campaign_type is null or spend is null or business_model is null),
       'date, client, platform, campaign_name, campaign_type, spend and business_model must never be null'

union all
-- 5. Every campaign_type is a known value or UNMAPPED
select 'known_campaign_types',
       (select count(*) from mart_campaign_daily
        where campaign_type <> 'UNMAPPED' and not list_contains(getvariable('campaign_types'), campaign_type)),
       'campaign_type must be one of config.CAMPAIGN_TYPES or UNMAPPED'

union all
-- 6. Every client in the ad data is set up in clients.csv and the media plan
select 'clients_configured',
       (select count(*) from mart_campaign_daily where monthly_budget is null or business_model is null),
       'every client and month with spend needs a row in clients.csv and media_plan.csv'

union all
-- 7. Reconciliation statuses come only from the allowed list
select 'allowed_reconciliation_statuses',
       (select count(*) from reconciliation_weekly where not list_contains(getvariable('recon_statuses'), status))
     + (select count(*) from reconciliation_summary where not list_contains(getvariable('recon_statuses'), typical_status)),
       'reconciliation statuses must be one of config.RECON_STATUSES'

union all
-- 8. QA rows are complete and use the two severities
select 'qa_rows_complete',
       (select count(*) from qa_results
        where title is null or detail is null or action is null or client is null
           or not list_contains(getvariable('qa_severities'), severity)),
       'every QA row needs a title, detail, action, client and a severity of High or Medium'

union all
-- 9. No negative or impossible delivery numbers survived staging
select 'non_negative_delivery',
       (select count(*) from fct_ads_daily
        where spend < 0 or impressions < 0 or clicks < 0 or platform_conversions < 0 or clicks > impressions),
       'spend, impressions, clicks and conversions must be >= 0, and clicks <= impressions';
