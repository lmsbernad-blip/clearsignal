"""Input contracts (before the build) and data tests (after the build)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
from conftest import query

import config
import contracts
import warehouse


@pytest.fixture
def copy_root(demo_root: Path, tmp_path: Path) -> Path:
    """A private, editable copy of the demo data."""
    shutil.copytree(demo_root / "data", tmp_path / "data")
    return tmp_path


def edit_csv(root: Path, key: str, change: Callable[[pd.DataFrame], pd.DataFrame]) -> None:
    rel = config.RAW_FILES.get(key) or config.SEED_FILES[key]
    path = root / rel
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    change(df).to_csv(path, index=False, lineterminator="\n")


def set_cell(col: str, value: str, row: int = 0) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def change(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[row, col] = value
        return df

    return change


# ----------------------------------------------------------------------------- contracts pass on good data
def test_demo_data_meets_every_contract(demo_root):
    contracts.validate_inputs(demo_root)


def test_build_records_passing_data_tests(demo_db):
    results = query(demo_db, "select * from data_test_results")
    assert len(results) == 9
    assert (results["failures"] == 0).all(), results


# ----------------------------------------------------------------------------- contracts catch bad input
@pytest.mark.parametrize(
    ("key", "change", "message"),
    [
        ("meta_ads", set_cell("spend", "-12.5"), "meta_ads_insights.csv: spend is negative in row 2"),
        ("google_ads", set_cell("Clicks", "-1", row=4), "Clicks is negative in row 6"),
        ("ga4", set_cell("sessions", "-3"), "sessions is negative"),
        ("google_ads", set_cell("Currency", "EUR"), "Currency must be one of USD; found 'EUR'"),
        ("google_ads", set_cell("Date", "21/11/2026"), "Date has values that aren't valid dates"),
        ("meta_ads", set_cell("date_start", "2031-01-01"), "date_start is outside 2015-01-01 to today"),
        ("ga4", set_cell("date", "2014-12-31".replace("-", "")), "date is outside"),
        ("meta_ads", set_cell("_synced_at", "yesterday"), "_synced_at has values that aren't valid dates"),
        ("google_ads", set_cell("Impressions", "lots"), "Impressions has values that aren't numbers"),
        ("google_ads", lambda df: df.assign(Cost="", cost_micros=""), "both Cost and cost_micros are blank"),
        (
            "meta_ads",
            lambda df: df.drop(columns=["inline_link_clicks"]),
            "missing a required column: inline_link_clicks",
        ),
        ("meta_ads", lambda df: df.iloc[0:0], "has a header but no rows"),
        ("campaign_mapping", set_cell("platform", "TikTok Ads"), "platform must be one of Google Ads, Meta Ads"),
        ("campaign_mapping", set_cell("campaign_type", "Search - Brnd"), "campaign_type must be one of"),
        ("campaign_mapping", lambda df: pd.concat([df, df.iloc[[0]]]), "platform + campaign_name must be unique"),
        ("clients", set_cell("business_model", "retail"), "business_model must be one of ecommerce, leadgen"),
        ("clients", set_cell("value_per_lead_usd", "", row=1), "lead-gen clients need a value_per_lead_usd above 0"),
        ("media_plan", set_cell("month", "Nov 2026"), "month has values that aren't valid dates"),
        ("media_plan", set_cell("planned_budget_usd", "-90000"), "planned_budget_usd is negative"),
    ],
)
def test_contract_violation_stops_the_build(copy_root, key, change, message):
    edit_csv(copy_root, key, change)
    with pytest.raises(contracts.ContractError, match=message.replace("(", r"\(").replace("+", r"\+")):
        contracts.validate_inputs(copy_root)
    with pytest.raises(warehouse.WarehouseError, match="problem"):
        warehouse.build(db_path=copy_root / "w.duckdb", root=copy_root)
    assert not (copy_root / "w.duckdb").exists()


def test_all_problems_are_reported_together(copy_root):
    edit_csv(copy_root, "meta_ads", set_cell("spend", "-1"))
    edit_csv(copy_root, "google_ads", set_cell("Currency", "GBP"))
    (copy_root / config.RAW_FILES["ga4"]).unlink()
    with pytest.raises(contracts.ContractError) as err:
        contracts.validate_inputs(copy_root)
    text = str(err.value)
    assert text.startswith("3 problems in the input files")
    assert "Input file is missing: data/raw/ga4_traffic_acquisition.csv" in text


def test_row_examples_are_capped(copy_root):
    edit_csv(copy_root, "meta_ads", lambda df: df.assign(spend="-1"))
    with pytest.raises(contracts.ContractError, match=r"rows 2, 3, 4 and \d+ more"):
        contracts.validate_inputs(copy_root)


def test_not_a_csv(copy_root):
    (copy_root / config.RAW_FILES["ga4"]).write_bytes(b"\xff\xfe\x00garbage\x00\n\x00")
    with pytest.raises(contracts.ContractError, match="ga4_traffic_acquisition.csv"):
        contracts.validate_inputs(copy_root)


# ----------------------------------------------------------------------------- data tests stop a bad build
def test_failing_data_test_blocks_the_warehouse(copy_root, tmp_path):
    """A rule broken inside the pipeline (not in the inputs) must stop the build and keep the old warehouse."""
    db = copy_root / "w.duckdb"
    warehouse.build(db_path=db, root=copy_root)
    sql = tmp_path / "sql"
    shutil.copytree(config.SQL_DIR, sql)
    # Simulate a pipeline bug: the model layer stops deduplicating Meta re-syncs.
    model = (sql / "02_model.sql").read_text(encoding="utf-8").replace(") where rn = 1;", ");")
    (sql / "02_model.sql").write_text(model, encoding="utf-8")
    with pytest.raises(warehouse.WarehouseError, match="fct_ads_daily_unique_grain: 4 failing row") as err:
        warehouse.build(db_path=db, root=copy_root, sql_dir=sql)
    assert "spend_preserved_to_the_cent" not in str(err.value)  # mart still matches its (wrong) sources
    assert query(db, "select count(*) n from fct_ads_daily")["n"].iloc[0] == 2100  # previous build kept


def test_missing_data_test_file_is_an_error(copy_root, tmp_path):
    sql = tmp_path / "sql"
    shutil.copytree(config.SQL_DIR, sql)
    (sql / "05_data_tests.sql").write_text(
        "create or replace table data_test_results as select 'x' as test_name, "
        "0 as failures, 'd' as description where false;"
    )
    with pytest.raises(warehouse.WarehouseError, match="No data tests ran"):
        warehouse.build(db_path=copy_root / "w.duckdb", root=copy_root, sql_dir=sql)
