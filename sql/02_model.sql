-- 02 MODEL: clean, deduplicated facts joined through the campaign mapping.

-- Meta re-syncs can deliver the same day twice; keep the latest sync per date x campaign.
create or replace view int_meta_ads as
select * exclude (rn) from (
    select *, row_number() over (partition by date, client, campaign_name order by synced_at desc) as rn
    from stg_meta_ads_raw
) where rn = 1;

create or replace table fct_ads_daily as
select date, client, platform, campaign_name, spend, impressions, clicks,
       platform_conversions, platform_conversion_value
from stg_google_ads
union all
select date, client, platform, campaign_name, spend, impressions, clicks,
       platform_conversions, platform_conversion_value
from int_meta_ads;

-- GA4 paid traffic mapped back to ad campaigns through utm_campaign.
create or replace table fct_ga4_paid_daily as
select g.date, g.client, m.platform, m.campaign_name, g.source_medium, g.utm_campaign,
       g.sessions, g.ga4_conversions, g.ga4_revenue
from stg_ga4 g
join seed_campaign_mapping m
  on m.client = g.client and m.utm_campaign = g.utm_campaign;

-- Campaign x day mart: platform numbers next to GA4 numbers, with a common "value" definition.
--   e-commerce: value = revenue;  lead gen: value = conversions x value per lead
create or replace table mart_campaign_daily as
select
    a.date, a.client, a.platform, a.campaign_name,
    coalesce(m.campaign_type, 'UNMAPPED')                                   as campaign_type,
    a.spend, a.impressions, a.clicks,
    a.platform_conversions,
    coalesce(g.ga4_conversions, 0)                                          as ga4_conversions,
    case when c.business_model = 'ecommerce' then a.platform_conversion_value
         else a.platform_conversions * c.value_per_lead_usd end             as platform_value,
    case when c.business_model = 'ecommerce' then coalesce(g.ga4_revenue, 0)
         else coalesce(g.ga4_conversions, 0) * c.value_per_lead_usd end     as ga4_value,
    p.planned_budget_usd                                                    as monthly_budget,
    c.business_model
from fct_ads_daily a
left join seed_campaign_mapping m using (client, platform, campaign_name)
left join fct_ga4_paid_daily g    using (date, client, platform, campaign_name)
left join seed_clients c          using (client)
left join seed_media_plan p
  on p.client = a.client and p.month = strftime(a.date, '%Y-%m');
