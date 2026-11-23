"""Visual layer: theme, CSS, motion and small HTML components used by the app.

Design idea, "from noise to signal": the header shows a jittery grey trace resolving into a clean teal
signal; KPI cards read like instrument readouts; data issues carry a signal-strength glyph; sections are
numbered like instrument channels. Every animation is short, runs once (or is a slow ambient loop in
the header), and is switched off for anyone who asks their system for reduced motion.
"""

from __future__ import annotations

import html
import math
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

DISPLAY = "'Space Grotesk', 'Inter', system-ui, sans-serif"
BODY = "'Inter', system-ui, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, Menlo, monospace"

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
        hoverlabel=dict(bgcolor="white", bordercolor=LINE, font=dict(color=INK, family="JetBrains Mono, monospace")),
        title=dict(font=dict(size=15, color=INK, family="Space Grotesk, Inter, sans-serif"), x=0, xanchor="left"),
    )
)
pio.templates.default = "plotly_white+kit"


def inject_css() -> None:
    """Add the app's stylesheet (fonts, sidebar, header, readouts, cards, tabs, motion) to the page."""
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input {{ font-family: {BODY}; }}
/* graph-paper background: a faint dot grid, like an instrument screen */
.stApp {{ background-color: {BG};
  background-image: radial-gradient(rgba(15,30,46,.07) 1px, transparent 1px);
  background-size: 22px 22px; }}
/* Hide Streamlit's own menu, deploy button and footer, but NOT the toolbar itself: the button that reopens a
   collapsed sidebar lives inside it, and hiding the toolbar made the sidebar impossible to bring back. */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stMainMenu"], [data-testid="stMainMenuButton"],
[data-testid="stAppDeployButton"], [data-testid="stToolbarActions"] {{ display: none !important; }}
[data-testid="stToolbar"] {{ background: transparent; }}
/* Reopen-sidebar control: always visible, styled as a clear "Filters" tab */
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] {{ visibility: visible !important;
  opacity: 1 !important; z-index: 1000; }}
[data-testid="stExpandSidebarButton"] {{ width:auto !important; height:auto !important; padding:.42rem .75rem !important;
  background:{INK} !important; color:#fff !important; border-radius:3px 10px 3px 10px !important;
  box-shadow: 0 8px 18px -8px rgba(15,30,46,.6); display:inline-flex !important; align-items:center; gap:.4rem; }}
[data-testid="stExpandSidebarButton"] svg, [data-testid="stExpandSidebarButton"] span {{ color:#fff !important; fill:#fff !important; }}
[data-testid="stExpandSidebarButton"]::after {{ content:"Filters"; font-family:{MONO}; font-size:.7rem; letter-spacing:.08em;
  text-transform:uppercase; }}
[data-testid="stExpandSidebarButton"]:hover {{ background:{TEAL} !important; }}
/* Collapse control inside the sidebar: always visible (Streamlit shows it only on hover) */
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapseButton"] button {{ visibility: visible !important; opacity: .75; }}
[data-testid="stHeader"] {{ background: transparent; height: 0; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1320px; }}
@media (max-width: 900px) {{ .block-container {{ padding-top: 3.6rem; }} }}  /* room for the Filters tab */

/* ---------------------------------------------------------------- motion */
@keyframes rise {{ from {{ opacity:0; transform: translateY(10px); }} to {{ opacity:1; transform:none; }} }}
@keyframes fade {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
@keyframes sweep {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
@keyframes draw {{ from {{ stroke-dashoffset: var(--len, 1200); }} to {{ stroke-dashoffset: 0; }} }}
@keyframes jitter {{ 0%,100% {{ transform: translateY(0); }} 25% {{ transform: translateY(-1.5px); }}
                    50% {{ transform: translateY(1px); }} 75% {{ transform: translateY(-.5px); }} }}
@keyframes scan {{ from {{ transform: translateX(-10%); }} to {{ transform: translateX(110%); }} }}
@keyframes travel {{ from {{ left: 0%; }} to {{ left: 100%; }} }}
@keyframes ping {{ 0% {{ box-shadow: 0 0 0 0 var(--ring); }} 80%,100% {{ box-shadow: 0 0 0 9px transparent; }} }}
@keyframes bars {{ from {{ transform: scaleY(.15); }} to {{ transform: scaleY(1); }} }}
@keyframes digits {{ from {{ opacity:0; transform: translateY(60%); filter: blur(3px); }}
                    to {{ opacity:1; transform:none; filter:none; }} }}
.rise {{ animation: rise .6s cubic-bezier(.2,.7,.2,1) both; animation-delay: calc(var(--i, 0) * 70ms); }}
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{ animation: rise .7s cubic-bezier(.2,.7,.2,1) both .15s; }}
[data-baseweb="tab-panel"], [role="tabpanel"] {{ animation: fade .35s ease both; }}

/* ---------------------------------------------------------------- sidebar */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {INK} 0%, #13324A 100%); }}
[data-testid="stSidebar"] * {{ color: #E8EEF4 !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"] {{ background: rgba(255,255,255,.10) !important;
  border: 1px solid rgba(255,255,255,.25) !important; border-radius: 10px !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] input {{ color:#fff !important; -webkit-text-fill-color:#fff !important;
  font-weight:600; background: transparent !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] button svg {{ fill:#fff !important; color:#fff !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.12); }}
.brand {{ display:flex; align-items:center; gap:.7rem; margin:.2rem 0 1.2rem; }}
.brand-mark {{ width:40px; height:40px; border-radius:12px; background: rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.18); display:flex; align-items:flex-end; justify-content:center; gap:3px;
  padding:0 0 9px; box-sizing:border-box; }}
.brand-mark i {{ width:4px; border-radius:2px; background:{ORANGE}; transform-origin: bottom;
  animation: bars .9s cubic-bezier(.2,.7,.2,1) both; }}
.brand-mark i:nth-child(1) {{ height:8px; animation-delay:.05s; background:#7FB8C9; }}
.brand-mark i:nth-child(2) {{ height:14px; animation-delay:.15s; background:#3FA3BE; }}
.brand-mark i:nth-child(3) {{ height:20px; animation-delay:.25s; }}
.brand-name {{ font-family:{DISPLAY}; font-weight:700; font-size:1.08rem; line-height:1.1; letter-spacing:-.01em; }}
.brand-sub {{ font-family:{MONO}; font-size:.66rem; opacity:.6; letter-spacing:.04em; text-transform:uppercase; }}
.side-note {{ font-size:.75rem; opacity:.6; line-height:1.45; margin-top:1rem; }}

/* ---------------------------------------------------------------- header ("noise to signal") */
.hero {{ position:relative; overflow:hidden; color:#fff; margin-bottom:1.1rem; padding: 1.5rem 1.9rem 1.3rem;
  border-radius: 6px 26px 6px 26px; background: linear-gradient(115deg, {INK} 0%, #0F3149 60%, #0B4F61 100%);
  box-shadow: 0 18px 40px -18px rgba(15,30,46,.55); animation: rise .6s cubic-bezier(.2,.7,.2,1) both; }}
.hero::after {{ content:""; position:absolute; inset:0; pointer-events:none;
  background: repeating-linear-gradient(0deg, rgba(255,255,255,.025) 0 1px, transparent 1px 4px); }}
.hero-wave {{ position:absolute; right:0; top:8%; height:72%; width:46%; opacity:.9; pointer-events:none; }}
@media (max-width: 900px) {{ .hero-wave {{ width:100%; opacity:.35; }} }}
.hero-wave .noise {{ stroke: rgba(232,238,244,.38); stroke-width:1.4; fill:none; animation: jitter .35s steps(2) infinite; }}
.hero-wave .signal {{ stroke:{ORANGE}; stroke-width:2.4; fill:none; stroke-linecap:round;
  stroke-dasharray: var(--len, 1200); animation: draw 1.8s cubic-bezier(.6,.05,.3,1) both .25s;
  filter: drop-shadow(0 0 6px rgba(240,138,62,.55)); }}
.hero-wave .scanline {{ animation: scan 5.5s linear infinite; }}
.hero-top {{ position:relative; z-index:1; display:flex; justify-content:space-between; align-items:flex-start;
  gap:1rem; flex-wrap:wrap; }}
.eyebrow {{ font-family:{MONO}; text-transform:uppercase; letter-spacing:.14em; font-size:.68rem; opacity:.72; }}
.eyebrow b {{ color:{ORANGE}; font-weight:700; }}
.hero h1 {{ font-family:{DISPLAY}; font-size:2.25rem; font-weight:700; margin:.2rem 0 .25rem; color:#fff;
  letter-spacing:-.03em; line-height:1.05; }}
.hero p {{ margin:0; opacity:.85; font-size:.92rem; max-width:31rem; text-shadow: 0 1px 8px rgba(15,30,46,.9); }}
.pill {{ display:inline-flex; align-items:center; gap:.5rem; padding:.42rem .85rem; border-radius:4px 12px 4px 12px;
  font-family:{MONO}; font-size:.74rem; font-weight:500; white-space:nowrap; backdrop-filter: blur(6px); }}
.pill-red {{ background:rgba(214,69,69,.16); color:#FFD6D6; border:1px solid rgba(255,140,140,.45); --ring: rgba(255,122,122,.7); }}
.pill-green {{ background:rgba(31,157,107,.18); color:#CFF5E4; border:1px solid rgba(120,220,180,.45); --ring: rgba(110,231,183,.7); }}
.dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; animation: ping 1.8s ease-out infinite; }}

/* the five steps as a signal path with a pulse travelling along it */
.track {{ position:relative; z-index:1; display:flex; justify-content:space-between; margin:1.35rem .2rem 0; padding-top:.1rem; }}
.track::before {{ content:""; position:absolute; left:6px; right:6px; top:6px; height:1px;
  background: linear-gradient(90deg, rgba(255,255,255,.15), rgba(255,255,255,.45), rgba(255,255,255,.15));
  transform-origin:left; animation: sweep 1.1s cubic-bezier(.6,.05,.3,1) both .2s; }}
.track .pulse {{ position:absolute; top:3px; left:0; width:7px; height:7px; margin-left:3px; border-radius:50%;
  background:{ORANGE}; box-shadow: 0 0 10px 2px rgba(240,138,62,.8); animation: travel 4.5s cubic-bezier(.45,0,.55,1) infinite 1.2s; }}
.node {{ position:relative; display:flex; flex-direction:column; align-items:flex-start; gap:.35rem;
  animation: rise .5s cubic-bezier(.2,.7,.2,1) both; animation-delay: calc(.25s + var(--i) * 110ms); }}
.node:last-child {{ align-items:flex-end; }}
.node::before {{ content:""; width:13px; height:13px; border-radius:50%; background:{INK};
  border:1.5px solid rgba(255,255,255,.55); box-sizing:border-box; }}
.node span {{ font-family:{MONO}; font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; opacity:.85; }}
.node span b {{ color:{ORANGE}; margin-right:.3rem; font-weight:700; }}
.node em {{ font-style:normal; font-size:.7rem; opacity:.62; white-space:nowrap; line-height:1.3; }}
@media (max-width: 900px) {{ .node em {{ display:none; }}
  .track {{ display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:.3rem; }}
  .node span {{ font-size:.58rem; letter-spacing:.04em; }} .node span b {{ display:block; margin:0 0 .1rem; }} }}
.node:last-child em {{ text-align:right; }}

/* ---------------------------------------------------------------- "start here" briefing */
.brief {{ display:grid; grid-template-columns: 1.15fr 1fr 1.25fr; gap:.85rem; margin:0 0 1rem; }}
@media (max-width: 1000px) {{ .brief {{ grid-template-columns: 1fr; }} }}
.brief > div {{ background:#fff; border:1px solid {LINE}; border-radius:4px 16px 4px 16px; padding:.85rem 1.05rem;
  animation: rise .55s cubic-bezier(.2,.7,.2,1) both; animation-delay: calc(var(--i) * 80ms); }}
.brief-k {{ font-family:{MONO}; font-size:.64rem; letter-spacing:.12em; text-transform:uppercase; color:{TEAL}; margin-bottom:.35rem; }}
.brief p {{ margin:0; font-size:.86rem; color:#334155; line-height:1.5; }}
.verdict {{ border-left:4px solid var(--c) !important; }}
.verdict-h {{ display:flex; align-items:center; gap:.5rem; font-family:{DISPLAY}; font-weight:700; font-size:1.12rem; color:{INK}; margin-bottom:.2rem; }}
.verdict-i {{ width:22px; height:22px; border-radius:50%; background:var(--c); color:#fff; display:inline-flex;
  align-items:center; justify-content:center; font-size:.8rem; font-weight:800; flex:none; }}
.howto {{ margin:0; padding:0; list-style:none; counter-reset: how; display:grid; gap:.22rem; }}
.howto li {{ counter-increment: how; font-size:.83rem; color:#334155; display:flex; gap:.5rem; align-items:baseline; }}
.howto li::before {{ content: counter(how); font-family:{MONO}; font-size:.66rem; font-weight:700; color:#fff; background:{INK};
  border-radius:3px; padding:.05rem .38rem; flex:none; }}
.howto b {{ color:{INK}; }}
.headline {{ font-family:{DISPLAY}; font-size:1.06rem; color:{INK}; margin:.2rem 0 .7rem; letter-spacing:-.01em; line-height:1.45;
  animation: rise .55s cubic-bezier(.2,.7,.2,1) both .1s; }}
.headline b {{ color:{TEAL}; }}
.headline small {{ font-family:{BODY}; font-size:.78rem; color:{MUTED}; margin-left:.35rem; }}

/* ---------------------------------------------------------------- KPI readouts */
.kpis {{ display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap:.85rem; margin-bottom:1.2rem; }}
@media (max-width: 1000px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
.kpi {{ position:relative; overflow:hidden; background:#fff; border:1px solid {LINE}; border-radius:4px 16px 4px 16px;
  padding:1rem 1.05rem .7rem; box-shadow:0 1px 2px rgba(15,30,46,.04); transition: transform .2s, box-shadow .2s; }}
.kpi:hover {{ transform: translateY(-2px); box-shadow: 0 12px 24px -16px rgba(15,30,46,.35); }}
.kpi::before {{ content:""; position:absolute; left:0; top:0; height:3px; width:100%; background: var(--accent);
  transform-origin:left; animation: sweep .9s cubic-bezier(.6,.05,.3,1) both; animation-delay: calc(.2s + var(--i) * 90ms); }}
.kpi-label {{ font-family:{MONO}; color:{MUTED}; font-size:.68rem; font-weight:500; text-transform:uppercase; letter-spacing:.1em; }}
.kpi-cap {{ font-size:.74rem; color:{MUTED}; line-height:1.35; margin:.15rem 0 .1rem; min-height:2em; }}
.kpi-value {{ font-family:{DISPLAY}; font-size:1.75rem; font-weight:700; color:{INK}; letter-spacing:-.03em;
  margin:.25rem 0 .2rem; font-variant-numeric: tabular-nums; overflow:hidden; }}
.kpi-value span {{ display:inline-block; animation: digits .7s cubic-bezier(.2,.7,.2,1) both; animation-delay: calc(.3s + var(--i) * 90ms); }}
.delta {{ font-family:{MONO}; font-size:.72rem; font-weight:700; padding:.12rem .45rem; border-radius:3px; }}
.delta-good {{ color:{GREEN}; background:#E6F6EF; }}
.delta-bad {{ color:{RED}; background:#FCEAEA; }}
.delta-flat {{ color:{MUTED}; background:#EEF2F6; }}
.kpi svg {{ display:block; margin-top:.45rem; }}
.kpi svg polyline {{ stroke-dasharray: 600; animation: draw 1.4s cubic-bezier(.6,.05,.3,1) both; --len: 600;
  animation-delay: calc(.45s + var(--i) * 90ms); }}
.kpi svg polygon {{ animation: fade 1s ease both; animation-delay: calc(.9s + var(--i) * 90ms); }}

/* ---------------------------------------------------------------- tabs: a channel selector */
.stTabs [role="tablist"] {{ gap:.2rem; background:#fff; padding:.3rem; border-radius:4px 14px 4px 14px;
  border:1px solid {LINE}; box-shadow:0 1px 2px rgba(15,30,46,.04); overflow-x:auto; }}
.stTabs [data-testid="stTab"] {{ position:relative; padding:.55rem .72rem !important; border-radius:3px 10px 3px 10px;
  margin:0 !important; cursor:pointer; transition: background .2s, transform .2s; }}
.stTabs [data-testid="stTab"] p {{ font-weight:600; font-size:.83rem; color:{MUTED} !important; margin:0; white-space:nowrap; }}
.stTabs [data-testid="stTab"]:hover {{ background:#F1F5F9; }}
.stTabs [data-testid="stTab"][aria-selected="true"] {{ background:{INK} !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"] p {{ color:#fff !important; }}
.stTabs [data-testid="stTab"][aria-selected="true"]::after {{ content:""; position:absolute; left:14px; right:14px; bottom:5px;
  height:2px; border-radius:2px; background:{ORANGE}; transform-origin:left; animation: sweep .35s ease both; }}
.stTabs .react-aria-SelectionIndicator, .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none !important; }}

/* ---------------------------------------------------------------- section headers, numbered per tab */
[data-baseweb="tab-panel"], [role="tabpanel"] {{ counter-reset: sec; }}
.sec {{ margin:1.4rem 0 .65rem; counter-increment: sec; animation: rise .5s cubic-bezier(.2,.7,.2,1) both; }}
.sec h3 {{ font-family:{DISPLAY}; font-size:1.22rem; font-weight:700; color:{INK}; margin:0; letter-spacing:-.02em;
  display:flex; align-items:baseline; gap:.6rem; }}
.sec h3::before {{ content: counter(sec, decimal-leading-zero) " /"; font-family:{MONO}; font-size:.72rem; font-weight:500;
  color:{TEAL}; letter-spacing:.06em; }}
.sec p {{ color:{MUTED}; margin:.3rem 0 0; font-size:.88rem; max-width:62rem; }}

/* ---------------------------------------------------------------- cards */
.card {{ background:#fff; border:1px solid {LINE}; border-radius:4px 16px 4px 16px; padding:1rem 1.15rem;
  box-shadow:0 1px 2px rgba(15,30,46,.04); animation: rise .6s cubic-bezier(.2,.7,.2,1) both; }}
.issue {{ position:relative; background:#fff; border:1px solid {LINE}; border-radius:4px 14px 4px 14px;
  padding:.9rem 1.1rem .9rem 1.25rem; margin-bottom:.65rem; animation: rise .55s cubic-bezier(.2,.7,.2,1) both;
  transition: transform .2s, box-shadow .2s; }}
.issue:hover {{ transform: translateX(3px); box-shadow: 0 10px 22px -16px rgba(15,30,46,.4); }}
.issue::before {{ content:""; position:absolute; left:-1px; top:12px; bottom:12px; width:4px; border-radius:0 3px 3px 0;
  background:var(--c); transform-origin:top; animation: bars .6s cubic-bezier(.2,.7,.2,1) both .1s; }}
.issue-top {{ display:flex; justify-content:space-between; gap:1rem; align-items:center; flex-wrap:wrap; }}
.issue-title {{ font-family:{DISPLAY}; font-weight:600; color:{INK}; font-size:1rem; letter-spacing:-.01em; }}
.issue-detail {{ color:#334155; font-size:.88rem; margin-top:.4rem; line-height:1.5; }}
.chips {{ display:flex; gap:.35rem; flex-wrap:wrap; margin-top:.45rem; }}
.chip {{ font-family:{MONO}; font-size:.68rem; font-weight:500; padding:.18rem .55rem; border-radius:3px; background:#EEF2F6; color:#475569; }}
.chip-mono {{ font-family:{MONO}; font-weight:500; }}
.badge {{ display:inline-flex; align-items:center; gap:.4rem; font-family:{MONO}; font-size:.66rem; font-weight:700;
  letter-spacing:.08em; text-transform:uppercase; padding:.22rem .55rem; border-radius:3px; color:#fff; background:var(--c); }}
/* signal-strength glyph: severity by shape (3 bars = fix now, 1 bar = watch), not only by color */
.sig {{ display:inline-flex; align-items:flex-end; gap:2px; height:11px; }}
.sig i {{ width:3px; border-radius:1px; background:rgba(255,255,255,.35); transform-origin:bottom; animation: bars .5s ease both; }}
.sig i.on {{ background:#fff; }}
.sig i:nth-child(1) {{ height:4px; }} .sig i:nth-child(2) {{ height:7px; animation-delay:.08s; }}
.sig i:nth-child(3) {{ height:11px; animation-delay:.16s; }}
.issue-action {{ margin-top:.6rem; padding-top:.55rem; border-top:1px dashed #E2E8F0; color:#0B4F61; font-size:.86rem; }}
.impact {{ font-family:{MONO}; font-weight:700; color:{INK}; font-size:.82rem; }}
.stat-row {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:.85rem; margin:.4rem 0 1rem; }}
@media (max-width: 1000px) {{ .stat-row {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} }}
.stat {{ position:relative; background:#fff; border:1px solid {LINE}; border-radius:4px 14px 4px 14px; padding:.8rem 1rem; }}
.stat::after {{ content:""; position:absolute; left:1rem; bottom:0; width:28px; height:2px; background:{TEAL}; }}
.stat-v {{ font-family:{DISPLAY}; font-size:1.45rem; font-weight:700; color:{INK}; font-variant-numeric: tabular-nums;
  letter-spacing:-.02em; }}
.stat-l {{ font-family:{MONO}; font-size:.66rem; color:{MUTED}; font-weight:500; text-transform:uppercase; letter-spacing:.1em; }}
.callout {{ position:relative; background:{TEAL_LIGHT}; border:1px solid #BFE1EA; border-radius:4px 14px 4px 14px;
  padding:.9rem 1.1rem .9rem 1.3rem; color:#0B4F61; font-size:.9rem; animation: rise .55s cubic-bezier(.2,.7,.2,1) both .1s; }}
.callout::before {{ content:""; position:absolute; left:.55rem; top:.95rem; bottom:.95rem; width:2px; border-radius:2px; background:{TEAL}; }}
.callout b {{ color:{INK}; }}
.summary {{ background:#fff; border:1px solid {LINE}; border-radius:4px 16px 4px 16px; padding:1.2rem 1.4rem; line-height:1.65;
  animation: rise .6s cubic-bezier(.2,.7,.2,1) both; }}
.summary li {{ animation: rise .5s cubic-bezier(.2,.7,.2,1) both; }}
.summary li:nth-child(2) {{ animation-delay:.08s; }} .summary li:nth-child(3) {{ animation-delay:.16s; }}
.summary li:nth-child(4) {{ animation-delay:.24s; }} .summary li:nth-child(5) {{ animation-delay:.32s; }}

[data-testid="stDataFrame"] {{ border:1px solid {LINE}; border-radius:4px 14px 4px 14px; overflow:hidden; background:#fff; }}
[data-testid="stPlotlyChart"] {{ background:#fff; border:1px solid {LINE}; border-radius:4px 16px 4px 16px; padding:.5rem .6rem; }}
.stDownloadButton button, .stButton button {{ border-radius:3px 10px 3px 10px; font-weight:600; border:1px solid {LINE};
  transition: transform .15s, box-shadow .15s; }}
.stDownloadButton button:hover, .stButton button:hover {{ transform: translateY(-1px); box-shadow: 0 6px 14px -8px rgba(15,30,46,.35); }}

/* ---------------------------------------------------------------- accessibility: honour reduced motion */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition: none !important; }}
  .track .pulse {{ display:none; }}
}}
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
    """ClearSignal mark (three rising signal bars) and tagline at the top of the sidebar."""
    st.sidebar.markdown(
        """<div class="brand"><div class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></div>
      <div><div class="brand-name">ClearSignal</div><div class="brand-sub">Ad results you can trust</div></div></div>""",
        unsafe_allow_html=True,
    )


def _hero_wave(w: int = 760, h: int = 200) -> str:
    """Decorative SVG: a noisy grey trace on the left that resolves into a clean signal on the right."""
    rng = np.random.default_rng(11)  # fixed seed: the same picture on every load
    n = 120
    xs = np.linspace(0, w, n)
    mid = h * 0.58
    clean = [mid - 34 * math.sin(x / w * 5.2 * math.pi) * (0.35 + 0.65 * x / w) for x in xs]
    noise_amp = np.clip(1 - xs / (w * 0.75), 0, 1) * 30
    noisy = [c + float(a * rng.normal()) for c, a in zip(clean, noise_amp, strict=True)]
    to_pts = lambda ys: " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys, strict=True))  # noqa: E731
    signal_len = int(sum(math.hypot(xs[i + 1] - xs[i], clean[i + 1] - clean[i]) for i in range(n - 1))) + 10
    return (
        f'<svg class="hero-wave" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
        '<defs><linearGradient id="hw-fade" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".35" stop-color="#fff" stop-opacity="1"/></linearGradient>'
        '<mask id="hw-mask"><rect width="100%" height="100%" fill="url(#hw-fade)"/></mask>'
        '<linearGradient id="hw-scan" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity=".10"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        "</linearGradient></defs>"
        f'<g mask="url(#hw-mask)"><polyline class="noise" points="{to_pts(noisy)}"/>'
        f'<polyline class="signal" style="--len:{signal_len}" points="{to_pts(clean)}"/>'
        f'<rect class="scanline" x="0" y="0" width="{w * 0.12:.0f}" height="{h}" fill="url(#hw-scan)"/></g></svg>'
    )


def hero(client: str, subtitle: str, n_high: int, as_of: str) -> None:
    """Page header: client name, subtitle, data date, High-issue pill and the five-step signal path."""
    pill = (
        (
            f'<span class="pill pill-red"><span class="dot" style="background:#FF7A7A"></span>{n_high} data '
            f"issue{'s' if n_high != 1 else ''} to fix</span>"
        )
        if n_high
        else '<span class="pill pill-green"><span class="dot" style="background:#6EE7B7"></span>Numbers checked and ready</span>'
    )
    steps = [
        ("Collect", "3 data sources"),
        ("Check", "8 data checks · tab 1"),
        ("Compare", "platforms vs GA4 · tab 2"),
        ("Report", "results · tab 3"),
        ("Advise", "budget, email · tabs 4–5"),
    ]
    nodes = "".join(
        f'<div class="node" style="--i:{i}"><span><b>{i + 1:02d}</b>{s}</span><em>{esc(cap)}</em></div>'
        for i, (s, cap) in enumerate(steps)
    )
    st.markdown(
        f"""<div class="hero">{_hero_wave()}<div class="hero-top"><div>
      <div class="eyebrow"><b>●</b> ClearSignal · numbers up to {esc(as_of)}</div>
      <h1>{esc(client)}</h1><p>{esc(subtitle)}</p></div>{pill}</div>
      <div class="track"><span class="pulse" aria-hidden="true"></span>{nodes}</div></div>""",
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
        f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{color}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{gid})"/><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"'
        f' stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>'
    )


def kpi_cards(items: list[tuple]) -> None:
    """Row of KPI readouts. items: (label, value_str, delta or None, good_when_up, spark_values, color[, caption]).

    The change is shown with an arrow and a sign, not only a color.
    """
    cards = []
    for i, item in enumerate(items):
        label, value, delta, up_good, spark, color = item[:6]
        caption = item[6] if len(item) > 6 else ""
        if delta is None or np.isnan(delta):
            d = '<span class="delta delta-flat">n/a</span>'
        else:
            cls = "delta-flat" if abs(delta) < 0.005 else ("delta-good" if (delta > 0) == up_good else "delta-bad")
            arrow = "▲" if delta > 0 else "▼"
            d = f'<span class="delta {cls}">{arrow} {abs(delta):.1%}</span>'
        cards.append(
            f'<div class="kpi rise" style="--i:{i};--accent:{color}"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value"><span>{esc(value)}</span></div>'
            f"{f'<div class=kpi-cap>{esc(caption)}</div>' if caption else ''}{d}{sparkline(spark, color)}</div>"
        )
    st.markdown(f'<div class="kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


def briefing(
    about: str, verdict_title: str, verdict_text: str, ok: bool | None, reading_order: list[tuple[str, str]]
) -> None:
    """'Start here' panel: what you're looking at, a plain verdict, and the order to read the tabs.

    ok: True = ready, None = ready with notes, False = not ready. The verdict carries an icon and words,
    not only a color.
    """
    color, icon = {True: (GREEN, "✓"), None: (AMBER, "!"), False: (RED, "✕")}[ok]
    steps = "".join(f"<li><span><b>{esc(t)}</b>: {esc(d)}</span></li>" for t, d in reading_order)
    st.markdown(
        f"""<div class="brief">
      <div style="--i:0"><div class="brief-k">What you're looking at</div><p>{esc(about)}</p></div>
      <div class="verdict" style="--i:1;--c:{color}"><div class="brief-k">Can this report go to the client today?</div>
        <div class="verdict-h"><span class="verdict-i" aria-hidden="true">{icon}</span>{esc(verdict_title)}</div>
        <p>{esc(verdict_text)}</p></div>
      <div style="--i:2"><div class="brief-k">How to read it</div><ol class="howto">{steps}</ol></div></div>""",
        unsafe_allow_html=True,
    )


def headline(sentence: str, emphasis: list[str], note: str = "") -> None:
    """The period's results in one plain sentence; each value in `emphasis` is highlighted."""
    text = esc(sentence)
    for value in emphasis:
        e = esc(value)
        text = text.replace(e, f"<b>{e}</b>", 1)
    st.markdown(
        f'<div class="headline">{text}{f"<small>{esc(note)}</small>" if note else ""}</div>', unsafe_allow_html=True
    )


def section(title: str, text: str = "") -> None:
    """Section heading (numbered per tab by CSS) with an optional one-line explanation."""
    st.markdown(
        f'<div class="sec"><h3>{esc(title)}</h3>{f"<p>{esc(text)}</p>" if text else ""}</div>', unsafe_allow_html=True
    )


def _signal_bars(strength: int) -> str:
    """Three-bar signal glyph with `strength` bars lit (decorative; the badge text carries the meaning)."""
    return (
        '<span class="sig" aria-hidden="true">'
        + "".join(f'<i class="{"on" if n < strength else ""}"></i>' for n in range(3))
        + "</span>"
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
    """One data-health issue: severity badge (text + signal glyph), title, chips, detail and next step."""
    color = RED if severity == "High" else AMBER
    label = "Fix now" if severity == "High" else "Watch"
    impact = (
        f'<span class="impact">${usd:,.0f} of ad spend affected</span>' if usd is not None and not np.isnan(usd) else ""
    )
    act = f'<div class="issue-action"><b>Next step:</b> {esc(action)}</div>' if action else ""
    st.markdown(
        f"""<div class="issue" style="--c:{color}"><div class="issue-top">
      <div style="display:flex;gap:.6rem;align-items:center"><span class="badge" style="--c:{color}">{_signal_bars(3 if severity == "High" else 1)}{label}</span>
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
            f'<div class="stat rise" style="--i:{i}"><div class="stat-l">{esc(l)}</div><div class="stat-v">{esc(v)}</div></div>'
            for i, (l, v) in enumerate(items)
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def callout(md_html: str) -> None:
    """Highlighted note. `md_html` is trusted markup written in the code, never data."""
    st.markdown(f'<div class="callout">{md_html}</div>', unsafe_allow_html=True)
