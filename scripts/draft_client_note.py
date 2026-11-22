"""
Draft the weekly client email with Claude from the warehouse facts.

  pip install anthropic
  $env:ANTHROPIC_API_KEY = "sk-ant-..."        # PowerShell  (macOS/Linux: export ANTHROPIC_API_KEY=...)
  python scripts/draft_client_note.py "DTC Skincare"

Without an API key it prints the prompt so you can paste it into Claude yourself.
The analyst always reviews the draft before anything is sent to a client.
"""
import os
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from analytics import fit_response_curves, load, optimize_budget, weekly_summary  # noqa: E402
from prompts import client_note_prompt  # noqa: E402

client = sys.argv[1] if len(sys.argv) > 1 else "DTC Skincare"
db = ROOT / "data" / "warehouse.duckdb"
df = load(db)
with duckdb.connect(str(db), read_only=True) as con:
    qa = con.execute("select * from qa_results").df()
cdf = df[df["client"] == client]
summary = weekly_summary(cdf, client, qa, optimize_budget(fit_response_curves(cdf)))
prompt = client_note_prompt(client, summary, qa[qa["client"] == client])

if not os.environ.get("ANTHROPIC_API_KEY"):
    print(prompt)
    sys.exit(0)

import anthropic  # noqa: E402

msg = anthropic.Anthropic().messages.create(
    model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
    max_tokens=1200,
    messages=[{"role": "user", "content": prompt}],
)
print(msg.content[0].text)
