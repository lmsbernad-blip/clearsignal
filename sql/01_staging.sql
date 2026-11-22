-- 01 STAGING: one view per source, renamed to a common vocabulary. No business logic yet.

create or replace table seed_campaign_mapping as select * from read_csv_auto('data/seeds/campaign_mapping.csv', header = true);
create or replace table seed_media_plan      as select * from read_csv_auto('data/seeds/media_plan.csv', header = true);
create or replace table seed_clients         as select * from read_csv_auto('data/seeds/clients.csv', header = true);

-- Google Ads: two connectors feed this file; one sends Cost in dollars, the other cost_micros.
create or replace view stg_google_ads as
select
    cast("Date" as date)                                                   as date,
    regexp_replace("Account name", ' - Google Ads$', '')                   as client,
    'Google Ads'                                                           as platform,
    "Campaign name"                                                        as campaign_name,
    coalesce(try_cast("Cost" as double), try_cast(cost_micros as double) / 1e6) as spend,
    "Cost" is null and cost_micros is not null                             as spend_from_micros,
    "Impressions"                                                          as impressions,
    "Clicks"                                                               as clicks,
    "Conversions"                                                          as platform_conversions,
    "Conv. value"                                                          as platform_conversion_value,
    "Currency"                                                             as currency
from read_csv_auto('data/raw/google_ads_campaign_daily.csv', header = true);

-- Meta Ads: raw rows kept as-is so QA can see re-sync duplicates; deduped in the next layer.
create or replace view stg_meta_ads_raw as
select
    cast(date_start as date)                                               as date,
    regexp_replace(account_name, ' - Meta$', '')                           as client,
    'Meta Ads'                                                             as platform,
    campaign_name,
    spend,
    impressions,
    inline_link_clicks                                                     as clicks,
    purchases_7d_click_1d_view + leads_7d_click_1d_view                    as platform_conversions,
    purchase_value                                                         as platform_conversion_value,
    'USD'                                                                  as currency,
    account_timezone,
    cast(_synced_at as timestamp)                                          as synced_at
from read_csv_auto('data/raw/meta_ads_insights.csv', header = true);

-- GA4: dates arrive as YYYYMMDD strings; property name carries the client.
create or replace view stg_ga4 as
select
    strptime(cast(date as varchar), '%Y%m%d')::date                        as date,
    regexp_replace(property, ' GA4$', '')                                  as client,
    "sessionSourceMedium"                                                  as source_medium,
    "sessionCampaignName"                                                  as utm_campaign,
    sessions,
    "keyEvents"                                                            as ga4_conversions,
    "purchaseRevenue"                                                      as ga4_revenue
from read_csv_auto('data/raw/ga4_traffic_acquisition.csv', header = true, types = {'date': 'VARCHAR'});
