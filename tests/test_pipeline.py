"""Pipeline tests: generate the demo data, build the warehouse in a temp folder, check what the SQL finds."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from conftest import query

import config
import warehouse

PLANTED = ["duplicate_rows", "cost_in_micros", "unmapped_campaign", "missing_utms", "no_ga4_match", "tracking_break"]


def rows(qa: pd.DataFrame, check_id: str) -> pd.DataFrame:
    return qa[qa["check_id"] == check_id]


# ----------------------------------------------------------------------------- planted problems are found
def test_duplicate_meta_days(qa):
    dup = rows(qa, "duplicate_rows")
    assert set(dup["client"]) == {"DTC Skincare"}
    assert set(dup["object"]) == {"DTC_FB_Prospecting_US", "DTC_FB_Retargeting_US"}
    assert (dup["rows_affected"] == 2).all()
    assert (dup["severity"] == "High").all()
    assert dup["usd_at_risk"].sum() == pytest.approx(2221.35, abs=0.01)
    assert dup["detail"].str.contains("Nov 8 to Nov 9").all()


def test_duplicates_removed_from_facts(demo_db):
    raw = query(demo_db, "select count(*) n from stg_meta_ads_raw")["n"].iloc[0]
    deduped = query(demo_db, "select count(*) n from fct_ads_daily where platform = 'Meta Ads'")["n"].iloc[0]
    assert raw - deduped == 4  # 2 campaigns × 2 days
    grain = query(
        demo_db,
        """select count(*) n from (select date, client, platform, campaign_name
                               from fct_ads_daily group by all having count(*) > 1)""",
    )
    assert grain["n"].iloc[0] == 0


def test_cost_in_micros(qa, demo_db):
    m = rows(qa, "cost_in_micros")
    assert len(m) == 1
    assert m.iloc[0]["client"] == "Home Services" and m.iloc[0]["severity"] == "Medium"
    check = query(
        demo_db,
        """select max(abs(s.spend - try_cast(r.cost_micros as double) / 1e6)) err, count(*) n
                              from stg_google_ads s
                              join read_csv_auto(? , header = true) r
                                on cast(r."Date" as date) = s.date and r."Campaign name" = s.campaign_name
                              where s.spend_from_micros""",
        [str(Path(demo_db).parent / config.RAW_FILES["google_ads"])],
    )
    assert check["n"].iloc[0] > 0 and check["err"].iloc[0] < 0.005
    assert query(demo_db, "select max(spend) m from fct_ads_daily")["m"].iloc[0] < 10_000  # no million-x spend


def test_unmapped_holiday_campaign(qa, demo_db):
    u = rows(qa, "unmapped_campaign")
    assert u["object"].tolist() == ["DTC_GS_Holiday_US"]
    types = query(
        demo_db, "select distinct campaign_type from mart_campaign_daily where campaign_name = 'DTC_GS_Holiday_US'"
    )
    assert types["campaign_type"].tolist() == ["UNMAPPED"]


def test_missing_utms_and_no_ga4_match(qa):
    utm = rows(qa, "missing_utms")
    assert utm["client"].tolist() == ["B2B SaaS"]
    assert "leads from Facebook" in utm.iloc[0]["detail"]
    nomatch = rows(qa, "no_ga4_match")
    assert nomatch["object"].tolist() == ["B2B_FB_Retargeting_US"]
    assert "Add tracking tags" in nomatch.iloc[0]["action"]


def test_meta_tracking_outage(qa):
    tb = rows(qa, "tracking_break")
    assert set(tb["object"]) == {"DTC_FB_Prospecting_US", "DTC_FB_Retargeting_US"}
    assert (tb["client"] == "DTC Skincare").all()
    assert (tb["rows_affected"] == 3).all()
    assert tb["detail"].str.contains("From Nov 15 to Nov 17").all()
    assert tb["title"].eq("Ad platform stopped counting sales").all()


def test_home_services_overspend(qa):
    pacing = rows(qa, "budget_pacing").set_index("client")
    hs = pacing.loc["Home Services"]
    assert hs["title"] == "Spending ahead of budget" and hs["severity"] == "High"
    assert "66% more than planned" in hs["detail"]


def test_no_freshness_issues_on_demo_data(qa):
    assert rows(qa, "freshness").empty


def test_every_check_row_is_readable(qa):
    assert not qa[["check_id", "title", "severity", "client", "detail", "action"]].isna().any().any()
    assert set(qa["severity"]) <= {"High", "Medium"}


def test_pinned_high_issue_count(qa):
    # The header pill for DTC Skincare: 2 duplicate + 1 unmapped + 2 tracking break.
    assert int(((qa["client"] == "DTC Skincare") & (qa["severity"] == "High")).sum()) == 5


# ----------------------------------------------------------------------------- reconciliation
ALLOWED_STATUS = {
    config.MATCH_STATUS,
    "Normal: Meta also counts people who only saw an ad",
    "Fix: not visible in Google Analytics",
    "Fix: new campaign not set up in reporting",
    "Fix: ad platform stopped counting",
    "Needs a closer look",
}


def test_reconciliation_statuses(demo_db):
    weekly = query(demo_db, "select * from reconciliation_weekly")
    summary = query(demo_db, "select * from reconciliation_summary").set_index("campaign_name")
    assert set(weekly["status"]) <= ALLOWED_STATUS
    assert set(summary["typical_status"]) <= ALLOWED_STATUS
    assert weekly["week"].nunique() <= config.RECON_WEEKS + 1  # 8 weeks; the window can clip a partial first week
    assert summary.loc["B2B_FB_Retargeting_US", "typical_status"] == "Fix: not visible in Google Analytics"
    assert summary.loc["DTC_GS_Holiday_US", "typical_status"] == "Fix: new campaign not set up in reporting"


def test_spend_is_preserved_into_the_mart(demo_db):
    totals = query(
        demo_db,
        """select (select round(sum(spend), 2) from mart_campaign_daily) mart,
                                      (select round(sum(spend), 2) from stg_google_ads)
                                    + (select round(sum(spend), 2) from int_meta_ads) src""",
    )
    assert totals["mart"].iloc[0] == pytest.approx(totals["src"].iloc[0], abs=0.01)


# ----------------------------------------------------------------------------- negative test: clean data
def test_clean_data_raises_none_of_the_planted_problems(clean_root):
    qa = query(clean_root / "warehouse.duckdb", "select * from qa_results")
    for check_id in PLANTED:
        assert rows(qa, check_id).empty, f"{check_id} fired on clean data:\n{rows(qa, check_id)}"
    assert "Home Services" not in set(rows(qa, "budget_pacing")["client"])
    assert rows(qa, "freshness").empty


def test_clean_data_reconciles(clean_root):
    summary = query(clean_root / "warehouse.duckdb", "select * from reconciliation_summary")
    assert not summary["typical_status"].str.startswith("Fix:").any()


# ----------------------------------------------------------------------------- build safety
def test_generator_is_deterministic(demo_root, tmp_path):
    import generate_data

    generate_data.generate(tmp_path)
    for rel in [*config.RAW_FILES.values(), *config.SEED_FILES.values()]:
        assert (tmp_path / rel).read_bytes() == (demo_root / rel).read_bytes(), rel


def test_failed_build_keeps_previous_warehouse(demo_root, tmp_path):
    import shutil

    shutil.copytree(demo_root / "data", tmp_path / "data")
    db = tmp_path / "warehouse.duckdb"
    warehouse.build(db_path=db, root=tmp_path)
    (tmp_path / config.RAW_FILES["meta_ads"]).unlink()
    with pytest.raises(warehouse.WarehouseError, match="Input file is missing: data/raw/meta_ads_insights.csv"):
        warehouse.build(db_path=db, root=tmp_path)
    assert warehouse.missing_tables(db) == []
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        (lambda p: p.write_text(""), "empty or has no header"),
        (lambda p: p.write_text(p.read_text().replace(",spend,", ",amount_spent,", 1)), "missing a required column"),
    ],
)
def test_bad_input_gives_readable_error(demo_root, tmp_path, damage, message):
    import shutil

    shutil.copytree(demo_root / "data", tmp_path / "data")
    damage(tmp_path / config.RAW_FILES["meta_ads"])
    with pytest.raises(warehouse.WarehouseError, match=message):
        warehouse.build(db_path=tmp_path / "w.duckdb", root=tmp_path)


def test_read_table_refuses_unknown_names(demo_db):
    with pytest.raises(ValueError):
        warehouse.read_table("qa_results; drop table qa_results", demo_db)
    assert len(warehouse.read_table("qa_results", demo_db)) > 0
