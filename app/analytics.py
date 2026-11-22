"""Analytics behind the app: KPIs, channel scorecard, budget optimizer, weekly summary. Data QA lives in sql/03_qa_checks.sql."""
from __future__ import annotations

import numpy as np
import pandas as pd


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


def nouns(df: pd.DataFrame) -> dict:
    """Words that match the client's business: sales for e-commerce, leads for lead generation."""
    ecommerce = (df["business_model"] == "ecommerce").any()
    return dict(result="sale" if ecommerce else "lead", results="sales" if ecommerce else "leads",
                Results="Sales" if ecommerce else "Leads", value="sales revenue" if ecommerce else "lead value",
                Value="Sales revenue" if ecommerce else "Lead value")


def load(db_path) -> pd.DataFrame:
    """Campaign x day mart from the DuckDB warehouse, with a readable channel label."""
    import duckdb
    with duckdb.connect(str(db_path), read_only=True) as con:
        df = con.execute("select * from mart_campaign_daily").df()
    df["date"] = pd.to_datetime(df["date"])
    df["channel"] = df["campaign_type"].map(FRIENDLY).fillna(df["campaign_type"])
    unmapped = df["campaign_type"] == "UNMAPPED"
    df.loc[unmapped, "channel"] = df.loc[unmapped, "campaign_name"] + " (not set up yet)"
    return df


def kpis(df: pd.DataFrame, basis: str = "ga4") -> dict:
    spend = df["spend"].sum()
    conv = df[f"{basis}_conversions"].sum()
    value = df[f"{basis}_value"].sum()
    return dict(
        spend=spend, conversions=conv, value=value,
        roas=value / spend if spend else np.nan,
        cpa=spend / conv if conv else np.nan,
        ctr=df["clicks"].sum() / df["impressions"].sum() if df["impressions"].sum() else np.nan,
    )


def channel_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("channel").agg(
        spend=("spend", "sum"), clicks=("clicks", "sum"), impressions=("impressions", "sum"),
        platform_conversions=("platform_conversions", "sum"), ga4_conversions=("ga4_conversions", "sum"),
        ga4_value=("ga4_value", "sum"),
    )
    g["roas"] = g["ga4_value"] / g["spend"]
    g["cpa"] = g["spend"] / g["ga4_conversions"]
    g["ctr"] = g["clicks"] / g["impressions"]
    # how much more the ad platform claims than GA4 sees
    g["over_attribution"] = g["platform_conversions"] / g["ga4_conversions"] - 1
    g["share_of_spend"] = g["spend"] / g["spend"].sum()
    return g.sort_values("spend", ascending=False).reset_index()


# --------------------------------------------------------------------------- optimizer
def fit_response_curves(df: pd.DataFrame, fit_days: int = 60) -> pd.DataFrame:
    """Fit value = a * spend^b per channel on recent daily data (log-log regression).
    b < 1 means diminishing returns: each extra peso buys a little less."""
    as_of = df["date"].max()
    recent = df[df["date"] > as_of - pd.Timedelta(days=fit_days)]
    out = []
    for channel, g in recent.groupby("channel"):
        g = g[(g["spend"] > 0) & (g["ga4_value"] > 0)]
        if len(g) < 20:
            continue
        # log(value) = log(a) + b*log(spend) + weekday effects (so weekday swings don't inflate b)
        x = np.log(g["spend"].values)
        wd = pd.get_dummies(g["date"].dt.dayofweek, drop_first=True).values.astype(float)
        X = np.column_stack([np.ones(len(g)), x, wd])
        coef, *_ = np.linalg.lstsq(X, np.log(g["ga4_value"].values), rcond=None)
        b = float(np.clip(coef[1], 0.2, 0.95))
        # re-anchor the level at the average weekday so predictions match a typical day
        resid = np.log(g["ga4_value"].values) - b * x
        a = float(np.exp(resid.mean()))
        out.append(dict(channel=channel, a=a, b=b, current_daily_spend=g["spend"].tail(30).mean()))
    return pd.DataFrame(out)


def optimize_budget(curves: pd.DataFrame, total_daily: float | None = None,
                    min_mult: float = 0.7, max_mult: float = 1.5, steps: int = 400) -> pd.DataFrame:
    """Reallocate the same daily budget to maximize predicted value.
    Greedy marginal-return allocation with guardrails (each channel 70%-150% of today's spend)."""
    c = curves.copy()
    total = total_daily if total_daily is not None else c["current_daily_spend"].sum()
    lo = c["current_daily_spend"] * min_mult
    # Brand search is capped by how many people already search the brand: allow at most +10%.
    brand = c["channel"].str.contains("brand name", case=False)
    hi = c["current_daily_spend"] * max_mult.where(~brand, 1.10) if isinstance(max_mult, pd.Series) else \
        c["current_daily_spend"] * pd.Series(max_mult, index=c.index).where(~brand, 1.10)
    alloc = lo.copy()
    remaining = total - alloc.sum()
    step = remaining / steps
    for _ in range(steps):
        x = alloc.values
        marginal = c["a"].values * c["b"].values * np.power(x, c["b"].values - 1)
        marginal[alloc.values + step > hi.values] = -np.inf
        i = int(np.argmax(marginal))
        if not np.isfinite(marginal[i]):
            break
        alloc.iloc[i] += step
    c["recommended_daily_spend"] = alloc
    c["current_value"] = c["a"] * c["current_daily_spend"] ** c["b"]
    c["recommended_value"] = c["a"] * c["recommended_daily_spend"] ** c["b"]
    c["change_pct"] = c["recommended_daily_spend"] / c["current_daily_spend"] - 1
    c["current_marginal_roas"] = c["a"] * c["b"] * c["current_daily_spend"] ** (c["b"] - 1)
    return c.sort_values("change_pct", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- weekly summary
def weekly_summary(df: pd.DataFrame, client: str, alerts: pd.DataFrame, plan: pd.DataFrame) -> str:
    n = nouns(df)
    as_of = df["date"].max()
    this_wk = df[df["date"] > as_of - pd.Timedelta(days=7)]
    last_wk = df[(df["date"] <= as_of - pd.Timedelta(days=7)) & (df["date"] > as_of - pd.Timedelta(days=14))]
    k1, k0 = kpis(this_wk), kpis(last_wk)

    def move(a, b):
        c = (a / b - 1) if b else 0.0
        return "flat vs last week" if abs(c) < 0.005 else f"{'up' if c > 0 else 'down'} {abs(c):.0%} vs last week"

    ch = channel_table(this_wk)
    ch = ch[ch["ga4_value"] > 0]  # campaigns we can't measure yet are listed under "being fixed" instead
    best = ch.loc[ch["roas"].idxmax()]
    worst = ch.loc[ch["roas"].idxmin()]
    issues = alerts[(alerts["client"] == client) & (alerts["severity"] == "High")]
    up, down = plan.iloc[0], plan.iloc[-1]
    uplift = plan["recommended_value"].sum() / plan["current_value"].sum() - 1

    lines = [
        f"**{client}: week ending {as_of:%b %-d, %Y}**",
        "",
        f"- **Results:** ${k1['spend']:,.0f} spent ({move(k1['spend'], k0['spend'])}) brought in ${k1['value']:,.0f} in "
        f"{n['value']}, or **${k1['roas']:.2f} back for every $1** ({move(k1['roas'], k0['roas'])}). "
        f"Each {n['result']} cost ${k1['cpa']:,.0f} on average ({move(k1['cpa'], k0['cpa'])}).",
        f"- **Working best:** {best['channel']}, ${best['roas']:.2f} back per $1. "
        f"**Weakest:** {worst['channel']}, ${worst['roas']:.2f} per $1.",
    ]
    if len(issues):
        titles = list(dict.fromkeys(issues["title"]))
        lines.append(f"- **Being fixed:** " + "; ".join(titles) + ".")
    else:
        lines.append("- **Data:** all tracking checks passed this week.")
    lines.append(
        f"- **Recommendation:** move some budget from {down['channel']} to {up['channel']}. Same total budget; "
        f"we expect about {uplift:.0%} more {n['results']}. We'd test it for 2 weeks before making it permanent.")
    return "\n".join(lines)
