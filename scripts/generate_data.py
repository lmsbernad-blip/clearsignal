"""
Generate a realistic client-onboarding scenario: three agency clients whose Google Ads, Meta Ads and GA4
data arrive as connector exports (Supermetrics / Improvado style), each in its own schema.

Real client data is confidential, so this is a seeded simulation. It plants the problems an
agency analyst actually meets during onboarding, so the SQL checks have something real to find:

  1. Duplicate Meta rows after a connector re-sync (DTC Skincare, Nov 8-9)
  2. Google Ads cost arriving as cost_micros from a second connector (Home Services)
  3. A Meta campaign with no UTM tags, so GA4 files its traffic as facebook.com / referral (B2B SaaS)
  4. A new Google Ads campaign launched without being added to the campaign mapping (DTC Holiday)
  5. A Meta pixel outage: spend continues, platform purchases drop to zero (DTC, Nov 15-17)
  6. A client overspending its monthly media plan (Home Services, November)
Plus normal, expected gaps: Meta's 7-day click / 1-day view attribution over-claims vs GA4,
and Meta accounts report in Pacific time while GA4 properties use Eastern time.

Run:  python scripts/generate_data.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("clearsignal.generate")
ROOT = Path(__file__).resolve().parents[1]
SEED = 7
LF = "\n"  # same bytes on Windows and Linux

DAYS = pd.date_range("2026-06-01", "2026-11-21", freq="D")
D = pd.Timestamp

# client -> (business model, value per conversion USD (lead gen only), monthly budget USD)
CLIENTS = {
    "DTC Skincare": ("ecommerce", None, 90_000),
    "B2B SaaS": ("leadgen", 650, 60_000),
    "Home Services": ("leadgen", 280, 40_000),
}
# campaign, platform, client, campaign type, share of client budget, elasticity, utm_campaign, launch date
CAMPAIGNS = [
    ("DTC_GS_Brand_US", "Google Ads", "DTC Skincare", "Search - Brand", 0.12, 0.85, "dtc_gs_brand_us", None),
    ("DTC_GS_NonBrand_US", "Google Ads", "DTC Skincare", "Search - Non-brand", 0.25, 0.70, "dtc_gs_nonbrand_us", None),
    ("DTC_GSH_AllProducts_US", "Google Ads", "DTC Skincare", "Shopping", 0.20, 0.75, "dtc_gsh_allproducts_us", None),
    (
        "DTC_GS_Holiday_US",
        "Google Ads",
        "DTC Skincare",
        "Search - Seasonal",
        0.08,
        0.70,
        "dtc_gs_holiday_us",
        "2026-11-10",
    ),
    (
        "DTC_FB_Prospecting_US",
        "Meta Ads",
        "DTC Skincare",
        "Paid Social - Prospecting",
        0.25,
        0.60,
        "dtc-meta-prospecting",
        None,
    ),
    (
        "DTC_FB_Retargeting_US",
        "Meta Ads",
        "DTC Skincare",
        "Paid Social - Retargeting",
        0.10,
        0.65,
        "dtc-meta-retargeting",
        None,
    ),
    ("B2B_GS_Brand_US", "Google Ads", "B2B SaaS", "Search - Brand", 0.15, 0.85, "b2b_gs_brand_us", None),
    ("B2B_GS_NonBrand_US", "Google Ads", "B2B SaaS", "Search - Non-brand", 0.45, 0.65, "b2b_gs_nonbrand_us", None),
    ("B2B_FB_LeadGen_US", "Meta Ads", "B2B SaaS", "Paid Social - Lead Gen", 0.28, 0.55, "b2b_fb_leadgen_us", None),
    ("B2B_FB_Retargeting_US", "Meta Ads", "B2B SaaS", "Paid Social - Retargeting", 0.12, 0.60, None, None),  # no UTMs
    (
        "HOME_GS_Services_US",
        "Google Ads",
        "Home Services",
        "Search - Non-brand",
        0.55,
        0.80,
        "home_gs_services_us",
        None,
    ),
    ("HOME_PMAX_Local_US", "Google Ads", "Home Services", "Performance Max", 0.20, 0.70, "home_pmax_local_us", None),
    ("HOME_FB_Leads_US", "Meta Ads", "Home Services", "Paid Social - Lead Gen", 0.25, 0.60, "home_fb_leads_us", None),
]
CTR = {"Google Ads": 0.045, "Meta Ads": 0.011}
CPM = {"Google Ads": 38.0, "Meta Ads": 11.0}
PLATFORM_OVERCLAIM = {"Google Ads": 1.08, "Meta Ads": 1.38}  # platform conversions vs truth
GA4_CAPTURE = 0.94  # consent / ad-blocker loss
AOV = 62.0  # DTC average order value


def generate(root: Path = ROOT) -> dict[str, int]:
    """Write the demo exports to <root>/data/raw and the seeds to <root>/data/seeds. Returns row counts."""
    rng = np.random.default_rng(SEED)
    RAW = Path(root) / "data" / "raw"
    SEEDS = Path(root) / "data" / "seeds"
    RAW.mkdir(parents=True, exist_ok=True)
    SEEDS.mkdir(parents=True, exist_ok=True)

    google, meta, ga4 = [], [], []
    for camp, platform, client, _ctype, share, elast, utm, launch in CAMPAIGNS:
        model, vpc, budget = CLIENTS[client]
        base = budget / 30 * share
        k = (base * rng.uniform(2.5, 5.0) / (AOV if model == "ecommerce" else vpc)) / base**elast
        flights = {i: rng.uniform(0.7, 1.3) for i in range(len(DAYS) // 14 + 2)}
        carry = 0.0
        for i, d in enumerate(DAYS):
            if launch and d < D(launch):
                continue
            wk = 1.0 + (0.10 if d.day_of_week < 5 else -0.15)
            spend = base * flights[i // 14] * wk * rng.normal(1, 0.08)
            if client == "Home Services" and d >= D("2026-11-01"):
                spend *= 1.45  # issue 6: overspend
            true_conv = k * spend**elast * rng.lognormal(0, 0.15)
            impressions = spend / CPM[platform] * 1000
            clicks = impressions * CTR[platform] * rng.normal(1, 0.06)
            p_conv = true_conv * PLATFORM_OVERCLAIM[platform]
            if camp.startswith("DTC_FB") and D("2026-11-15") <= d <= D("2026-11-17"):
                p_conv = 0.0  # issue 5: pixel outage
            p_value = p_conv * AOV * rng.normal(1, 0.04) if model == "ecommerce" else 0.0

            if platform == "Google Ads":
                row = {
                    "Date": d.date(),
                    "Account name": f"{client} - Google Ads",
                    "Campaign name": camp,
                    "Impressions": round(impressions),
                    "Clicks": round(clicks),
                    "Conversions": round(p_conv, 2),
                    "Conv. value": round(p_value, 2),
                    "Currency": "USD",
                }
                if client == "Home Services" and d >= D("2026-10-01"):
                    row["Cost"] = None  # issue 2: second connector sends micros
                    row["cost_micros"] = round(spend * 1_000_000)
                else:
                    row["Cost"] = round(spend, 2)
                google.append(row)
            else:
                row = {
                    "date_start": d.date(),
                    "account_name": f"{client} - Meta",
                    "account_timezone": "America/Los_Angeles",
                    "campaign_name": camp,
                    "spend": round(spend, 2),
                    "impressions": round(impressions),
                    "inline_link_clicks": round(clicks),
                    "purchases_7d_click_1d_view": round(p_conv, 2) if model == "ecommerce" else 0,
                    "leads_7d_click_1d_view": round(p_conv, 2) if model == "leadgen" else 0,
                    "purchase_value": round(p_value, 2),
                    "_synced_at": f"{(d + pd.Timedelta(days=1)).date()}T06:00:00Z",
                }
                meta.append(row)
                if client == "DTC Skincare" and D("2026-11-08") <= d <= D("2026-11-09"):
                    dup = dict(row, _synced_at=f"{(d + pd.Timedelta(days=3)).date()}T06:00:00Z")
                    meta.append(dup)  # issue 1: re-sync duplicates

            # GA4 sees the true conversions it can track; ~12% land on the next day (ET vs PT day boundary for Meta)
            ga4_conv = true_conv * GA4_CAPTURE * rng.normal(1, 0.04)
            shift = 0.12 if platform == "Meta Ads" else 0.0
            today_conv = ga4_conv * (1 - shift) + carry
            carry = ga4_conv * shift
            sessions = clicks * rng.uniform(0.82, 0.92)
            if utm is None:  # issue 3: no UTMs -> referral bucket
                src, gcamp = "facebook.com / referral", "(referral)"
            else:
                src = "google / cpc" if platform == "Google Ads" else "facebook / paid_social"
                gcamp = utm
            ga4.append(
                {
                    "date": d.strftime("%Y%m%d"),
                    "property": f"{client} GA4",
                    "sessionSourceMedium": src,
                    "sessionCampaignName": gcamp,
                    "sessions": round(sessions),
                    "keyEvents": round(today_conv, 1),
                    "purchaseRevenue": round(today_conv * AOV * rng.normal(1, 0.03), 2)
                    if model == "ecommerce"
                    else 0.0,
                }
            )

    # some organic / direct traffic in GA4 so the export looks like a real property
    for client in CLIENTS:
        for d in DAYS:
            for src, s, conv in (("(direct) / (none)", 900, 9), ("google / organic", 1400, 12)):
                c = conv * rng.normal(1, 0.15)
                ga4.append(
                    {
                        "date": d.strftime("%Y%m%d"),
                        "property": f"{client} GA4",
                        "sessionSourceMedium": src,
                        "sessionCampaignName": "(not set)",
                        "sessions": round(s * rng.normal(1, 0.1)),
                        "keyEvents": round(c, 1),
                        "purchaseRevenue": round(c * AOV, 2) if CLIENTS[client][0] == "ecommerce" else 0.0,
                    }
                )

    g = pd.DataFrame(google)[
        [
            "Date",
            "Account name",
            "Campaign name",
            "Cost",
            "cost_micros",
            "Impressions",
            "Clicks",
            "Conversions",
            "Conv. value",
            "Currency",
        ]
    ]
    g.to_csv(RAW / "google_ads_campaign_daily.csv", index=False, lineterminator=LF)
    pd.DataFrame(meta).to_csv(RAW / "meta_ads_insights.csv", index=False, lineterminator=LF)
    pd.DataFrame(ga4).to_csv(RAW / "ga4_traffic_acquisition.csv", index=False, lineterminator=LF)

    # seeds: campaign mapping (maintained by the analyst) and the media plan
    mapping = pd.DataFrame(
        [
            dict(platform=p, campaign_name=c, client=cl, campaign_type=t, utm_campaign=u)
            for c, p, cl, t, _, _, u, launch in CAMPAIGNS
            if c != "DTC_GS_Holiday_US"
        ]
    )  # issue 4
    mapping.to_csv(SEEDS / "campaign_mapping.csv", index=False, lineterminator=LF)
    plan = pd.DataFrame(
        [
            dict(client=c, month=m.strftime("%Y-%m"), planned_budget_usd=b)
            for c, (_, _, b) in CLIENTS.items()
            for m in pd.date_range("2026-06-01", "2026-11-01", freq="MS")
        ]
    )
    plan.to_csv(SEEDS / "media_plan.csv", index=False, lineterminator=LF)
    clients = pd.DataFrame(
        [
            dict(client=c, business_model=m, value_per_lead_usd=v, ga4_timezone="America/New_York")
            for c, (m, v, _) in CLIENTS.items()
        ]
    )
    clients.to_csv(SEEDS / "clients.csv", index=False, lineterminator=LF)

    log.info("google_ads rows: %s | meta rows: %s | ga4 rows: %s", f"{len(g):,}", f"{len(meta):,}", f"{len(ga4):,}")
    return {"google_ads": len(g), "meta_ads": len(meta), "ga4": len(ga4)}


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Generate the seeded ClearSignal demo data.")
    parser.add_argument("--root", type=Path, default=ROOT, help="folder to write data/raw and data/seeds into")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    generate(args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
