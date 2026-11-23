"""Smoke tests for the Streamlit app with streamlit.testing (no browser), against the temp warehouse."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
CLIENTS = ["DTC Skincare", "B2B SaaS", "Home Services"]
PERIODS = ["Last 7 days", "Last 30 days", "Last 90 days"]
BASES = ["Google Analytics (recommended)", "Each ad platform's own numbers"]
TABS = [
    "1 · Data health",
    "2 · Do the numbers match?",
    "3 · Results",
    "4 · Where to spend next",
    "5 · Weekly client email",
    "Value to your agency",
    "How it works",
]
BAD_TEXT = re.compile(r"\b(nan|inf)\b", re.IGNORECASE)


@pytest.fixture(autouse=True)
def fresh_streamlit_caches():
    """Each test starts with empty Streamlit caches, so one test's warehouse never leaks into another."""
    import streamlit as st

    st.cache_data.clear()
    st.cache_resource.clear()
    yield


def page_text(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def test_every_tab_for_every_filter_combination(use_demo_warehouse):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert [t.label for t in at.tabs] == TABS
    for client, period, basis in itertools.product(CLIENTS, PERIODS, BASES):
        at.sidebar.selectbox[0].select(client)
        at.sidebar.radio[0].set_value(period)
        at.sidebar.radio[1].set_value(basis)
        at.run()
        combo = f"{client} / {period} / {basis}"
        assert not at.exception, f"{combo}: {[e.message for e in at.exception]}"
        assert not at.error, combo
        for tab in at.tabs:
            assert len(tab.children) > 0, f"{combo}: tab {tab.label!r} is empty"
        text = page_text(at)
        assert client in text, combo
        assert not BAD_TEXT.search(text), f"{combo}: 'nan' or 'inf' on screen"


def test_lead_gen_client_never_says_sales(use_demo_warehouse):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.selectbox[0].select("B2B SaaS")
    at.run()
    summary = [m.value for m in at.markdown if 'class="summary"' in m.value][0]
    assert "leads" in summary and "sales" not in summary


def test_start_here_panel_gives_a_plain_verdict(use_demo_warehouse):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.selectbox[0].select("DTC Skincare")
    at.run()
    text = page_text(at)
    assert "What you&#x27;re looking at" in text or "What you're looking at" in text
    assert "Can this report go to the client today?" in text and "Not yet" in text
    assert "5 problems would make the numbers wrong" in text
    assert "In the last 30 days," in text and "back for every $1 spent" in text
    assert "what came back for every $1 of ads" in text


def test_header_counts_high_issues(use_demo_warehouse):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.sidebar.selectbox[0].select("DTC Skincare")
    at.run()
    assert "5 data issues to fix" in page_text(at)


def test_missing_data_shows_a_friendly_message(tmp_path, monkeypatch: pytest.MonkeyPatch):
    # Empty project folder: no data, no warehouse. The app must explain, not crash.
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert at.error and "can't load its data" in at.error[0].value
    assert "Input file is missing" in at.error[0].value
