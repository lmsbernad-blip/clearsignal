-- 03 DATA HEALTH CHECKS: every check returns the rows that FAIL, in one table the team reviews each morning.
-- check_id is the technical name; title / detail / action are written for account managers and clients.
-- severity: High = numbers in client reports are wrong today; Medium = fix soon.

create or replace table qa_results as

-- 1. Duplicate rows from connector re-syncs
select 'duplicate_rows' as check_id, 'Some days were counted twice' as title, 'High' as severity,
       client, platform, campaign_name as object,
       count(*) - count(distinct date) as rows_affected,
       round(sum(spend) - sum(spend) / count(*) * count(distinct date), 2) as usd_at_risk,
       'Meta sent the data for ' || strftime(min(date), '%b %-d') || case when min(date) <> max(date) then ' to ' || strftime(max(date), '%b %-d') else '' end || ' twice, so spend for this campaign looked $'
       || format('{:,.0f}', sum(spend) - sum(spend) / count(*) * count(distinct date)) || ' higher than it really was.' as detail,
       'Already corrected in the report. Ask the data connection provider to confirm it won''t repeat.' as action
from (select *, count(*) over (partition by date, client, campaign_name) as cnt from stg_meta_ads_raw)
where cnt > 1
group by client, platform, campaign_name

union all
-- 2. Spend arriving in micros from a second connector
select 'cost_in_micros', 'Spend arriving in the wrong unit', 'Medium', client, platform, 'Whole account', count(*), round(sum(spend), 2),
       'Since ' || strftime(min(date), '%b %-d') || ', one of the two Google Ads data feeds reports spend in millionths of a dollar, '
       || 'which would make spend look a million times too high.',
       'Converted automatically, so the report is right. Switch both feeds to the same spend field to remove the risk.'
from stg_google_ads where spend_from_micros
group by client, platform

union all
-- 3. Ad campaigns missing from the mapping
select 'unmapped_campaign', 'New campaign not set up in reporting', 'High', client, platform, campaign_name, count(*), round(sum(spend), 2),
       'This campaign went live on ' || strftime(min(date), '%b %-d') || ' but hasn''t been added to the reporting setup, so its results '
       || 'are missing from the report.',
       'Add the campaign to the reporting setup (one row in campaign_mapping.csv).'
from fct_ads_daily a
where not exists (select 1 from seed_campaign_mapping m
                  where m.client = a.client and m.platform = a.platform and m.campaign_name = a.campaign_name)
group by client, platform, campaign_name

union all
-- 4. Paid social traffic in GA4 with no UTM tags
select 'missing_utms', 'Paid ads showing up as free traffic', 'High', g.client, 'Meta Ads', 'Facebook visits with no ad tags', count(*), null,
       'Since ' || strftime(min(g.date), '%b %-d') || ', Google Analytics has recorded ' || format('{:,}', cast(round(sum(g.ga4_conversions)) as bigint))
       || case when max(c.business_model) = 'ecommerce' then ' sales' else ' leads' end || ' from Facebook as ordinary '
       || 'website referrals instead of paid ads, because one campaign''s ad links are missing tracking tags.',
       'Media buyer adds tracking tags to the ad links; we then credit the results to the right campaign.'
from stg_ga4 g
left join seed_clients c using (client)
where g.source_medium like '%facebook%' and g.source_medium like '%referral%'
group by g.client, g.source_medium

union all
-- 5. Campaigns with no matching GA4 traffic at all
select 'no_ga4_match', 'Campaign results not visible in Google Analytics', 'High', m.client, m.platform, m.campaign_name, 0, round(sum(a.spend), 2),
       'Google Analytics can''t see any results for this campaign, so the report shows it earning nothing, even though ' || replace(m.platform, ' Ads', '') || ' reports '
       || format('{:,.0f}', sum(a.platform_conversions)) || ' results.',
       case when m.utm_campaign is null then 'Add tracking tags to the ad links (see the item above).'
            else 'Check the campaign''s tracking template.' end
from seed_campaign_mapping m
join fct_ads_daily a using (client, platform, campaign_name)
where not exists (select 1 from stg_ga4 g where g.client = m.client and g.utm_campaign = m.utm_campaign)
group by m.client, m.platform, m.campaign_name, m.utm_campaign

union all
-- 6. Tracking break: spend but zero platform conversions for 2+ days
select 'tracking_break',
       'Ad platform stopped counting ' || case when max(business_model) = 'ecommerce' then 'sales' else 'leads' end,
       'High', client, platform, campaign_name, count(*), round(sum(spend), 2),
       'From ' || strftime(min(date), '%b %-d') || ' to ' || strftime(max(date), '%b %-d') || ', ads kept running ($' || format('{:,.0f}', sum(spend))
       || ') but ' || replace(platform, ' Ads', '') || ' counted zero '
       || case when max(business_model) = 'ecommerce' then 'sales' else 'leads' end
       || ', while Google Analytics still recorded ' || cast(round(sum(ga4_conversions)) as bigint)
       || '. The ads didn''t stop working; the tracking did.',
       'Ask the client''s web team to check the ' || replace(platform, ' Ads', '') || ' tracking code. '
       || replace(platform, ' Ads', '') || ' can''t optimize well until it''s fixed.'
from mart_campaign_daily d
where platform_conversions = 0 and spend > 0
  and spend > getvariable('tracking_break_min_spend_share') * (
      select median(spend) from mart_campaign_daily x
      where x.client = d.client and x.platform = d.platform and x.campaign_name = d.campaign_name)
group by client, platform, campaign_name
having count(*) >= getvariable('tracking_break_min_days')

union all
-- 7. Budget pacing
select 'budget_pacing', case when pace > 1 then 'Spending ahead of budget' else 'Spending behind budget' end,
       case when abs(pace - 1) > getvariable('pacing_high_severity') then 'High' else 'Medium' end, client, 'All channels', 'This month', days_elapsed,
       round(mtd_spend - planned_to_date, 2),
       '$' || format('{:,.0f}', mtd_spend) || ' spent so far this month, ' || format('{:.0f}', abs(pace - 1) * 100) || '% '
       || case when pace > 1 then 'more' else 'less' end || ' than planned. At this rate the month ends at $'
       || format('{:,.0f}', projected) || ' against a $' || format('{:,.0f}', budget) || ' budget.',
       case when pace > 1 then 'Media buyer lowers daily budgets, or the client approves the extra spend.'
            else 'Media buyer raises daily budgets to use the full plan.' end
from (
    select client, sum(spend) as mtd_spend, max(monthly_budget)::double as budget,
           day(max(date)) as days_elapsed,
           max(monthly_budget) * day(max(date)) / day(last_day(max(date))) as planned_to_date,
           sum(spend) / (max(monthly_budget) * day(max(date)) / day(last_day(max(date)))) as pace,
           sum(spend) / day(max(date)) * day(last_day(max(date))) as projected
    from mart_campaign_daily
    where date >= date_trunc('month', (select max(date) from mart_campaign_daily))
    group by client
)
where pace > getvariable('pacing_high') or pace < getvariable('pacing_low')

union all
-- 8. Freshness
select 'freshness', 'Data is out of date', 'Medium', client, src, 'Latest data', 0, null,
       src || ' data stops on ' || strftime(max_d, '%b %-d') || ', ' || (expected - max_d) || ' day(s) behind.',
       'Check the data connection for this source.'
from (
    select client, 'Google Ads' as src, max(date) as max_d from stg_google_ads group by client
    union all select client, 'Meta Ads', max(date) from stg_meta_ads_raw group by client
    union all select client, 'Google Analytics', max(date) from stg_ga4 group by client
) cross join (
    -- the newest date any source has reached, so a stale GA4 is caught too
    select greatest((select max(date) from stg_google_ads), (select max(date) from stg_meta_ads_raw),
                    (select max(date) from stg_ga4)) as expected
)
where max_d < expected;
