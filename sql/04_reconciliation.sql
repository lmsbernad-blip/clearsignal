-- 04 RECONCILIATION: platform-reported vs GA4 conversions, weekly (weekly grain absorbs the PT vs ET day-boundary shift).

create or replace table reconciliation_weekly as
with w as (
    select client, platform, campaign_name, campaign_type,
           date_trunc('week', date)::date as week,
           sum(spend) as spend,
           sum(platform_conversions) as platform_conversions,
           sum(ga4_conversions) as ga4_conversions
    from mart_campaign_daily
    where date >= (select max(date) from mart_campaign_daily) - to_days(cast(getvariable('recon_days') as integer))
    group by all
)
select *,
    case when ga4_conversions > 0 then round(platform_conversions / ga4_conversions - 1, 4) end as platform_vs_ga4,
    case
        when campaign_type = 'UNMAPPED'                         then 'Fix: new campaign not set up in reporting'
        when ga4_conversions = 0 and platform_conversions > 0  then 'Fix: not visible in Google Analytics'
        when platform_conversions = 0 and ga4_conversions > 0  then 'Fix: ad platform stopped counting'
        when platform = 'Meta Ads' and platform_conversions / nullif(ga4_conversions, 0) between getvariable('meta_view_low') and getvariable('meta_view_high')
                                                               then 'Normal: Meta also counts people who only saw an ad'
        when abs(platform_conversions / nullif(ga4_conversions, 0) - 1) <= getvariable('match_tolerance')
                                                               then getvariable('match_status')
        else 'Needs a closer look'
    end as status
from w;

create or replace table reconciliation_summary as
select client, platform, campaign_name, campaign_type,
       sum(spend) as spend_8w,
       sum(platform_conversions) as platform_conversions_8w,
       sum(ga4_conversions) as ga4_conversions_8w,
       round(sum(platform_conversions) / nullif(sum(ga4_conversions), 0) - 1, 4) as platform_vs_ga4,
       mode(status) as typical_status,
       count(*) filter (where status like 'Fix:%' or status = 'Needs a closer look') as weeks_needing_action
from reconciliation_weekly
group by all
order by weeks_needing_action desc, spend_8w desc;
