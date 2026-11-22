# Case study: "Why does Meta say 152 leads when your report says zero?"

**Client:** B2B SaaS · **Campaign:** `B2B_FB_Retargeting_US` · **Period:** last 8 weeks

## The question
The client's media buyer sees 152 leads in Meta Ads Manager for the retargeting campaign. The agency dashboard shows **0 GA4 leads** and a ROAS of 0, so the campaign looks like the obvious one to pause.

## Investigation (SQL in `sql/`)

**1. Is the campaign in the mapping?** Yes, but its `utm_campaign` is blank.
```sql
select * from seed_campaign_mapping where campaign_name = 'B2B_FB_Retargeting_US';
```

**2. Where did its traffic go in GA4?** Look for Facebook traffic that isn't tagged as paid:
```sql
select source_medium, utm_campaign, sum(sessions) as sessions, sum(ga4_conversions) as conversions
from stg_ga4
where client = 'B2B SaaS' and source_medium ilike '%facebook%'
group by all;
```
Result: GA4 has **104 leads** (plus the campaign's sessions) under `facebook.com / referral`, campaign `(referral)`. The ads have no UTM parameters, so GA4 treated paid clicks as an ordinary referral.

**3. Is this the whole gap?** 104 GA4 leads vs 152 Meta leads = Meta reports **+46%**. The client's other Meta campaign (properly tagged) shows **+49%** over the same weeks, in line with Meta's 7-day click / 1-day view attribution. So the remaining gap is the expected attribution difference, not a second problem.

## Finding
| | Before fix | After fix |
|---|---|---|
| GA4 leads credited | 0 | 104 |
| Value (104 × $650 per lead) | $0 | $67,600 |
| ROAS on $14,500 spend | 0.00 | **≈ 4.7** |

The campaign the report said to pause is one of the client's **most efficient**.

## Actions
1. **Media buyer:** add the UTM template to every ad in the campaign (`utm_source=facebook&utm_medium=paid_social&utm_campaign=b2b_fb_retargeting_us`).
2. **Analyst:** add the utm_campaign to `campaign_mapping.csv`; annotate the dashboard for the affected weeks.
3. **Prevention:** QA checks 4 (*Missing UTMs*) and 5 (*No GA4 match*) now catch this on day one for every client.

## Other findings from the same onboarding
- **DTC Skincare, Meta, Nov 8–9:** a connector re-sync delivered both days twice. Raw spend $4,443 vs actual **$2,221**. Deduplicated on `_synced_at`.
- **DTC Skincare, Meta, Nov 15–17:** spend continued but Meta purchases dropped to 0 while GA4 still recorded sales. That's a pixel / Conversions API outage, not a performance drop.
- **Home Services, Google Ads:** since Oct 1, a second connector sends `cost_micros` instead of `Cost`. Converted ÷ 1,000,000. Both connectors should use one field.
- **DTC_GS_Holiday_US:** launched Nov 10 without a mapping row, so its results were missing from GA4 reporting.
