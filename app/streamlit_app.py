"""
ClearSignal: ad results you can trust.
Collect -> check -> compare -> report -> advise, for every agency client account.

Run:  python scripts/build_warehouse.py   then   streamlit run app/streamlit_app.py
"""

import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
import ui
import warehouse
from analytics import (
    budget_pacing,
    channel_table,
    fit_response_curves,
    kpis,
    load,
    nouns,
    optimize_budget,
    pct_change,
    period_windows,
    plan_uplift,
    usd,
    weekly_summary,
)
from prompts import client_note_prompt

st.set_page_config(page_title="ClearSignal · Ad results you can trust", page_icon="📡", layout="wide")
ui.inject_css()


# ---------------------------------------------------------------- data access (cached, read-only)
@st.cache_resource(show_spinner="Preparing the data for the first time…")
def ensure_warehouse() -> str | None:
    """Build the warehouse if it is missing or incomplete. Returns a readable problem, or None if ready."""
    if not warehouse.missing_tables():
        return None
    try:
        warehouse.build()
    except warehouse.WarehouseError as err:
        return str(err)
    missing = warehouse.missing_tables()
    return f"The warehouse is missing: {', '.join(missing)}." if missing else None


@st.cache_data
def table(name: str) -> pd.DataFrame:
    """One allow-listed warehouse table (see config.APP_TABLES)."""
    return warehouse.read_table(name)


@st.cache_data
def mart() -> pd.DataFrame:
    return load()


@st.cache_data
def budget_plan(client_name: str) -> pd.DataFrame:
    """The optimizer's plan for one client; computed once and shared by two tabs."""
    rows = mart()
    return optimize_budget(fit_response_curves(rows[rows["client"] == client_name]))


def stop_with_problem(problem: str) -> None:
    ui.sidebar_brand()
    st.error(
        f"**ClearSignal can't load its data.** {problem}\n\n"
        "To fix it, run these two commands from the project folder, then refresh this page:\n\n"
        "```\npython scripts/generate_data.py\npython scripts/build_warehouse.py\n```"
    )
    st.stop()


problem = ensure_warehouse()
if problem:
    ensure_warehouse.clear()  # try again on the next page load once the data is fixed
    stop_with_problem(problem)
try:
    df = mart()
    qa = table("qa_results")
    recon = table("reconciliation_summary")
    recon_wk = table("reconciliation_weekly")
except warehouse.WarehouseError as err:
    stop_with_problem(str(err))
if df.empty:
    stop_with_problem("The warehouse has no campaign data.")

PLATFORM_NAME = {
    "Google Ads": "Google Ads",
    "Meta Ads": "Meta (Facebook & Instagram)",
    "All channels": "All channels",
    "Google Analytics": "Google Analytics",
}

as_of = df["date"].max()
label_of = df.drop_duplicates("campaign_name").set_index("campaign_name")["channel"].to_dict()

# ---------------------------------------------------------------- sidebar
ui.sidebar_brand()
client = st.sidebar.selectbox("Client", sorted(df["client"].unique()))
days = int(st.sidebar.radio("Time period", ["Last 7 days", "Last 30 days", "Last 90 days"], index=1).split()[1])
basis_label = st.sidebar.radio(
    "Count results using",
    ["Google Analytics (recommended)", "Each ad platform's own numbers"],
    help="Google Analytics counts each sale or lead once. Ad platforms each take credit "
    "for the same result, so their numbers add up to more than really happened.",
)
basis = "ga4" if basis_label.startswith("Google") else "platform"
st.sidebar.markdown("---")
st.sidebar.markdown(
    '<div class="side-note">Demo with realistic sample data for three agency clients. Built by Lorenzo Bernad.</div>',
    unsafe_allow_html=True,
)

client_df = df[df["client"] == client]
words = nouns(client_df)
cur, prev = period_windows(client_df, as_of, days)
kpi_now, kpi_prev = kpis(cur, basis), kpis(prev, basis)
client_qa = qa[qa["client"] == client]
model = "Online store" if words["result"] == "sale" else "Lead generation"
channels = " and ".join(sorted({PLATFORM_NAME.get(p, p).split(" (")[0] for p in client_df["platform"].unique()}))
plan = budget_plan(client)

# ---------------------------------------------------------------- header
ui.hero(
    client,
    f"{model} · advertising on {channels} · last {days} days compared with the {days} days before",
    int((client_qa["severity"] == "High").sum()),
    f"{as_of:%b} {as_of.day}, {as_of:%Y}",
)

# ---------------------------------------------------------------- start here: what this is, verdict, reading order
high = client_qa[client_qa["severity"] == "High"]
n_high, n_medium = len(high), int((client_qa["severity"] == "Medium").sum())
if n_high:
    examples = list(dict.fromkeys(high["title"]))[:2]
    ready, verdict = False, "Not yet"
    verdict_text = (
        f"{n_high} problem{'s' if n_high != 1 else ''} would make the numbers wrong, "
        f"for example: {'; '.join(t[:1].lower() + t[1:] for t in examples)}. Tab 1 shows each one and the fix."
    )
elif n_medium:
    ready, verdict = None, "Yes, with notes"
    verdict_text = (
        f"Nothing makes the numbers wrong today. {n_medium} item{'s' if n_medium != 1 else ''} to watch in tab 1."
    )
else:
    ready, verdict, verdict_text = True, "Yes", "Every data check passed. The report can be shared as is."
ui.briefing(
    about=(
        f"The reporting an ad agency runs for its client {client} ({model.lower()}). ClearSignal checks the ad data "
        f"first, then shows the results and what to do next. All numbers are realistic sample data."
    ),
    verdict_title=verdict,
    verdict_text=verdict_text,
    ok=ready,
    reading_order=[
        ("Data health", "can we trust the numbers?"),
        ("Do the numbers match?", "ad platforms vs Google Analytics"),
        ("Results", "what the ads achieved"),
        ("Where to spend next", "move budget for more " + words["results"]),
        ("Weekly client email", "the update, ready to send"),
    ],
)

daily = (
    cur.groupby("date")
    .agg(spend=("spend", "sum"), value=(f"{basis}_value", "sum"), conv=(f"{basis}_conversions", "sum"))
    .reset_index()
)
daily["roas"] = daily["value"] / daily["spend"].replace(0, float("nan"))
daily["cpa"] = daily["spend"] / daily["conv"].replace(0, float("nan"))
roas_text = "-" if pd.isna(kpi_now["roas"]) else f"${kpi_now['roas']:.2f}"
cpa_text = usd(kpi_now["cpa"], 0) if not pd.isna(kpi_now["cpa"]) and kpi_now["cpa"] < 1000 else usd(kpi_now["cpa"])
counted_by = "Google Analytics" if basis == "ga4" else "the ad platforms"
roas_change = pct_change(kpi_now["roas"], kpi_prev["roas"])
if pd.isna(roas_change):
    trend = "no earlier period to compare with"
elif abs(roas_change) < 0.005:
    trend = f"about the same as the {days} days before"
else:
    trend = f"{'up' if roas_change > 0 else 'down'} {abs(roas_change):.0%} on the {days} days before"
if kpi_now["spend"] and not pd.isna(kpi_now["roas"]):
    ui.headline(
        f"In the last {days} days, {usd(kpi_now['spend'])} of ads brought in {usd(kpi_now['value'])} in "
        f"{words['value']}: {roas_text} back for every $1 spent, {trend}.",
        emphasis=[usd(kpi_now["spend"]), usd(kpi_now["value"]), roas_text],
        note=f"{words['Results']} counted by {counted_by}.",
    )
ui.kpi_cards(
    [
        (
            "Ad spend",
            usd(kpi_now["spend"]),
            pct_change(kpi_now["spend"], kpi_prev["spend"]),
            True,
            daily["spend"],
            ui.TEAL,
            "what the client paid the ad platforms",
        ),
        (
            words["Value"],
            usd(kpi_now["value"]),
            pct_change(kpi_now["value"], kpi_prev["value"]),
            True,
            daily["value"],
            ui.TEAL,
            f"what the ads brought in, counted by {counted_by}",
        ),
        (
            "Return per $1 spent",
            roas_text,
            pct_change(kpi_now["roas"], kpi_prev["roas"]),
            True,
            daily["roas"],
            ui.ORANGE,
            "what came back for every $1 of ads",
        ),
        (
            f"Cost per {words['result']}",
            cpa_text,
            pct_change(kpi_now["cpa"], kpi_prev["cpa"]),
            False,
            daily["cpa"],
            ui.ORANGE,
            f"ad spend divided by the number of {words['results']}",
        ),
        (
            words["Results"],
            f"{kpi_now['conversions']:,.0f}",
            pct_change(kpi_now["conversions"], kpi_prev["conversions"]),
            True,
            daily["conv"],
            ui.TEAL,
            f"{words['results']} counted by {counted_by}",
        ),
    ]
)

tabs = st.tabs(
    [
        "1 · Data health",
        "2 · Do the numbers match?",
        "3 · Results",
        "4 · Where to spend next",
        "5 · Weekly client email",
        "Value to your agency",
        "How it works",
    ]
)

# ---------------------------------------------------------------- 1. data health
with tabs[0]:
    ui.section(
        "Can we trust today's numbers?",
        "Every morning ClearSignal checks the data behind each client report. Each card below is a problem "
        "that would make a report wrong, with what it means and what we're doing about it.",
    )
    ui.stat_row(
        [
            ("Issues across all clients", f"{len(qa)}"),
            ("Need fixing now", f"{int((qa['severity'] == 'High').sum())}"),
            ("For this client", f"{len(client_qa)}"),
            ("Ad spend affected", usd(qa["usd_at_risk"].sum())),
        ]
    )
    scope = st.segmented_control(
        "Show", ["This client", "All clients"], default="This client", label_visibility="collapsed"
    )
    view = qa if scope == "All clients" else client_qa
    if view.empty:
        ui.callout("<b>Everything checks out.</b> This client's report can be shared as is.")
    order = {"High": 0, "Medium": 1}
    for r in view.assign(o=view["severity"].map(order)).sort_values(["o", "client"]).itertuples():
        where = label_of.get(r.object, r.object)
        ui.issue_card(
            r.severity,
            r.title,
            r.client,
            PLATFORM_NAME.get(r.platform, r.platform),
            where,
            r.detail,
            r.usd_at_risk,
            r.action,
        )

# ---------------------------------------------------------------- 2. do the numbers match
STATUS_COLOR = {
    config.MATCH_STATUS: ui.GREEN,
    "Normal: Meta also counts people who only saw an ad": ui.TEAL,
    "Fix: not visible in Google Analytics": ui.RED,
    "Fix: new campaign not set up in reporting": ui.RED,
    "Fix: ad platform stopped counting": ui.RED,
    "Needs a closer look": ui.AMBER,
}
with tabs[1]:
    ui.section(
        f"Do the ad platforms and Google Analytics agree on {words['results']}?",
        "Ad platforms usually report more results than Google Analytics, because each one takes credit for the "
        "same customer. Some difference is normal; a big or sudden one usually means broken tracking. "
        f"Last {config.RECON_WEEKS} weeks, compared week by week.",
    )
    rc = recon[recon["client"] == client].copy()
    if rc.empty:
        ui.callout("<b>No campaigns to compare yet</b> for this client.")
    else:
        rc["label"] = rc["campaign_name"].map(label_of).fillna(rc["campaign_name"])
        rc["gap"] = rc["platform_vs_ga4"].fillna(1.0)
        tol = config.MATCH_TOLERANCE
        fig = go.Figure()
        for status, g in rc.groupby("typical_status"):
            fig.add_bar(
                y=g["label"].map(ui.plot_text),
                x=g["gap"],
                orientation="h",
                name=status,
                marker_color=STATUS_COLOR.get(status, ui.MUTED),
                marker_line_width=0,
                text=[("not visible in Google Analytics" if pd.isna(v) else f"{v:+.0%}") for v in g["platform_vs_ga4"]],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{y}<br>Ad platform reports %{text} vs Google Analytics<extra></extra>",
            )
        fig.add_vrect(x0=-tol, x1=tol, fillcolor=ui.GREEN, opacity=0.06, line_width=0)
        ui.style(
            fig, f"How many more {words['results']} the ad platform reports than Google Analytics", 160 + 48 * len(rc)
        )
        fig.update_layout(
            barmode="overlay",
            bargap=0.35,
            xaxis=dict(range=[-0.25, 1.45], showticklabels=False, ticks=""),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, width="stretch")

        c1, c2 = st.columns([3, 2])
        with c1:
            show = rc.assign(campaign=rc["label"])[
                [
                    "campaign",
                    "spend_8w",
                    "platform_conversions_8w",
                    "ga4_conversions_8w",
                    "platform_vs_ga4",
                    "typical_status",
                ]
            ]
            st.dataframe(
                show,
                hide_index=True,
                width="stretch",
                height=min(420, 40 + 36 * len(rc)),
                column_config={
                    "campaign": "Campaign",
                    "spend_8w": st.column_config.NumberColumn(f"Spend ({config.RECON_WEEKS} weeks)", format="$%,.0f"),
                    "platform_conversions_8w": st.column_config.NumberColumn("Ad platform says", format="%,.0f"),
                    "ga4_conversions_8w": st.column_config.NumberColumn("Google Analytics says", format="%,.0f"),
                    "platform_vs_ga4": st.column_config.NumberColumn("Difference", format="percent"),
                    "typical_status": "What it means",
                },
            )
        with c2:
            pick_label = st.selectbox("Week by week", rc["label"].tolist())
            pick = rc.loc[rc["label"] == pick_label, "campaign_name"].iloc[0]
            w = recon_wk[(recon_wk["client"] == client) & (recon_wk["campaign_name"] == pick)].melt(
                id_vars="week",
                value_vars=["platform_conversions", "ga4_conversions"],
                var_name="source",
                value_name="n",
            )
            w["source"] = w["source"].map(
                {"platform_conversions": "Ad platform", "ga4_conversions": "Google Analytics"}
            )
            f2 = px.bar(
                w,
                x="week",
                y="n",
                color="source",
                barmode="group",
                color_discrete_map={"Ad platform": ui.ORANGE, "Google Analytics": ui.TEAL},
            )
            ui.style(f2, f"{words['Results']} per week · {pick_label}", 340).update_layout(bargap=0.25)
            st.plotly_chart(f2, width="stretch")

# ---------------------------------------------------------------- 3. results
with tabs[2]:
    src = "Google Analytics" if basis == "ga4" else "each ad platform"
    ui.section("How are the ads performing?", f"Results counted by {src}. Switch in the left panel.")
    left, right = st.columns([3, 2])
    with left:
        wk = (
            client_df[client_df["date"] > as_of - pd.Timedelta(days=max(days, 56))]
            .assign(week=lambda d: d["date"].dt.to_period("W").dt.start_time)
            .assign(channel=lambda d: d["channel"].map(ui.plot_text))
            .groupby(["week", "channel"])[["spend", f"{basis}_value"]]
            .sum()
            .reset_index()
        )
        wk = wk[(wk[f"{basis}_value"] > 0) & (wk["spend"] > 0)]
        wk["roas"] = wk[f"{basis}_value"] / wk["spend"]
        f = px.line(wk, x="week", y="roas", color="channel", markers=True, line_shape="spline")
        f.update_traces(line_width=2.5, marker_size=6, hovertemplate="%{x|%b %d}: $%{y:.2f} back per $1<extra></extra>")
        ui.style(f, "Return per $1 spent, by week", 420).update_layout(yaxis_tickprefix="$")
        st.plotly_chart(f, width="stretch")
    with right:
        pacing = budget_pacing(client_df, as_of)
        month_start = as_of.replace(day=1)
        mtd = client_df[(client_df["date"] >= month_start) & (client_df["date"] <= as_of)]
        cum = mtd.groupby("date")["spend"].sum().cumsum().reset_index()
        month_days = pd.date_range(month_start, month_start + pd.offsets.MonthEnd(0))
        budget, dim = pacing["budget"], pacing["days_in_month"]
        over = pacing["status"] == "over"
        fp = go.Figure()
        fp.add_scatter(
            x=month_days,
            y=[budget * d.day / dim for d in month_days],
            name="Planned",
            line=dict(color=ui.MUTED, dash="dot", width=2),
        )
        fp.add_scatter(
            x=cum["date"],
            y=cum["spend"],
            name="Actual",
            fill="tozeroy",
            line=dict(color=ui.RED if over else ui.TEAL, width=3),
            fillcolor="rgba(214,69,69,.10)" if over else "rgba(14,124,153,.10)",
        )
        if not pd.isna(budget):
            fp.add_hline(
                y=budget,
                line=dict(color=ui.INK, width=1),
                annotation_text=f"Monthly budget ${budget:,.0f}",
                annotation_position="top left",
            )
        ui.style(fp, f"Budget this month · heading {pacing['verdict']}", 420).update_layout(
            yaxis_tickprefix="$", yaxis_tickformat=",.0f"
        )
        st.plotly_chart(fp, width="stretch")

    campaign_summary = channel_table(cur)
    ui.section("Campaign summary")
    st.dataframe(
        campaign_summary[["channel", "spend", "share_of_spend", "ga4_conversions", "cpa", "roas", "over_attribution"]],
        hide_index=True,
        width="stretch",
        column_config={
            "channel": "Campaign",
            "spend": st.column_config.NumberColumn("Spend", format="$%,.0f"),
            "share_of_spend": st.column_config.ProgressColumn(
                "Share of budget", format="percent", min_value=0, max_value=1
            ),
            "ga4_conversions": st.column_config.NumberColumn(words["Results"], format="%,.0f"),
            "cpa": st.column_config.NumberColumn(f"Cost per {words['result']}", format="$%,.2f"),
            "roas": st.column_config.NumberColumn("Return per $1", format="$%.2f"),
            "over_attribution": st.column_config.NumberColumn("Ad platform over-counts by", format="percent"),
        },
    )

# ---------------------------------------------------------------- 4. where to spend next
with tabs[3]:
    ui.section(
        "Same budget, more results",
        f"Every channel brings back less as you spend more on it. ClearSignal looks at the last "
        f"{config.FIT_DAYS} days and moves money to where the next dollar brings back the most "
        f"{words['value']}, in small steps (no channel changes by more than a third or half at once). "
        f"Brand-name search gets at most {config.BRAND_MAX_MULT - 1:.0%} more, because it can only reach "
        f"people already searching for the brand.",
    )
    if plan.empty:
        ui.callout(
            f"<b>Not enough history yet.</b> Each campaign needs at least {config.MIN_FIT_DAYS} days with "
            f"measurable results before ClearSignal can suggest a budget change."
        )
    else:
        uplift = plan_uplift(plan)
        ui.stat_row(
            [
                ("Daily budget (unchanged)", usd(plan["current_daily_spend"].sum())),
                (f"Expected extra {words['results']}", f"{uplift:+.1%}"),
                (
                    f"≈ Extra {words['value']} / month",
                    usd((plan["recommended_value"].sum() - plan["current_value"].sum()) * 30),
                ),
                ("Campaigns compared", f"{len(plan)}"),
            ]
        )
        c1, c2 = st.columns([3, 2])
        with c1:
            p = plan.sort_values("change_pct")
            fo = go.Figure(
                go.Bar(
                    y=p["channel"].map(ui.plot_text),
                    x=p["change_pct"],
                    orientation="h",
                    marker_color=[ui.GREEN if v > 0 else ui.RED for v in p["change_pct"]],
                    text=[f"{'+' if v > 0 else ''}{v:.0%}" for v in p["change_pct"]],
                    textposition="outside",
                    cliponaxis=False,
                )
            )
            ui.style(fo, "Suggested change to each campaign's budget", 120 + 52 * len(p), legend=False).update_layout(
                xaxis_tickformat="+.0%", xaxis_range=[-0.45, 0.75], bargap=0.4
            )
            st.plotly_chart(fo, width="stretch")
        with c2:
            fm = go.Figure(
                go.Bar(
                    x=plan["current_marginal_roas"],
                    y=plan["channel"].map(ui.plot_text),
                    orientation="h",
                    marker_color=ui.TEAL,
                    text=[f"${v:.2f}" for v in plan["current_marginal_roas"]],
                    textposition="outside",
                    cliponaxis=False,
                )
            )
            ui.style(fm, "What the next $1 brings back today", 120 + 52 * len(plan), legend=False).update_layout(
                yaxis=dict(categoryorder="total ascending"),
                bargap=0.4,
                xaxis_range=[0, plan["current_marginal_roas"].max() * 1.3],
            )
            st.plotly_chart(fm, width="stretch")
    ui.callout(
        "<b>How we'd use this:</b> try the change for 2 weeks on part of the budget and compare results before "
        "making it permanent. It's an estimate based on recent results, not a guarantee. Campaigns we can't "
        "measure yet (see Data health) are left out until their tracking is fixed."
    )

# ---------------------------------------------------------------- 5. weekly client email
with tabs[4]:
    ui.section(
        "This week's update for the client",
        "Written automatically from this week's numbers. The account manager reads it, adjusts if needed, and sends.",
    )
    summary = weekly_summary(client_df, client, qa, plan)
    c1, c2 = st.columns([1, 1])
    with c1:
        lines = [l for l in summary.splitlines() if l.strip()]
        head = re.sub(r"\*\*(.+?)\*\*", r"\1", lines[0])
        items = "".join("<li>" + re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ui.esc(l[2:])) + "</li>" for l in lines[1:])
        st.markdown(
            f'<div class="summary"><div style="font-weight:800;font-size:1.05rem;margin-bottom:.4rem">'
            f'{ui.esc(head)}</div><ul style="padding-left:1.1rem;margin:0">{items}</ul></div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download update", summary.replace("**", ""), f"{client.replace(' ', '_')}_weekly_update.txt"
        )
    with c2:
        ui.callout(
            "<b>Turn it into a polished email with Claude.</b> ClearSignal prepares the instructions with this "
            "week's facts and open issues, so Claude writes a short, friendly client email plus notes for the "
            "team, without inventing numbers."
        )
        prompt = client_note_prompt(client, summary, client_qa)
        with st.expander("See the instructions sent to Claude", expanded=False):
            st.code(prompt, language="markdown")
        st.download_button("Download instructions", prompt, f"{client.replace(' ', '_')}_claude_prompt.md")

# ---------------------------------------------------------------- 6. value to your agency
with tabs[5]:
    ui.section(
        "What a dedicated analyst plus ClearSignal is worth to an agency",
        "For conversations with agencies. Every number below is an assumption you can change.",
    )
    a, b = st.columns(2)
    with a:
        accounts = st.slider("Client accounts the agency reports on", 3, 60, 15)
        hrs = st.slider("Hours per client per week spent pulling and checking numbers", 1.0, 10.0, 4.0, 0.5)
        auto = st.slider("Share of that work ClearSignal does automatically (%)", 0, 90, 50, 5) / 100
    with b:
        us_cost = st.number_input(
            "Yearly cost of a US-based analyst, salary plus benefits ($)", 50_000, 250_000, 95_000, 5_000
        )
        discount = (
            st.slider("Savings with an offshore staffing partner vs a US hire (%) · typical: 60%", 0, 80, 60, 5) / 100
        )
        rate = st.number_input("What one hour of analyst time is worth to the agency ($)", 20, 300, 75, 5)
    hours_before = accounts * hrs
    hours_saved = hours_before * auto
    hire_savings = us_cost * discount
    time_value = hours_saved * 48 * rate
    cap_before = 40 / hrs
    cap_after = 40 / (hrs * (1 - auto))  # auto is at most 90%, so this never divides by zero
    ui.stat_row(
        [
            ("Hours on reporting each week", f"{hours_before:,.0f}"),
            ("Hours freed each week", f"{hours_saved:,.0f}"),
            ("Yearly saving per hire", usd(hire_savings)),
            ("Yearly value of freed time", usd(time_value)),
        ]
    )
    fc = go.Figure(
        go.Bar(
            x=["Today", "With ClearSignal"],
            y=[cap_before, cap_after],
            marker_color=[ui.MUTED, ui.TEAL],
            text=[f"{cap_before:.0f} clients", f"{cap_after:.0f} clients"],
            textposition="outside",
            cliponaxis=False,
            width=0.45,
        )
    )
    ui.style(fc, "Clients one analyst can handle", 360, legend=False).update_layout(
        yaxis_range=[0, max(cap_after, cap_before) * 1.3]
    )
    c1, c2 = st.columns([2, 3])
    with c1:
        st.plotly_chart(fc, width="stretch")
    with c2:
        ui.callout(
            f"<b>About {usd(hire_savings + time_value)} a year in value per analyst placed</b><br><br>"
            f"{usd(hire_savings)} saved compared with hiring in the US, plus {usd(time_value)} of analyst time "
            f"moved from copying numbers between tools to finding insights and talking with clients.<br><br>"
            f"Based on 48 working weeks. An illustration; the result depends on the numbers above."
        )

# ---------------------------------------------------------------- how it works
with tabs[6]:
    ui.section("How ClearSignal works")
    st.markdown(
        """
<div class="card">
<p><b>The problem.</b> When an agency takes on a client, the first weeks go to the same headaches: data that arrives twice,
campaigns that aren't tracked, ad platforms and Google Analytics disagreeing. Until those are found, every report is
quietly wrong, and clients lose trust.</p>
<p><b>What ClearSignal does, in five steps.</b></p>
<ol>
<li><b>Collect</b> results from Google Ads, Meta and Google Analytics into one place.</li>
<li><b>Check</b> the data every morning for the eight problems that most often break reports.</li>
<li><b>Compare</b> what each ad platform claims with what Google Analytics actually saw, and explain the difference.</li>
<li><b>Report</b> results, budget pacing and the return on every dollar.</li>
<li><b>Advise</b> where to move budget next, and draft the weekly client email.</li>
</ol>
<p><b>About this demo.</b> Real client data is confidential, so the demo runs on realistic sample data for three clients
(an online store, a software company and a home services business), with common real-world problems built in for
ClearSignal to catch. With real accounts, the same checks run on the agency's own data feeds.</p>
<p style="margin-bottom:0">Built by <b>Lorenzo Bernad</b>, analytics engineer.</p>
</div>""",
        unsafe_allow_html=True,
    )
