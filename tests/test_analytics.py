"""Unit tests for app/analytics.py on small hand-made data with known answers."""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd
import pytest

import config
from analytics import (
    budget_pacing,
    channel_table,
    fit_response_curves,
    kpis,
    nouns,
    optimize_budget,
    pct_change,
    period_windows,
    plan_uplift,
    usd,
    weekly_summary,
)

NO_NAN = re.compile(r"\b(nan|inf)\b", re.IGNORECASE)


def tiny(**overrides) -> pd.DataFrame:
    """Two campaign-days with round numbers."""
    data = {
        "spend": [100.0, 300.0],
        "impressions": [1000, 1000],
        "clicks": [10, 30],
        "ga4_conversions": [2.0, 3.0],
        "ga4_value": [400.0, 800.0],
        "platform_conversions": [3.0, 5.0],
        "platform_value": [500.0, 1100.0],
    }
    data.update(overrides)
    return pd.DataFrame(data)


# ----------------------------------------------------------------------------- kpis
class TestKpis:
    def test_ga4_math(self):
        k = kpis(tiny())
        assert k["spend"] == 400
        assert k["conversions"] == 5
        assert k["value"] == 1200
        assert k["roas"] == pytest.approx(3.0)  # 1200 / 400
        assert k["cpa"] == pytest.approx(80.0)  # 400 / 5
        assert k["ctr"] == pytest.approx(0.02)  # 40 / 2000

    def test_platform_basis(self):
        k = kpis(tiny(), basis="platform")
        assert k["conversions"] == 8
        assert k["roas"] == pytest.approx(4.0)  # 1600 / 400
        assert k["cpa"] == pytest.approx(50.0)  # 400 / 8

    def test_zero_denominators_give_nan_not_inf(self):
        k = kpis(tiny(spend=[0.0, 0.0], ga4_conversions=[0.0, 0.0], impressions=[0, 0]))
        assert math.isnan(k["roas"]) and math.isnan(k["cpa"]) and math.isnan(k["ctr"])

    def test_empty_frame(self):
        k = kpis(tiny().iloc[0:0])
        assert k["spend"] == 0 and math.isnan(k["roas"])

    def test_unknown_basis_rejected(self):
        with pytest.raises(ValueError):
            kpis(tiny(), basis="facebook")


# ----------------------------------------------------------------------------- helpers
@pytest.mark.parametrize(
    ("value", "expected"),
    [(812.4, "$812"), (45_300, "$45.3K"), (1_250_000, "$1.2M"), (-2_000, "$-2.0K"), (float("nan"), "-"), (None, "-")],
)
def test_usd(value, expected):
    assert usd(value) == expected


def test_pct_change():
    assert pct_change(110, 100) == pytest.approx(0.10)
    assert math.isnan(pct_change(5, 0))


def test_nouns_follow_business_model():
    assert nouns(pd.DataFrame({"business_model": ["ecommerce"]}))["results"] == "sales"
    assert nouns(pd.DataFrame({"business_model": ["leadgen"]}))["results"] == "leads"


def test_period_windows_do_not_overlap():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=20)})
    cur, prev = period_windows(df, df["date"].max(), 7)
    assert len(cur) == 7 and len(prev) == 7
    assert cur["date"].min() > prev["date"].max()


def test_channel_table_math_and_zero_safety():
    df = tiny().assign(channel=["A", "B"])
    t = channel_table(df).set_index("channel")
    assert t.loc["B", "roas"] == pytest.approx(800 / 300)
    assert t.loc["A", "over_attribution"] == pytest.approx(3 / 2 - 1)
    assert t["share_of_spend"].sum() == pytest.approx(1.0)
    zero = channel_table(tiny(ga4_conversions=[0.0, 0.0]).assign(channel=["A", "B"]))
    assert not np.isinf(zero[["cpa", "over_attribution"]].to_numpy()).any()


# ----------------------------------------------------------------------------- pacing
def month_of_spend(daily: float, budget: float = 3000.0, days: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2026-11-01", periods=days)  # 30-day month
    return pd.DataFrame({"date": dates, "spend": daily, "monthly_budget": budget})


@pytest.mark.parametrize(
    ("daily", "status"),
    [(100.0, "on track"), (87.0, "on track"), (109.0, "on track"), (120.0, "over"), (80.0, "under")],
)
def test_budget_pacing_uses_the_data_check_band(daily, status):
    # Budget 3,000 for 30 days = 100/day planned, so pace = daily / 100.
    df = month_of_spend(daily)
    p = budget_pacing(df, df["date"].max())
    assert p["pace"] == pytest.approx(daily / 100)
    assert p["status"] == status
    low, high = config.PACING_BAND
    assert (low <= p["pace"] <= high) == (status == "on track")


def test_budget_pacing_verdict_text():
    df = month_of_spend(150.0)
    assert budget_pacing(df, df["date"].max())["verdict"] == "50% over budget"


def test_budget_pacing_without_plan():
    df = month_of_spend(100.0, budget=np.nan)
    assert budget_pacing(df, df["date"].max())["status"] == "unknown"


# ----------------------------------------------------------------------------- response curves
def synthetic_history(a: float, b: float, days: int = 60, channel: str = "X", ctype: str = "Shopping") -> pd.DataFrame:
    rng = np.random.default_rng(1)
    spend = rng.uniform(200, 800, days)
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=days),
            "channel": channel,
            "campaign_type": ctype,
            "spend": spend,
            "ga4_value": a * spend**b,
        }
    )


def test_fit_recovers_known_curve():
    curves = fit_response_curves(synthetic_history(a=3.0, b=0.7))
    row = curves.iloc[0]
    assert row["b"] == pytest.approx(0.7, abs=1e-6)
    assert row["a"] == pytest.approx(3.0, rel=1e-6)


def test_fit_skips_short_history_and_empty_input():
    assert fit_response_curves(synthetic_history(3.0, 0.7, days=config.MIN_FIT_DAYS - 1)).empty
    assert fit_response_curves(synthetic_history(3.0, 0.7).iloc[0:0]).empty


# ----------------------------------------------------------------------------- optimizer
CURVES = pd.DataFrame(
    {
        "channel": ["Brand", "Search", "Social", "Shopping"],
        "campaign_type": ["Search - Brand", "Search - Non-brand", "Paid Social - Prospecting", "Shopping"],
        "a": [20.0, 12.0, 40.0, 9.0],
        "b": [0.9, 0.75, 0.55, 0.85],
        "current_daily_spend": [300.0, 900.0, 600.0, 500.0],
    }
)


def check_plan(plan: pd.DataFrame, total: float) -> None:
    assert plan["recommended_daily_spend"].sum() == pytest.approx(total, abs=1.0)
    ratio = plan["recommended_daily_spend"] / plan["current_daily_spend"]
    assert (ratio >= config.MIN_MULT - 1e-9).all()
    assert (ratio <= config.MAX_MULT + 1e-9).all()
    brand = plan["campaign_type"] == config.BRAND_CAMPAIGN_TYPE
    assert (ratio[brand] <= config.BRAND_MAX_MULT + 1e-9).all()


def test_optimizer_keeps_total_and_guardrails():
    plan = optimize_budget(CURVES)
    check_plan(plan, CURVES["current_daily_spend"].sum())
    assert plan_uplift(plan) > 0


def test_brand_cap_holds_even_when_brand_is_most_efficient():
    curves = CURVES.assign(a=[500.0, 12.0, 40.0, 9.0])  # brand has by far the best marginal return
    plan = optimize_budget(curves)
    brand = plan.set_index("campaign_type").loc["Search - Brand"]
    assert brand["change_pct"] <= config.BRAND_MAX_MULT - 1 + 1e-9
    assert brand["change_pct"] > 0.09  # it does get (almost all of) its allowed +10%


def test_brand_cap_follows_campaign_type_not_label():
    plan = optimize_budget(
        CURVES.assign(channel=["Renamed label", "Search", "Social", "Shopping"], a=[500.0, 12, 40, 9])
    )
    assert plan.set_index("campaign_type").loc["Search - Brand", "change_pct"] <= 0.10 + 1e-9


def test_optimizer_custom_total_and_bad_total():
    total = CURVES["current_daily_spend"].sum() * 1.1
    check_plan(optimize_budget(CURVES, total_daily=total), total)
    with pytest.raises(ValueError):
        optimize_budget(CURVES, total_daily=10.0)


def test_optimizer_empty_input():
    plan = optimize_budget(CURVES.iloc[0:0])
    assert plan.empty and math.isnan(plan_uplift(plan))


@pytest.mark.parametrize("client", ["DTC Skincare", "B2B SaaS", "Home Services"])
def test_optimizer_on_demo_clients(mart, client):
    plan = optimize_budget(fit_response_curves(mart[mart["client"] == client]))
    assert len(plan) >= 2
    check_plan(plan, plan["current_daily_spend"].sum())


def test_optimizer_is_deterministic(mart):
    c = mart[mart["client"] == "DTC Skincare"]
    shuffled = c.sample(frac=1, random_state=3)
    a = optimize_budget(fit_response_curves(c)).set_index("channel")["recommended_daily_spend"]
    b = optimize_budget(fit_response_curves(shuffled)).set_index("channel")
    assert a.sort_index().round(6).equals(b["recommended_daily_spend"].sort_index().round(6))


# ----------------------------------------------------------------------------- weekly summary
@pytest.mark.parametrize(
    ("client", "word", "other"),
    [("DTC Skincare", "sales", "leads"), ("B2B SaaS", "leads", "sales"), ("Home Services", "leads", "sales")],
)
def test_weekly_summary_words_and_no_nan(mart, qa, client, word, other):
    df = mart[mart["client"] == client]
    text = weekly_summary(df, client, qa, optimize_budget(fit_response_curves(df)))
    assert text.startswith(f"**{client}: week ending Nov 21, 2026**")
    assert f"more {word}" in text
    assert other not in text.lower()
    assert not NO_NAN.search(text)
    assert "Being fixed:" in text  # every demo client has at least one High issue


def test_weekly_summary_when_nothing_is_measurable(mart, qa):
    df = mart[mart["client"] == "B2B SaaS"].assign(ga4_value=0.0, ga4_conversions=0.0)
    text = weekly_summary(df, "B2B SaaS", qa, optimize_budget(fit_response_curves(df)))
    assert not NO_NAN.search(text)
    assert "No leads were counted this week" in text
    assert "can't compare them yet" in text
    assert "keep the current budget split" in text


def test_weekly_summary_clean_data_message(mart, qa):
    df = mart[mart["client"] == "DTC Skincare"]
    text = weekly_summary(df, "DTC Skincare", qa.iloc[0:0], optimize_budget(fit_response_curves(df)))
    assert "all tracking checks passed" in text
