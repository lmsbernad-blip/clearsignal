"""Prompt templates for the Claude steps in the workflow. Kept in code so they are versioned and reviewed like SQL."""
import pandas as pd


def client_note_prompt(client: str, summary_md: str, qa_rows: pd.DataFrame) -> str:
    issues = "\n".join(
        f"- [{'Fix now' if r.severity == 'High' else 'Watch'}] {r.title} ({r.platform}, {r.object}): {r.detail} "
        f"Next step: {r.action}" for r in qa_rows.itertuples()
    ) or "- None"
    return f"""You are a marketing analytics lead at a US advertising agency writing the weekly update for the client "{client}".

FACTS (from the reporting warehouse; do not invent numbers or causes beyond these):
{summary_md}

OPEN DATA ISSUES (from the daily data checks):
{issues}

Write two things:

1. CLIENT EMAIL (max 180 words). Plain US business English, no jargon (say "conversions counted by Google Analytics",
   not "GA4 key events"). Order: headline result with numbers, what is working, what we are fixing and how it
   affects their numbers, one recommendation, one question for them. Mention a data issue only if it changes what
   they should conclude, and say what we are doing about it.

2. INTERNAL NOTES for the account team (bullets): which data issues to fix first and who owns each
   (analyst / media buyer / client web team), and anything the client may ask about.

If a number needed to answer is missing from the facts, say so instead of estimating."""
