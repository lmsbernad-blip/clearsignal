"""Analytics behind the app: KPIs, channel scorecard, pacing, budget optimizer and weekly summary.

Data quality rules live in sql/03_qa_checks.sql; thresholds live in config.py.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

import config

FRIENDLY = {
    "Search - Brand": "Google Search · brand name",
    "Search - Non-brand": "Google Search · general",
    "Search - Seasonal": "Google Search · holiday",
    "Shopping": "Google Shopping",
    "Performance Max": "Google Performance Max",
    "Paid Social - Prospecting": "Meta · new customers",
    "Paid Social - Retargeting": "Meta · past visitors",
    "Paid Social - Lead Gen": "Meta · lead ads",
}

PLAN_COLUMNS = [
    "channel",
    "campaign_type",
    "a",
    "b",
    "current_daily_spend",
    "recommended_daily_spend",
    "current_value",
    "recommended_value",
    "change_pct",
    "current_marginal_roas",
]


# ----------------------------------------------------------------------------- formatting
def usd(x: float, dec: int = 1) -> str:
    """Short dollar label: $1.2M, $45.3K, $812. Missing values show as '-'."""
    if x is None or pd.isna(x):
        return "-"
    for unit, div in (("M", 1e6), ("K", 1e3)):
        if abs(x) >= div:
            return f"${x / div:,.{dec}f}{unit}"
    return f"${x:,.0f}"


def pct_change(new: float, old: float) -> float:
    """Relative change new vs old; NaN when there is nothing to compare against."""
    return new / old - 1 if old else float("nan")


def nouns(df: pd.DataFrame) -> dict[str, str]:
    """Words that match the client's business: sales for e-commerce, leads for lead generation."""
    ecommerce = bool((df["business_model"] == "ecommerce").any())
    return {
        "result": "sale" if ecommerce else "lead",
        "results": "sales" if ecommerce else "leads",
        "Results": "Sales" if ecommerce else "Leads",
        "value": "sales revenue" if ecommerce else "lead value",
        "Value": "Sales revenue" if ecommerce else "Lead value",
    }


# ----------------------------------------------------------------------------- data
def load(db_path: Path | str | None = None) -> pd.DataFrame:
    """Campaign × day mart from the warehouse, in a fixed order, with a readable channel label."""
    import warehouse

    df = warehouse.read_table("mart_campaign_daily", Path(db_path) if db_path else None)
    df["date"] = pd.to_datetime(df["date"])
    # A fixed order matters: "recent days" in the optimizer must not depend on how DuckDB returned the rows.
    df = df.sort_values(["client", "platform", "campaign_name", "date"], ignore_index=True)
    df["channel"] = df["campaign_type"].map(FRIENDLY).fillna(df["campaign_type"])
    unmapped = df["campaign_type"] == "UNMAPPED"
    df.loc[unmapped, "channel"] = df.loc[unmapped, "campaign_name"] + " (not set up yet)"
    return df


def period_windows(df: pd.DataFrame, as_of: pd.Timestamp, days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rows in the last `days` days up to `as_of`, and in the `days` days before that."""
    start = as_of - pd.Timedelta(days=days)
    current = df[(df["date"] > start) & (df["date"] <= as_of)]
    previous = df[(df["date"] <= start) & (df["date"] > start - pd.Timedelta(days=days))]
    return current, previous


# ----------------------------------------------------------------------------- KPIs
def kpis(df: pd.DataFrame, basis: str = "ga4") -> dict[str, float]:
    """Spend, conversions, value, ROAS, CPA and CTR, counting results by GA4 or by the platform.

    Ratios with a zero denominator are NaN (shown as "-" or "n/a"), never infinity.
    """
    if basis not in ("ga4", "platform"):
        raise ValueError("basis must be 'ga4' or 'platform'")
    spend = float(df["spend"].sum())
    conv = float(df[f"{basis}_conversions"].sum())
    value = float(df[f"{basis}_value"].sum())
    impressions = float(df["impressions"].sum())
    return {
        "spend": spend,
        "conversions": conv,
        "value": value,
        "roas": value / spend if spend else np.nan,
        "cpa": spend / conv if conv else np.nan,
        "ctr": float(df["clicks"].sum()) / impressions if impressions else np.nan,
    }


def channel_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per channel: spend, results, ROAS, CPA, CTR, platform over-counting and share of spend."""
    g = df.groupby("channel").agg(
        spend=("spend", "sum"),
        clicks=("clicks", "sum"),
        impressions=("impressions", "sum"),
        platform_conversions=("platform_conversions", "sum"),
        ga4_conversions=("ga4_conversions", "sum"),
        ga4_value=("ga4_value", "sum"),
    )
    nz = lambda s: s.replace(0, np.nan)  # noqa: E731 - avoid inf on zero denominators
    g["roas"] = g["ga4_value"] / nz(g["spend"])
    g["cpa"] = g["spend"] / nz(g["ga4_conversions"])
    g["ctr"] = g["clicks"] / nz(g["impressions"])
    # how much more the ad platform claims than GA4 sees
    g["over_attribution"] = g["platform_conversions"] / nz(g["ga4_conversions"]) - 1
    g["share_of_spend"] = g["spend"] / g["spend"].sum() if g["spend"].sum() else np.nan
    return g.sort_values("spend", ascending=False).reset_index()


def budget_pacing(df: pd.DataFrame, as_of: pd.Timestamp) -> dict[str, float | str]:
    """Month-to-date spend vs the media plan, using the same band as the data check (config.PACING_BAND).

    Returns budget, spend so far, projected month-end spend, pace (projected ÷ budget),
    status ("on track" / "over" / "under") and a short verdict such as "12% over budget".
    """
    month_start = as_of.replace(day=1)
    days_in_month = (month_start + pd.offsets.MonthEnd(0)).day
    mtd = df[(df["date"] >= month_start) & (df["date"] <= as_of)]
    budget = float(mtd["monthly_budget"].max()) if len(mtd) else float("nan")
    spent = float(mtd["spend"].sum())
    projected = spent / as_of.day * days_in_month
    pace = projected / budget if budget and not math.isnan(budget) else float("nan")
    low, high = config.PACING_BAND
    if math.isnan(pace):
        status, verdict = "unknown", "no budget in the media plan"
    elif low <= pace <= high:
        status, verdict = "on track", "on track"
    elif pace > high:
        status, verdict = "over", f"{pace - 1:.0%} over budget"
    else:
        status, verdict = "under", f"{1 - pace:.0%} under budget"
    return {
        "budget": budget,
        "spent": spent,
        "projected": projected,
        "pace": pace,
        "status": status,
        "verdict": verdict,
        "days_in_month": days_in_month,
    }


# ----------------------------------------------------------------------------- optimizer
def fit_response_curves(df: pd.DataFrame, fit_days: int = config.FIT_DAYS) -> pd.DataFrame:
    """Fit value = a · spend^b per channel on recent daily data (log-log regression with weekday effects).

    b < 1 means diminishing returns: each extra dollar buys a little less. Channels with fewer than
    config.MIN_FIT_DAYS usable days (spend and value both > 0) are left out. Returns one row per channel
    with a, b, campaign_type and current_daily_spend (mean of the last 30 usable days).
    """
    cols = ["channel", "campaign_type", "a", "b", "current_daily_spend"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    as_of = df["date"].max()
    recent = df[df["date"] > as_of - pd.Timedelta(days=fit_days)]
    daily = (
        recent.groupby(["channel", "date"], as_index=False)
        .agg(campaign_type=("campaign_type", "first"), spend=("spend", "sum"), ga4_value=("ga4_value", "sum"))
        .sort_values(["channel", "date"])
    )
    out = []
    lo_b, hi_b = config.ELASTICITY_CLIP
    for channel, g in daily.groupby("channel"):
        g = g[(g["spend"] > 0) & (g["ga4_value"] > 0)]
        if len(g) < config.MIN_FIT_DAYS:
            continue
        # log(value) = log(a) + b*log(spend) + weekday effects (so weekday swings don't inflate b)
        x = np.log(g["spend"].to_numpy(dtype=float))
        y = np.log(g["ga4_value"].to_numpy(dtype=float))
        wd = pd.get_dummies(g["date"].dt.dayofweek, drop_first=True).to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(g)), x, wd])
        coef, *_ = np.linalg.lstsq(design, y, rcond=None)
        b = float(np.clip(coef[1], lo_b, hi_b))
        # re-anchor the level at the average weekday so predictions match a typical day
        a = float(np.exp((y - b * x).mean()))
        out.append(
            {
                "channel": channel,
                "campaign_type": g["campaign_type"].iloc[0],
                "a": a,
                "b": b,
                "current_daily_spend": float(g["spend"].tail(30).mean()),
            }
        )
    return pd.DataFrame(out, columns=cols)


def optimize_budget(
    curves: pd.DataFrame,
    total_daily: float | None = None,
    min_mult: float = config.MIN_MULT,
    max_mult: float = config.MAX_MULT,
    steps: int = config.OPTIMIZER_STEPS,
) -> pd.DataFrame:
    """Reallocate the same daily budget across channels to maximize predicted value.

    Greedy marginal-return allocation in `steps` equal increments, with guardrails: each channel stays
    between min_mult and max_mult of today's spend, and brand search (config.BRAND_CAMPAIGN_TYPE) rises
    at most config.BRAND_MAX_MULT. An empty input gives an empty plan.
    """
    if curves.empty:
        return pd.DataFrame(columns=PLAN_COLUMNS)
    c = curves.reset_index(drop=True).copy()
    current = c["current_daily_spend"].to_numpy(dtype=float)
    total = float(total_daily) if total_daily is not None else float(current.sum())
    brand = (c["campaign_type"] == config.BRAND_CAMPAIGN_TYPE).to_numpy()
    lo = current * min_mult
    hi = current * np.where(brand, min(config.BRAND_MAX_MULT, max_mult), max_mult)
    if not lo.sum() - 1e-9 <= total <= hi.sum() + 1e-9:
        raise ValueError("total_daily is outside what the guardrails allow")
    a, b = c["a"].to_numpy(dtype=float), c["b"].to_numpy(dtype=float)
    alloc = lo.copy()
    step = (total - alloc.sum()) / steps
    for _ in range(steps):
        marginal = a * b * np.power(alloc, b - 1)
        marginal[alloc + step > hi + 1e-9] = -np.inf
        i = int(np.argmax(marginal))
        if not np.isfinite(marginal[i]):
            break
        alloc[i] += step
    c["recommended_daily_spend"] = alloc
    c["current_value"] = a * current**b
    c["recommended_value"] = a * alloc**b
    c["change_pct"] = alloc / current - 1
    c["current_marginal_roas"] = a * b * current ** (b - 1)
    return c[PLAN_COLUMNS].sort_values("change_pct", ascending=False).reset_index(drop=True)


def plan_uplift(plan: pd.DataFrame) -> float:
    """Expected relative gain in value from the recommended plan (NaN for an empty plan)."""
    if plan.empty or not plan["current_value"].sum():
        return float("nan")
    return float(plan["recommended_value"].sum() / plan["current_value"].sum() - 1)


# ----------------------------------------------------------------------------- weekly summary
def _move(new: float, old: float) -> str:
    """'up 12% vs last week' / 'down 3% vs last week' / 'flat vs last week'."""
    change = pct_change(new, old)
    if not math.isfinite(change):
        return "no figure for last week"
    if abs(change) < 0.005:
        return "flat vs last week"
    return f"{'up' if change > 0 else 'down'} {abs(change):.0%} vs last week"


def weekly_summary(df: pd.DataFrame, client: str, alerts: pd.DataFrame, plan: pd.DataFrame) -> str:
    """Plain-language markdown summary of the last 7 days vs the 7 before, for the client email.

    Counts results with GA4, uses sales or leads to match the business, lists open High data issues,
    and never prints 'nan' or 'inf' (missing figures are described in words instead).
    """
    n = nouns(df)
    as_of = df["date"].max()
    this_wk, last_wk = period_windows(df, as_of, 7)
    k1, k0 = kpis(this_wk), kpis(last_wk)

    if k1["spend"] and math.isfinite(k1["roas"]):
        results = (
            f"- **Results:** ${k1['spend']:,.0f} spent ({_move(k1['spend'], k0['spend'])}) brought in "
            f"${k1['value']:,.0f} in {n['value']}, or **${k1['roas']:.2f} back for every $1** "
            f"({_move(k1['roas'], k0['roas'])})."
        )
        if math.isfinite(k1["cpa"]):
            results += f" Each {n['result']} cost ${k1['cpa']:,.0f} on average ({_move(k1['cpa'], k0['cpa'])})."
        else:
            results += f" No {n['results']} were counted this week."
    else:
        results = "- **Results:** no ad spend was recorded this week."

    ch = channel_table(this_wk)
    ch = ch[ch["ga4_value"] > 0]  # campaigns we can't measure yet are listed under "being fixed" instead
    if len(ch):
        best, worst = ch.loc[ch["roas"].idxmax()], ch.loc[ch["roas"].idxmin()]
        working = (
            f"- **Working best:** {best['channel']}, ${best['roas']:.2f} back per $1. "
            f"**Weakest:** {worst['channel']}, ${worst['roas']:.2f} per $1."
        )
    else:
        working = (
            f"- **Working best:** no campaign had measurable {n['value']} this week, so we can't compare them yet."
        )

    lines = [f"**{client}: week ending {as_of:%b} {as_of.day}, {as_of:%Y}**", "", results, working]
    issues = alerts[(alerts["client"] == client) & (alerts["severity"] == "High")]
    if len(issues):
        titles = list(dict.fromkeys(issues["title"]))
        lines.append("- **Being fixed:** " + "; ".join(titles) + ".")
    else:
        lines.append("- **Data:** all tracking checks passed this week.")

    uplift = plan_uplift(plan)
    if len(plan) >= 2 and math.isfinite(uplift):
        up, down = plan.iloc[0], plan.iloc[-1]
        lines.append(
            f"- **Recommendation:** move some budget from {down['channel']} to {up['channel']}. Same total budget; "
            f"we expect about {uplift:.0%} more {n['results']}. We'd test it for 2 weeks before making it permanent."
        )
    else:
        lines.append(
            "- **Recommendation:** keep the current budget split; there isn't enough history yet to suggest a change."
        )
    return "\n".join(lines)
