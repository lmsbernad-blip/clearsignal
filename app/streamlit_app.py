"""
ClearSignal: ad results you can trust.
Collect -> check -> compare -> report -> advise, for every agency client account.

Run:  python scripts/build_warehouse.py   then   streamlit run app/streamlit_app.py
"""
import re
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import channel_table, fit_response_curves, kpis, load, nouns, optimize_budget, weekly_summary
from prompts import client_note_prompt
import ui

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "warehouse.duckdb"
st.set_page_config(page_title="ClearSignal · Ad results you can trust", page_icon="📡", layout="wide")
ui.inject_css()

if not DB.exists():
    import subprocess, sys
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_warehouse.py")], check=True)


@st.cache_data
def table(name: str) -> pd.DataFrame:
    with duckdb.connect(str(DB), read_only=True) as con:
        return con.execute(f"select * from {name}").df()


@st.cache_data
def mart() -> pd.DataFrame:
    return load(DB)


def usd(x, dec=1):
    if pd.isna(x):
        return "-"
    for unit, div in (("M", 1e6), ("K", 1e3)):
        if abs(x) >= div:
            return f"${x / div:,.{dec}f}{unit}"
    return f"${x:,.0f}"


def pct(a, b):
    return a / b - 1 if b else float("nan")


PLATFORM_NAME = {"Google Ads": "Google Ads", "Meta Ads": "Meta (Facebook & Instagram)", "All channels": "All channels",
                 "Google Analytics": "Google Analytics"}

df = mart()
qa = table("qa_results")
recon = table("reconciliation_summary")
recon_wk = table("reconciliation_weekly")
as_of = df["date"].max()
label_of = df.drop_duplicates("campaign_name").set_index("campaign_name")["channel"].to_dict()

# ---------------------------------------------------------------- sidebar
ui.sidebar_brand()
client = st.sidebar.selectbox("Client", sorted(df["client"].unique()))
days = int(st.sidebar.radio("Time period", ["Last 7 days", "Last 30 days", "Last 90 days"], index=1).split()[1])
basis_label = st.sidebar.radio("Count results using",
                               ["Google Analytics (recommended)", "Each ad platform's own numbers"],
                               help="Google Analytics counts each sale or lead once. Ad platforms each take credit "
                                    "for the same result, so their numbers add up to more than really happened.")
basis = "ga4" if basis_label.startswith("Google") else "platform"
st.sidebar.markdown("---")
st.sidebar.markdown('<div class="side-note">Demo with realistic sample data for three agency clients. '
                    'Built by Lorenzo Bernad.</div>', unsafe_allow_html=True)

cdf = df[df["client"] == client]
n = nouns(cdf)
cur = cdf[cdf["date"] > as_of - pd.Timedelta(days=days)]
prev = cdf[(cdf["date"] <= as_of - pd.Timedelta(days=days)) & (cdf["date"] > as_of - pd.Timedelta(days=2 * days))]
k, k0 = kpis(cur, basis), kpis(prev, basis)
cqa = qa[qa["client"] == client]
model = "Online store" if n["result"] == "sale" else "Lead generation"
channels = " and ".join(sorted({PLATFORM_NAME.get(p, p).split(" (")[0] for p in cdf["platform"].unique()}))

# ---------------------------------------------------------------- header
ui.hero(client, f"{model} · advertising on {channels} · last {days} days compared with the {days} days before",
        int((cqa["severity"] == "High").sum()), f"{as_of:%b %-d, %Y}")

daily = cur.groupby("date").agg(spend=("spend", "sum"), value=(f"{basis}_value", "sum"),
                                conv=(f"{basis}_conversions", "sum")).reset_index()
daily["roas"] = daily["value"] / daily["spend"]
daily["cpa"] = daily["spend"] / daily["conv"].replace(0, float("nan"))
ui.kpi_cards([
    ("Ad spend", usd(k["spend"]), pct(k["spend"], k0["spend"]), True, daily["spend"], ui.TEAL),
    (n["Value"], usd(k["value"]), pct(k["value"], k0["value"]), True, daily["value"], ui.TEAL),
    ("Return per $1 spent", f"${k['roas']:.2f}", pct(k["roas"], k0["roas"]), True, daily["roas"], ui.ORANGE),
    (f"Cost per {n['result']}", usd(k["cpa"], 0) if k["cpa"] < 1000 else usd(k["cpa"]), pct(k["cpa"], k0["cpa"]), False,
     daily["cpa"], ui.ORANGE),
    (n["Results"], f"{k['conversions']:,.0f}", pct(k["conversions"], k0["conversions"]), True, daily["conv"], ui.TEAL),
])

tabs = st.tabs(["Data health", "Do the numbers match?", "Results", "Where to spend next", "Weekly client email",
                "Value to your agency", "How it works"])

# ---------------------------------------------------------------- 1. data health
with tabs[0]:
    ui.section("Can we trust today's numbers?",
               "Every morning ClearSignal checks the data behind each client report. Each card below is a problem "
               "that would make a report wrong, with what it means and what we're doing about it.")
    ui.stat_row([("Issues across all clients", f"{len(qa)}"),
                 ("Need fixing now", f"{int((qa['severity'] == 'High').sum())}"),
                 ("For this client", f"{len(cqa)}"),
                 ("Ad spend affected", usd(qa["usd_at_risk"].sum()))])
    scope = st.segmented_control("Show", ["This client", "All clients"], default="This client", label_visibility="collapsed")
    view = qa if scope == "All clients" else cqa
    if view.empty:
        ui.callout("<b>Everything checks out.</b> This client's report can be shared as is.")
    order = {"High": 0, "Medium": 1}
    for r in view.assign(o=view["severity"].map(order)).sort_values(["o", "client"]).itertuples():
        where = label_of.get(r.object, r.object)
        ui.issue_card(r.severity, r.title, r.client, PLATFORM_NAME.get(r.platform, r.platform), where, r.detail,
                      r.usd_at_risk, r.action)

# ---------------------------------------------------------------- 2. do the numbers match
STATUS_COLOR = {
    "Matches (within 20%)": ui.GREEN,
    "Normal: Meta also counts people who only saw an ad": ui.TEAL,
    "Fix: not visible in Google Analytics": ui.RED,
    "Fix: new campaign not set up in reporting": ui.RED,
    "Fix: ad platform stopped counting": ui.RED,
    "Needs a closer look": ui.AMBER,
}
with tabs[1]:
    ui.section(f"Do the ad platforms and Google Analytics agree on {n['results']}?",
               "Ad platforms usually report more results than Google Analytics, because each one takes credit for the "
               "same customer. Some difference is normal; a big or sudden one usually means broken tracking. "
               "Last 8 weeks, compared week by week.")
    rc = recon[recon["client"] == client].copy()
    rc["label"] = rc["campaign_name"].map(label_of).fillna(rc["campaign_name"])
    rc["gap"] = rc["platform_vs_ga4"].fillna(1.0)
    fig = go.Figure()
    for status, g in rc.groupby("typical_status"):
        fig.add_bar(y=g["label"], x=g["gap"], orientation="h", name=status,
                    marker_color=STATUS_COLOR.get(status, ui.MUTED), marker_line_width=0,
                    text=[("not visible in Google Analytics" if pd.isna(v) else f"{v:+.0%}") for v in g["platform_vs_ga4"]],
                    textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}<br>Ad platform reports %{text} vs Google Analytics<extra></extra>")
    fig.add_vrect(x0=-0.2, x1=0.2, fillcolor=ui.GREEN, opacity=0.06, line_width=0)
    ui.style(fig, f"How many more {n['results']} the ad platform reports than Google Analytics", 160 + 48 * len(rc))
    fig.update_layout(barmode="overlay", bargap=0.35, xaxis=dict(range=[-0.25, 1.45], showticklabels=False, ticks=""),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns([3, 2])
    with c1:
        show = rc.assign(campaign=rc["label"])[["campaign", "spend_8w", "platform_conversions_8w", "ga4_conversions_8w",
                                                 "platform_vs_ga4", "typical_status"]]
        st.dataframe(show, hide_index=True, width="stretch", height=min(420, 40 + 36 * len(rc)), column_config={
            "campaign": "Campaign",
            "spend_8w": st.column_config.NumberColumn("Spend (8 weeks)", format="$%,.0f"),
            "platform_conversions_8w": st.column_config.NumberColumn(f"Ad platform says", format="%,.0f"),
            "ga4_conversions_8w": st.column_config.NumberColumn(f"Google Analytics says", format="%,.0f"),
            "platform_vs_ga4": st.column_config.NumberColumn("Difference", format="percent"),
            "typical_status": "What it means"})
    with c2:
        pick_label = st.selectbox("Week by week", rc["label"].tolist())
        pick = rc.loc[rc["label"] == pick_label, "campaign_name"].iloc[0]
        w = recon_wk[recon_wk["campaign_name"] == pick].melt(
            id_vars="week", value_vars=["platform_conversions", "ga4_conversions"], var_name="source", value_name="n")
        w["source"] = w["source"].map({"platform_conversions": "Ad platform", "ga4_conversions": "Google Analytics"})
        f2 = px.bar(w, x="week", y="n", color="source", barmode="group",
                    color_discrete_map={"Ad platform": ui.ORANGE, "Google Analytics": ui.TEAL})
        ui.style(f2, f"{n['Results']} per week · {pick_label}", 340).update_layout(bargap=0.25)
        st.plotly_chart(f2, width="stretch")

# ---------------------------------------------------------------- 3. results
with tabs[2]:
    src = "Google Analytics" if basis == "ga4" else "each ad platform"
    ui.section("How are the ads performing?", f"Results counted by {src}. Switch in the left panel.")
    left, right = st.columns([3, 2])
    with left:
        wk = (cdf[cdf["date"] > as_of - pd.Timedelta(days=max(days, 56))]
              .assign(week=lambda d: d["date"].dt.to_period("W").dt.start_time)
              .groupby(["week", "channel"])[["spend", f"{basis}_value"]].sum().reset_index())
        wk = wk[wk[f"{basis}_value"] > 0]
        wk["roas"] = wk[f"{basis}_value"] / wk["spend"]
        f = px.line(wk, x="week", y="roas", color="channel", markers=True, line_shape="spline")
        f.update_traces(line_width=2.5, marker_size=6, hovertemplate="%{x|%b %d}: $%{y:.2f} back per $1<extra></extra>")
        ui.style(f, "Return per $1 spent, by week", 420).update_layout(yaxis_tickprefix="$")
        st.plotly_chart(f, width="stretch")
    with right:
        mtd = cdf[cdf["date"] >= as_of.replace(day=1)]
        budget = mtd["monthly_budget"].max()
        dim = (as_of.replace(day=1) + pd.offsets.MonthEnd(0)).day
        cum = mtd.groupby("date")["spend"].sum().cumsum().reset_index()
        month_days = pd.date_range(as_of.replace(day=1), as_of.replace(day=1) + pd.offsets.MonthEnd(0))
        projected = mtd["spend"].sum() / as_of.day * dim
        pace = projected / budget
        fp = go.Figure()
        fp.add_scatter(x=month_days, y=[budget * d.day / dim for d in month_days], name="Planned",
                       line=dict(color=ui.MUTED, dash="dot", width=2))
        fp.add_scatter(x=cum["date"], y=cum["spend"], name="Actual", fill="tozeroy",
                       line=dict(color=ui.RED if pace > 1.1 else ui.TEAL, width=3),
                       fillcolor="rgba(214,69,69,.10)" if pace > 1.1 else "rgba(14,124,153,.10)")
        fp.add_hline(y=budget, line=dict(color=ui.INK, width=1), annotation_text=f"Monthly budget ${budget:,.0f}",
                     annotation_position="top left")
        verdict = "on track" if 0.9 <= pace <= 1.1 else (f"{pace - 1:.0%} over budget" if pace > 1 else f"{1 - pace:.0%} under budget")
        ui.style(fp, f"Budget this month · heading {verdict}", 420).update_layout(yaxis_tickprefix="$", yaxis_tickformat=",.0f")
        st.plotly_chart(fp, width="stretch")

    ct = channel_table(cur)
    ui.section("Campaign summary")
    st.dataframe(ct[["channel", "spend", "share_of_spend", "ga4_conversions", "cpa", "roas", "over_attribution"]],
                 hide_index=True, width="stretch", column_config={
                     "channel": "Campaign",
                     "spend": st.column_config.NumberColumn("Spend", format="$%,.0f"),
                     "share_of_spend": st.column_config.ProgressColumn("Share of budget", format="percent", min_value=0, max_value=1),
                     "ga4_conversions": st.column_config.NumberColumn(n["Results"], format="%,.0f"),
                     "cpa": st.column_config.NumberColumn(f"Cost per {n['result']}", format="$%,.2f"),
                     "roas": st.column_config.NumberColumn("Return per $1", format="$%.2f"),
                     "over_attribution": st.column_config.NumberColumn("Ad platform over-counts by", format="percent")})

# ---------------------------------------------------------------- 4. where to spend next
with tabs[3]:
    ui.section("Same budget, more results",
               f"Every channel brings back less as you spend more on it. ClearSignal looks at the last 60 days and moves "
               f"money to where the next dollar brings back the most {n['value']}, in small steps (no channel changes by more "
               f"than a third or half at once). Brand-name search gets at most 10% more, because it can only reach people "
               f"already searching for the brand.")
    plan = optimize_budget(fit_response_curves(cdf))
    uplift = plan["recommended_value"].sum() / plan["current_value"].sum() - 1
    ui.stat_row([("Daily budget (unchanged)", usd(plan["current_daily_spend"].sum())),
                 (f"Expected extra {n['results']}", f"{uplift:+.1%}"),
                 (f"≈ Extra {n['value']} / month", usd((plan["recommended_value"].sum() - plan["current_value"].sum()) * 30)),
                 ("Campaigns compared", f"{len(plan)}")])
    c1, c2 = st.columns([3, 2])
    with c1:
        p = plan.sort_values("change_pct")
        fo = go.Figure(go.Bar(y=p["channel"], x=p["change_pct"], orientation="h",
                              marker_color=[ui.GREEN if v > 0 else ui.RED for v in p["change_pct"]],
                              text=[f"{'+' if v > 0 else ''}{v:.0%}" for v in p["change_pct"]],
                              textposition="outside", cliponaxis=False))
        ui.style(fo, "Suggested change to each campaign's budget", 120 + 52 * len(p), legend=False).update_layout(
            xaxis_tickformat="+.0%", xaxis_range=[-0.45, 0.75], bargap=0.4)
        st.plotly_chart(fo, width="stretch")
    with c2:
        fm = go.Figure(go.Bar(x=plan["current_marginal_roas"], y=plan["channel"], orientation="h",
                              marker_color=ui.TEAL, text=[f"${v:.2f}" for v in plan["current_marginal_roas"]],
                              textposition="outside", cliponaxis=False))
        ui.style(fm, "What the next $1 brings back today", 120 + 52 * len(plan), legend=False).update_layout(
            yaxis=dict(categoryorder="total ascending"), bargap=0.4,
            xaxis_range=[0, plan["current_marginal_roas"].max() * 1.3])
        st.plotly_chart(fm, width="stretch")
    ui.callout("<b>How we'd use this:</b> try the change for 2 weeks on part of the budget and compare results before "
               "making it permanent. It's an estimate based on recent results, not a guarantee. Campaigns we can't measure "
               "yet (see Data health) are left out until their tracking is fixed.")

# ---------------------------------------------------------------- 5. weekly client email
with tabs[4]:
    ui.section("This week's update for the client",
               "Written automatically from this week's numbers. The account manager reads it, adjusts if needed, and sends.")
    plan = optimize_budget(fit_response_curves(cdf))
    summary = weekly_summary(cdf, client, qa, plan)
    c1, c2 = st.columns([1, 1])
    with c1:
        lines = [l for l in summary.splitlines() if l.strip()]
        head = re.sub(r"\*\*(.+?)\*\*", r"\1", lines[0])
        items = "".join("<li>" + re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", ui.esc(l[2:])) + "</li>" for l in lines[1:])
        st.markdown(f'<div class="summary"><div style="font-weight:800;font-size:1.05rem;margin-bottom:.4rem">'
                    f'{ui.esc(head)}</div><ul style="padding-left:1.1rem;margin:0">{items}</ul></div>', unsafe_allow_html=True)
        st.download_button("Download update", summary.replace("**", ""), f"{client.replace(' ', '_')}_weekly_update.txt")
    with c2:
        ui.callout("<b>Turn it into a polished email with Claude.</b> ClearSignal prepares the instructions with this week's "
                   "facts and open issues, so Claude writes a short, friendly client email plus notes for the team, "
                   "without inventing numbers.")
        prompt = client_note_prompt(client, summary, cqa)
        with st.expander("See the instructions sent to Claude", expanded=False):
            st.code(prompt, language="markdown")
        st.download_button("Download instructions", prompt, f"{client.replace(' ', '_')}_claude_prompt.md")

# ---------------------------------------------------------------- 6. value to your agency
with tabs[5]:
    ui.section("What a dedicated analyst plus ClearSignal is worth to an agency",
               "For conversations with agencies. Every number below is an assumption you can change.")
    a, b = st.columns(2)
    with a:
        accounts = st.slider("Client accounts the agency reports on", 3, 60, 15)
        hrs = st.slider("Hours per client per week spent pulling and checking numbers", 1.0, 10.0, 4.0, 0.5)
        auto = st.slider("Share of that work ClearSignal does automatically (%)", 0, 90, 50, 5) / 100
    with b:
        us_cost = st.number_input("Yearly cost of a US-based analyst, salary plus benefits ($)", 50_000, 250_000, 95_000, 5_000)
        discount = st.slider("Savings with an offshore staffing partner vs a US hire (%) · typical: 60%", 0, 80, 60, 5) / 100
        rate = st.number_input("What one hour of analyst time is worth to the agency ($)", 20, 300, 75, 5)
    hours_before = accounts * hrs
    hours_saved = hours_before * auto
    hire_savings = us_cost * discount
    time_value = hours_saved * 48 * rate
    cap_before = 40 / hrs
    cap_after = 40 / (hrs * (1 - auto)) if auto < 1 else float("inf")
    ui.stat_row([("Hours on reporting each week", f"{hours_before:,.0f}"), ("Hours freed each week", f"{hours_saved:,.0f}"),
                 ("Yearly saving per hire", usd(hire_savings)), ("Yearly value of freed time", usd(time_value))])
    fc = go.Figure(go.Bar(x=["Today", "With ClearSignal"], y=[cap_before, cap_after], marker_color=[ui.MUTED, ui.TEAL],
                          text=[f"{cap_before:.0f} clients", f"{cap_after:.0f} clients"], textposition="outside",
                          cliponaxis=False, width=0.45))
    ui.style(fc, "Clients one analyst can handle", 360, legend=False).update_layout(
        yaxis_range=[0, max(cap_after, cap_before) * 1.3])
    c1, c2 = st.columns([2, 3])
    with c1:
        st.plotly_chart(fc, width="stretch")
    with c2:
        ui.callout(f"<b>About {usd(hire_savings + time_value)} a year in value per analyst placed</b><br><br>"
                   f"{usd(hire_savings)} saved compared with hiring in the US, plus {usd(time_value)} of analyst time moved "
                   f"from copying numbers between tools to finding insights and talking with clients.<br><br>"
                   f"Based on 48 working weeks. An illustration; the result depends on the numbers above.")

# ---------------------------------------------------------------- how it works
with tabs[6]:
    ui.section("How ClearSignal works")
    st.markdown("""
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
</div>""", unsafe_allow_html=True)
