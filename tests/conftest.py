"""Shared fixtures: demo data and warehouses built in temporary folders (the real data/ is never touched)."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

import config  # noqa: E402
import generate_data  # noqa: E402
import warehouse  # noqa: E402

RAW = Path("data/raw")
SEEDS = Path("data/seeds")


def _write(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, lineterminator="\n")


def remove_planted_problems(root: Path) -> None:
    """Edit the generated demo files in `root` so that none of the six planted problems remain."""
    raw, seeds = root / RAW, root / SEEDS

    # 1. Meta re-sync duplicates: keep only the latest sync per day and campaign.
    meta = pd.read_csv(raw / "meta_ads_insights.csv")
    meta = meta.sort_values("_synced_at").drop_duplicates(["date_start", "campaign_name"], keep="last")
    # 5. Meta pixel outage (DTC, Nov 15-17): give those days normal purchase counts again.
    outage = meta["campaign_name"].str.startswith("DTC_FB") & meta["date_start"].between("2026-11-15", "2026-11-17")
    meta.loc[outage, "purchases_7d_click_1d_view"] = 40.0
    meta.loc[outage, "purchase_value"] = 2480.0
    _write(meta.sort_values(["campaign_name", "date_start"]), raw / "meta_ads_insights.csv")

    # 2. Cost in micros (Home Services): convert back to the normal Cost column.
    google = pd.read_csv(raw / "google_ads_campaign_daily.csv")
    micros = google["Cost"].isna() & google["cost_micros"].notna()
    google.loc[micros, "Cost"] = (google.loc[micros, "cost_micros"] / 1e6).round(2)
    google["cost_micros"] = np.nan
    _write(google, raw / "google_ads_campaign_daily.csv")

    # 3. Missing UTMs (B2B retargeting): GA4 now sees the campaign as paid social with its own utm_campaign.
    ga4 = pd.read_csv(raw / "ga4_traffic_acquisition.csv", dtype={"date": str})
    referral = (ga4["property"] == "B2B SaaS GA4") & (ga4["sessionSourceMedium"] == "facebook.com / referral")
    ga4.loc[referral, "sessionSourceMedium"] = "facebook / paid_social"
    ga4.loc[referral, "sessionCampaignName"] = "b2b_fb_retargeting_us"
    _write(ga4, raw / "ga4_traffic_acquisition.csv")

    # 3 + 4. Mapping: add the holiday campaign and the retargeting campaign's utm_campaign.
    mapping = pd.read_csv(seeds / "campaign_mapping.csv")
    mapping.loc[mapping["campaign_name"] == "B2B_FB_Retargeting_US", "utm_campaign"] = "b2b_fb_retargeting_us"
    holiday = {
        "platform": "Google Ads",
        "campaign_name": "DTC_GS_Holiday_US",
        "client": "DTC Skincare",
        "campaign_type": "Search - Seasonal",
        "utm_campaign": "dtc_gs_holiday_us",
    }
    mapping = pd.concat([mapping, pd.DataFrame([holiday])], ignore_index=True)
    _write(mapping, seeds / "campaign_mapping.csv")

    # 6. Home Services overspend: the approved November plan matches the actual pace of spend.
    nov_google = google[
        google["Account name"].str.startswith("Home Services") & google["Date"].str.startswith("2026-11")
    ]
    nov_meta = meta[meta["account_name"].str.startswith("Home Services") & meta["date_start"].str.startswith("2026-11")]
    days_so_far = pd.to_datetime(nov_google["Date"]).dt.day.max()
    projected = (nov_google["Cost"].sum() + nov_meta["spend"].sum()) / days_so_far * 30
    plan = pd.read_csv(seeds / "media_plan.csv")
    plan.loc[(plan["client"] == "Home Services") & (plan["month"] == "2026-11"), "planned_budget_usd"] = round(
        projected
    )
    _write(plan, seeds / "media_plan.csv")


@pytest.fixture(scope="session")
def demo_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A temp folder with freshly generated demo data and a built warehouse at <root>/warehouse.duckdb."""
    root = tmp_path_factory.mktemp("demo")
    generate_data.generate(root)
    warehouse.build(db_path=root / "warehouse.duckdb", root=root)
    return root


@pytest.fixture(scope="session")
def clean_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Like demo_root, but with every planted problem removed before the build."""
    root = tmp_path_factory.mktemp("clean")
    generate_data.generate(root)
    remove_planted_problems(root)
    warehouse.build(db_path=root / "warehouse.duckdb", root=root)
    return root


@pytest.fixture(scope="session")
def demo_db(demo_root: Path) -> Path:
    return demo_root / "warehouse.duckdb"


def query(db: Path, sql: str, params: list | None = None) -> pd.DataFrame:
    """Run a read-only query against a test warehouse."""
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql, params or []).df()


@pytest.fixture(scope="session")
def qa(demo_db: Path) -> pd.DataFrame:
    return query(demo_db, "select * from qa_results")


@pytest.fixture(scope="session")
def mart(demo_db: Path) -> pd.DataFrame:
    import analytics

    return analytics.load(demo_db)


@pytest.fixture
def use_demo_warehouse(demo_db: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app and helpers at the temp warehouse for the duration of a test."""
    monkeypatch.setattr(config, "DB_PATH", demo_db)
    return demo_db
