"""Single place for ClearSignal's paths and business thresholds.

The SQL files read the thresholds through DuckDB variables (see `sql_variables()`), so the
numbers in the data checks, the reconciliation and the app always agree.
"""

from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
DB_PATH = DATA_DIR / "warehouse.duckdb"

# Input files, relative to the project (or test) root. The SQL reads them by these paths.
RAW_FILES = {
    "google_ads": "data/raw/google_ads_campaign_daily.csv",
    "meta_ads": "data/raw/meta_ads_insights.csv",
    "ga4": "data/raw/ga4_traffic_acquisition.csv",
}
SEED_FILES = {
    "campaign_mapping": "data/seeds/campaign_mapping.csv",
    "media_plan": "data/seeds/media_plan.csv",
    "clients": "data/seeds/clients.csv",
}

# Tables the app is allowed to read. Anything else is refused (no dynamic SQL from names).
APP_TABLES = ("mart_campaign_daily", "qa_results", "reconciliation_summary", "reconciliation_weekly")
REQUIRED_TABLES = (*APP_TABLES, "fct_ads_daily", "fct_ga4_paid_daily", "data_test_results")

# ----------------------------------------------------------------------------- reconciliation
MATCH_TOLERANCE = 0.20  # platform within ±20% of GA4 counts as a match
META_VIEW_BAND = (1.15, 1.70)  # Meta 7-day click / 1-day view: 15-70% above GA4 is expected
RECON_WEEKS = 8
MATCH_STATUS = f"Matches (within {MATCH_TOLERANCE:.0%})"
RECON_STATUSES = (
    MATCH_STATUS,
    "Normal: Meta also counts people who only saw an ad",
    "Fix: not visible in Google Analytics",
    "Fix: new campaign not set up in reporting",
    "Fix: ad platform stopped counting",
    "Needs a closer look",
)

# ----------------------------------------------------------------------------- campaign types
# Every campaign_type allowed in campaign_mapping.csv. Campaigns missing from the mapping become UNMAPPED.
CAMPAIGN_TYPES = (
    "Search - Brand",
    "Search - Non-brand",
    "Search - Seasonal",
    "Shopping",
    "Performance Max",
    "Paid Social - Prospecting",
    "Paid Social - Retargeting",
    "Paid Social - Lead Gen",
)
QA_SEVERITIES = ("High", "Medium")

# ----------------------------------------------------------------------------- budget pacing
PACING_BAND = (0.85, 1.10)  # month-to-date pace inside this band is "on track"
PACING_HIGH_SEVERITY = 0.25  # more than 25% off plan is a High issue

# ----------------------------------------------------------------------------- tracking break
TRACKING_BREAK_MIN_DAYS = 2
TRACKING_BREAK_MIN_SPEND_SHARE = 0.3  # only days with real spend (vs the campaign's median)

# ----------------------------------------------------------------------------- optimizer
FIT_DAYS = 60  # response curves are fit on the last 60 days
MIN_FIT_DAYS = 20  # a channel needs this many usable days to get a curve
ELASTICITY_CLIP = (0.2, 0.95)
MIN_MULT = 0.7  # each channel keeps at least 70% of today's spend
MAX_MULT = 1.5  # ...and gets at most 150%
BRAND_CAMPAIGN_TYPE = "Search - Brand"
BRAND_MAX_MULT = 1.10  # brand search reaches only people already searching: at most +10%
OPTIMIZER_STEPS = 400

# ----------------------------------------------------------------------------- Claude
DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"


def sql_variables() -> dict[str, float | int | str | tuple[str, ...]]:
    """Thresholds passed to the SQL files as DuckDB variables (read with getvariable('name'))."""
    return {
        "match_tolerance": MATCH_TOLERANCE,
        "match_status": MATCH_STATUS,
        "meta_view_low": META_VIEW_BAND[0],
        "meta_view_high": META_VIEW_BAND[1],
        "recon_days": RECON_WEEKS * 7 - 1,
        "pacing_low": PACING_BAND[0],
        "pacing_high": PACING_BAND[1],
        "pacing_high_severity": PACING_HIGH_SEVERITY,
        "tracking_break_min_days": TRACKING_BREAK_MIN_DAYS,
        "tracking_break_min_spend_share": TRACKING_BREAK_MIN_SPEND_SHARE,
        "campaign_types": CAMPAIGN_TYPES,
        "recon_statuses": RECON_STATUSES,
        "qa_severities": QA_SEVERITIES,
    }
