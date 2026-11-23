"""Visual layer: theme, CSS, and small HTML components used by the app."""

from __future__ import annotations

import html
from collections.abc import Iterable

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

INK = "#0F1E2E"
TEAL = "#0E7C99"
TEAL_LIGHT = "#E3F2F6"
ORANGE = "#F08A3E"
GREEN = "#1F9D6B"
RED = "#D64545"
AMBER = "#D99A06"
MUTED = "#64748B"
LINE = "#E6EBF0"
BG = "#F5F7FA"
SERIES = [TEAL, ORANGE, "#4C5BD4", "#2BB3A3", "#C2410C", "#7C8BA1", "#9B5DE5", "#E0B000"]

# ------------------------------------------------------------------ plotly theme
pio.templates["kit"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK),
        colorway=SERIES,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=36, b=8),
        xaxis=dict(showgrid=False, linecolor=LINE, ticks="outside", tickcolor=LINE, title=None),
        yaxis=dict(gridcolor=LINE, zeroline=False, title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None, font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(color=INK)),
        title=dict(font=dict(size=15, color=INK), x=0, xanchor="left"),
    )
)
pio.templates.default = "plotly_white+kit"


def inject_css() -> None:
    """Add the app's stylesheet (fonts, sidebar, hero, cards, tabs) to the page."""
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input {{ font-family: 'Inter', system-ui, sans-serif; }}
.stApp {{ background: {BG}; }}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {{ visibility: hidden; }}
[data-testid="stHeader"] {{ background: transparent; height: 0; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1320px; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {INK} 0%, #13324A 100%); }}
[data-testid="stSidebar"] * {{ color: #E8EEF4 !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"] {{ background: rgba(255,255,255,.10) !important;
  border: 1px solid rgba(255,255,255,.25) !important; border-radius: 10px !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] input {{ color:#fff !important; -webkit-text-fill-color:#fff !important;
  font-weight:600; background: transparent !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] button svg {{ fill:#fff !important; color:#fff !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.12); }}
.brand {{ display:flex; align-items:center; gap:.65rem; margin:.2rem 0 1.2rem; }}
.brand-mark {{ width:38px; height:38px; border-radius:11px; background:linear-gradient(135deg,{TEAL},{ORANGE});
  display:flex; align-items:center; justify-content:center; font-weight:800; color:#fff; font-size:1rem; }}
.brand-name {{ font-weight:700; font-size:1.02rem; line-height:1.15; }}
.brand-sub {{ font-size:.74rem; opacity:.65; }}
.side-note {{ font-size:.75rem; opacity:.6; line-height:1.45; margin-top:1rem; }}

/* hero */
.hero {{ background: radial-gradient(1200px 300px at 85% -40%, rgba(240,138,62,.45), transparent 60%),
         linear-gradient(120deg, {INK} 0%, #12405A 55%, {TEAL} 100%);
         border-radius: 20px; padding: 1.6rem 1.9rem; color: #fff; margin-bottom: 1.1rem;
         box-shadow: 0 10px 30px rgba(15,30,46,.18); }}
.hero-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; flex-wrap:wrap; }}
.eyebrow {{ text-transform:uppercase; letter-spacing:.12em; font-size:.72rem; opacity:.75; font-weight:600; }}
.hero h1 {{ font-size:2rem; font-weight:800; margin:.15rem 0 .25rem; color:#fff; letter-spacing:-.02em; }}
.hero p {{ margin:0; opacity:.82; font-size:.92rem; }}
.pill {{ display:inline-flex; align-items:center; gap:.4rem; padding:.38rem .8rem; border-radius:999px;
  font-size:.8rem; font-weight:600; white-space:nowrap; }}
.pill-red {{ background:rgba(214,69,69,.18); color:#FFD6D6; border:1px solid rgba(255,140,140,.45); }}
.pill-green {{ background:rgba(31,157,107,.2); color:#CFF5E4; border:1px solid rgba(120,220,180,.45); }}
.dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
.steps {{ display:flex; gap:.45rem; margin-top:1.1rem; flex-wrap:wrap; }}
.step {{ background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18); padding:.3rem .7rem;
  border-radius:999px; font-size:.76rem; font-weight:500; }}
.step b {{ color:{ORANGE}; margin-right:.25rem; }}

/* kpi cards */
.kpis {{ display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:.85rem; margin-bottom:1.2rem; }}
@media (max-width: 1000px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
.kpi {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:1rem 1.05rem .7rem;
  box-shadow:0 1px 2px rgba(15,30,46,.04); }}
.kpi-label {{ color:{MUTED}; font-size:.78rem; font-weight:600; text-transform:uppercase; letter-spacing:.06em; }}
.kpi-value {{ font-size:1.65rem; font-weight:800; color:{INK}; letter-spacing:-.02em; margin:.2rem 0 .15rem; }}
.delta {{ font-size:.78rem; font-weight:700; padding:.12rem .45rem; border-radius:6px; }}
.delta-good {{ color:{GREEN}; background:#E6F6EF; }}
.delta-bad {{ color:{RED}; background:#FCEAEA; }}
.delta-flat {{ color:{MUTED}; background:#EEF2F6; }}
.kpi svg {{ display:block; margin-top:.45rem; }}

/* tabs as pills */
.stTabs [role="tablist"] {{ gap:.3rem; background:#fff; padding:.35rem; border-radius:14px; border:1px solid {LINE};
  box-shadow:0 1px 2px rgba(15,30,46,.04); overflow-x:auto; }}
.stTabs [data-testid="stTab"] {{ padding:.55rem 1rem !important; border-radius:10px; margin:0 !important; cursor:pointer;
  transition: background .15s; }}
.stTabs [data-testid="stTab"] p {{ font-weight:600; font-size:.88rem; color:{MUTED} !important; margin:0; white-space:nowrap; }}
.stTabs [data-testid="stTab"]:hover {{ background:#F1F5F9; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background:{INK} !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color:#fff !important; }}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none !important; }}

/* section header */
.sec {{ margin:1.3rem 0 .6rem; }}
.sec h3 {{ font-size:1.15rem; font-weight:750; color:{INK}; margin:0; letter-spacing:-.01em; }}
.sec p {{ color:{MUTED}; margin:.25rem 0 0; font-size:.88rem; }}

/* cards */
.card {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:1rem 1.15rem;
  box-shadow:0 1px 2px rgba(15,30,46,.04); }}
.issue {{ background:#fff; border:1px solid {LINE}; border-left:5px solid var(--c); border-radius:14px;
  padding:.9rem 1.1rem; margin-bottom:.65rem; }}
.issue-top {{ display:flex; justify-content:space-between; gap:1rem; align-items:center; flex-wrap:wrap; }}
.issue-title {{ font-weight:700; color:{INK}; font-size:.98rem; }}
.issue-detail {{ color:#334155; font-size:.88rem; margin-top:.4rem; line-height:1.5; }}
.chips {{ display:flex; gap:.35rem; flex-wrap:wrap; margin-top:.45rem; }}
.chip {{ font-size:.72rem; font-weight:600; padding:.18rem .55rem; border-radius:999px; background:#EEF2F6; color:#475569; }}
.chip-mono {{ font-family: ui-monospace, Menlo, monospace; font-weight:500; }}
.badge {{ font-size:.7rem; font-weight:800; letter-spacing:.06em; text-transform:uppercase; padding:.2rem .55rem;
  border-radius:6px; color:#fff; background:var(--c); }}
.issue-action {{ margin-top:.55rem; padding-top:.55rem; border-top:1px dashed #E2E8F0; color:#0B4F61; font-size:.86rem; }}
.impact {{ font-weight:700; color:{INK}; font-size:.9rem; }}
.stat-row {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:.85rem; margin:.4rem 0 1rem; }}
.stat {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:.8rem 1rem; }}
.stat-v {{ font-size:1.4rem; font-weight:800; color:{INK}; }}
.stat-l {{ font-size:.76rem; color:{MUTED}; font-weight:600; text-transform:uppercase; letter-spacing:.05em; }}
.callout {{ background:{TEAL_LIGHT}; border:1px solid #BFE1EA; border-radius:14px; padding:.9rem 1.1rem; color:#0B4F61; font-size:.9rem; }}
.callout b {{ color:{INK}; }}
.summary {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:1.2rem 1.4rem; line-height:1.65; }}

[data-testid="stDataFrame"] {{ border:1px solid {LINE}; border-radius:14px; overflow:hidden; background:#fff; }}
[data-testid="stPlotlyChart"] {{ background:#fff; border:1px solid {LINE}; border-radius:16px; padding:.5rem .6rem; }}
.stDownloadButton button, .stButton button {{ border-radius:10px; font-weight:600; border:1px solid {LINE}; }}
</style>""",
        unsafe_allow_html=True,
    )


def style(fig: go.Figure, title: str = "", height: int = 380, legend: bool = True) -> go.Figure:
    """Consistent chart chrome: title top-left, legend below, no axis titles."""
    fig.update_layout(
        title=dict(
            text=f"<b>{plot_text(title)}</b>" if title else None, x=0.01, y=0.97, yanchor="top", font=dict(size=15)
        ),
        height=height,
        showlegend=legend,
        margin=dict(l=8, r=16, t=56 if title else 16, b=48 if legend else 8),
        legend=dict(orientation="h", yanchor="top", y=-0.16, x=0, title_text=""),
        xaxis_title=None,
        yaxis_title=None,
    )
    return fig


def esc(x: object) -> str:
    """HTML-escape any value before it goes into markup rendered with unsafe_allow_html."""
    return html.escape(str(x))


def plot_text(x: object) -> str:
    """Escape text for Plotly, which renders tags such as <b> and <a href> in titles, labels and legends."""
    return html.escape(str(x), quote=False)


def sidebar_brand() -> None:
    """ClearSignal logo and tagline at the top of the sidebar."""
    st.sidebar.markdown(
        """<div class="brand"><div class="brand-mark">CS</div>
      <div><div class="brand-name">ClearSignal</div><div class="brand-sub">Ad results you can trust</div></div></div>""",
        unsafe_allow_html=True,
    )


def hero(client: str, subtitle: str, n_high: int, as_of: str) -> None:
    """Page header: client name, subtitle, data date and a pill with the number of High issues."""
    pill = (
        (
            f'<span class="pill pill-red"><span class="dot" style="background:#FF7A7A"></span>{n_high} data '
            f"issue{'s' if n_high != 1 else ''} to fix</span>"
        )
        if n_high
        else '<span class="pill pill-green"><span class="dot" style="background:#6EE7B7"></span>Numbers checked and ready</span>'
    )
    steps = "".join(
        f'<span class="step"><b>{i}</b>{s}</span>'
        for i, s in enumerate(["Collect", "Check", "Compare", "Report", "Advise"], 1)
    )
    st.markdown(
        f"""<div class="hero"><div class="hero-top"><div>
      <div class="eyebrow">ClearSignal · numbers up to {esc(as_of)}</div>
      <h1>{esc(client)}</h1><p>{esc(subtitle)}</p></div>{pill}</div>
      <div class="steps">{steps}</div></div>""",
        unsafe_allow_html=True,
    )


def sparkline(values: Iterable[float], color: str = TEAL, w: int = 180, h: int = 38) -> str:
    """Small inline SVG trend line (lightly smoothed); empty string when there are fewer than 2 points."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) >= 7:  # light smoothing so the trend reads, not the daily noise
        v = np.convolve(v, np.ones(3) / 3, mode="valid")
    if len(v) < 2:
        return ""
    lo, hi = v.min(), v.max()
    rng = hi - lo or 1
    xs = np.linspace(0, w, len(v))
    ys = h - 3 - (v - lo) / rng * (h - 6)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys, strict=True))
    area = f"0,{h} " + pts + f" {w},{h}"
    gid = f"g{abs(hash((color, len(v), round(v.sum(), 2)))) % 10**8}"
    return (
        f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{gid})"/><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"'
        f' stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def kpi_cards(items: list[tuple]) -> None:
    """Row of KPI cards. items: (label, value_str, delta or None, good_when_up, spark_values, color).

    The change is shown with an arrow and a sign, not only a color.
    """
    cards = []
    for label, value, delta, up_good, spark, color in items:
        if delta is None or np.isnan(delta):
            d = '<span class="delta delta-flat">n/a</span>'
        else:
            cls = "delta-flat" if abs(delta) < 0.005 else ("delta-good" if (delta > 0) == up_good else "delta-bad")
            arrow = "▲" if delta > 0 else "▼"
            d = f'<span class="delta {cls}">{arrow} {abs(delta):.1%}</span>'
        cards.append(
            f'<div class="kpi"><div class="kpi-label">{esc(label)}</div><div class="kpi-value">{esc(value)}</div>'
            f"{d}{sparkline(spark, color)}</div>"
        )
    st.markdown(f'<div class="kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


def section(title: str, text: str = "") -> None:
    """Section heading with an optional one-line explanation."""
    st.markdown(
        f'<div class="sec"><h3>{esc(title)}</h3>{f"<p>{esc(text)}</p>" if text else ""}</div>', unsafe_allow_html=True
    )


def issue_card(
    severity: str,
    title: str,
    client: str,
    platform: str,
    where: str,
    detail: str,
    usd: float | None = None,
    action: str = "",
) -> None:
    """One data-health issue: severity badge with a text label, title, chips, detail and next step."""
    color = RED if severity == "High" else AMBER
    label = "Fix now" if severity == "High" else "Watch"
    impact = (
        f'<span class="impact">${usd:,.0f} of ad spend affected</span>' if usd is not None and not np.isnan(usd) else ""
    )
    act = f'<div class="issue-action"><b>Next step:</b> {esc(action)}</div>' if action else ""
    st.markdown(
        f"""<div class="issue" style="--c:{color}"><div class="issue-top">
      <div style="display:flex;gap:.6rem;align-items:center"><span class="badge" style="--c:{color}">{label}</span>
      <span class="issue-title">{esc(title)}</span></div>{impact}</div>
      <div class="chips"><span class="chip">{esc(client)}</span><span class="chip">{esc(platform)}</span>
      <span class="chip">{esc(where)}</span></div>
      <div class="issue-detail">{esc(detail)}</div>{act}</div>""",
        unsafe_allow_html=True,
    )


def stat_row(items: list[tuple[str, str]]) -> None:
    """Row of up to four labelled numbers. items: (label, value)."""
    st.markdown(
        '<div class="stat-row">'
        + "".join(
            f'<div class="stat"><div class="stat-l">{esc(l)}</div><div class="stat-v">{esc(v)}</div></div>'
            for l, v in items
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def callout(md_html: str) -> None:
    """Highlighted note. `md_html` is trusted markup written in the code, never data."""
    st.markdown(f'<div class="callout">{md_html}</div>', unsafe_allow_html=True)
