"""Input contracts: check every raw export and seed file before the warehouse is built.

Each file must have its required columns, values that parse (dates, numbers), dates in a sensible range,
no negative spend / impressions / clicks / conversions, and USD as the currency. All problems across all
files are collected and reported together in plain language, so one build run shows everything to fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

import config

EARLIEST_DATE = pd.Timestamp("2015-01-01")
MAX_EXAMPLES = 3


@dataclass(frozen=True)
class Contract:
    """What one input file must look like."""

    key: str
    path: str
    required: tuple[str, ...]
    dates: dict[str, str] = field(default_factory=dict)  # column -> strptime format ("" = ISO date or timestamp)
    non_negative: tuple[str, ...] = ()
    numeric: tuple[str, ...] = ()  # must parse as numbers when present (may be blank)
    text: tuple[str, ...] = ()  # must not be blank
    allowed: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unique: tuple[str, ...] = ()


CONTRACTS = (
    Contract(
        "google_ads",
        config.RAW_FILES["google_ads"],
        required=(
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
        ),
        dates={"Date": "%Y-%m-%d"},
        non_negative=("Cost", "cost_micros", "Impressions", "Clicks", "Conversions", "Conv. value"),
        text=("Account name", "Campaign name"),
        allowed={"Currency": ("USD",)},
    ),
    Contract(
        "meta_ads",
        config.RAW_FILES["meta_ads"],
        required=(
            "date_start",
            "account_name",
            "campaign_name",
            "spend",
            "impressions",
            "inline_link_clicks",
            "purchases_7d_click_1d_view",
            "leads_7d_click_1d_view",
            "purchase_value",
            "_synced_at",
        ),
        dates={"date_start": "%Y-%m-%d", "_synced_at": ""},
        non_negative=(
            "spend",
            "impressions",
            "inline_link_clicks",
            "purchases_7d_click_1d_view",
            "leads_7d_click_1d_view",
            "purchase_value",
        ),
        text=("account_name", "campaign_name"),
        # The Meta export has no currency column: the ad accounts are set to USD (checked at onboarding).
    ),
    Contract(
        "ga4",
        config.RAW_FILES["ga4"],
        required=(
            "date",
            "property",
            "sessionSourceMedium",
            "sessionCampaignName",
            "sessions",
            "keyEvents",
            "purchaseRevenue",
        ),
        dates={"date": "%Y%m%d"},
        non_negative=("sessions", "keyEvents", "purchaseRevenue"),
        text=("property", "sessionSourceMedium"),
    ),
    Contract(
        "campaign_mapping",
        config.SEED_FILES["campaign_mapping"],
        required=("platform", "campaign_name", "client", "campaign_type", "utm_campaign"),
        text=("platform", "campaign_name", "client", "campaign_type"),
        allowed={"platform": ("Google Ads", "Meta Ads"), "campaign_type": config.CAMPAIGN_TYPES},
        unique=("platform", "campaign_name"),
    ),
    Contract(
        "media_plan",
        config.SEED_FILES["media_plan"],
        required=("client", "month", "planned_budget_usd"),
        dates={"month": "%Y-%m"},
        non_negative=("planned_budget_usd",),
        text=("client",),
        unique=("client", "month"),
    ),
    Contract(
        "clients",
        config.SEED_FILES["clients"],
        required=("client", "business_model", "value_per_lead_usd"),
        numeric=("value_per_lead_usd",),
        non_negative=("value_per_lead_usd",),
        text=("client", "business_model"),
        allowed={"business_model": ("ecommerce", "leadgen")},
        unique=("client",),
    ),
)


class ContractError(ValueError):
    """One or more input files break their contract. The message lists every problem."""


def _rows(mask: pd.Series) -> str:
    """'rows 2, 7, 9 and 4 more' using spreadsheet row numbers (header = row 1)."""
    idx = [int(i) + 2 for i in mask[mask].index[:MAX_EXAMPLES]]
    more = int(mask.sum()) - len(idx)
    return (
        ("row " if len(idx) == 1 and not more else "rows ")
        + ", ".join(map(str, idx))
        + (f" and {more} more" if more else "")
    )


def check_file(contract: Contract, root: Path, today: pd.Timestamp) -> list[str]:
    """Problems with one file (empty list = the file is fine)."""
    path = Path(root) / contract.path
    name = contract.path
    if not path.exists():
        return [f"Input file is missing: {name}. Run `python scripts/generate_data.py` or add the export."]
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    except pd.errors.EmptyDataError:
        return [f"{name}: the file is empty or has no header row."]
    except (pd.errors.ParserError, UnicodeDecodeError) as err:
        return [f"{name}: the file isn't a readable CSV ({type(err).__name__})."]

    missing = [c for c in contract.required if c not in df.columns]
    if missing:
        return [f"{name}: missing a required column: {', '.join(missing)} (was a column renamed?)."]
    if df.empty:
        return [f"{name}: the file has a header but no rows."]

    problems: list[str] = []
    for col, fmt in contract.dates.items():
        values = df[col]
        parsed = pd.to_datetime(values, format=fmt or "mixed", errors="coerce", utc=not fmt)
        if not fmt:
            parsed = parsed.dt.tz_localize(None)
        bad = values.notna() & parsed.isna()
        if values.isna().any():
            problems.append(f"{name}: {col} is blank in {_rows(values.isna())}.")
        if bad.any():
            problems.append(
                f"{name}: {col} has values that aren't valid dates in {_rows(bad)} (e.g. {values[bad].iloc[0]!r})."
            )
        out_of_range = parsed.notna() & ((parsed < EARLIEST_DATE) | (parsed > today + pd.Timedelta(days=1)))
        if out_of_range.any():
            problems.append(
                f"{name}: {col} is outside {EARLIEST_DATE:%Y-%m-%d} to today in {_rows(out_of_range)} "
                f"(e.g. {values[out_of_range].iloc[0]!r})."
            )

    for col in dict.fromkeys((*contract.numeric, *contract.non_negative)):
        values = df[col]
        num = pd.to_numeric(values, errors="coerce")
        bad = values.notna() & num.isna()
        if bad.any():
            problems.append(
                f"{name}: {col} has values that aren't numbers in {_rows(bad)} (e.g. {values[bad].iloc[0]!r})."
            )
        if col in contract.non_negative and (num < 0).any():
            problems.append(f"{name}: {col} is negative in {_rows(num < 0)}.")

    for col in contract.text:
        blank = df[col].isna() | (df[col].str.strip() == "")
        if blank.any():
            problems.append(f"{name}: {col} is blank in {_rows(blank)}.")

    for col, allowed in contract.allowed.items():
        bad = df[col].notna() & ~df[col].isin(allowed)
        if bad.any():
            problems.append(
                f"{name}: {col} must be one of {', '.join(allowed)}; found "
                f"{df.loc[bad, col].iloc[0]!r} in {_rows(bad)}."
            )

    if contract.unique:
        dup = df.duplicated(list(contract.unique), keep=False)
        if dup.any():
            problems.append(f"{name}: {' + '.join(contract.unique)} must be unique; repeated in {_rows(dup)}.")

    # File-specific rules
    if contract.key == "google_ads":
        no_cost = df["Cost"].isna() & df["cost_micros"].isna()
        if no_cost.any():
            problems.append(f"{name}: both Cost and cost_micros are blank in {_rows(no_cost)}.")
    if contract.key == "clients":
        value = pd.to_numeric(df["value_per_lead_usd"], errors="coerce")
        no_value = (df["business_model"] == "leadgen") & ~(value > 0)
        if no_value.any():
            problems.append(f"{name}: lead-gen clients need a value_per_lead_usd above 0 ({_rows(no_value)}).")
    return problems


def validate_inputs(root: Path, today: pd.Timestamp | None = None) -> None:
    """Check every input file under `root`. Raises ContractError listing all problems; returns None if clean."""
    today = (today or pd.Timestamp.today()).normalize()
    problems = [p for contract in CONTRACTS for p in check_file(contract, root, today)]
    if problems:
        raise ContractError(
            f"{len(problems)} problem{'s' if len(problems) != 1 else ''} in the input files:\n- "
            + "\n- ".join(problems)
        )
