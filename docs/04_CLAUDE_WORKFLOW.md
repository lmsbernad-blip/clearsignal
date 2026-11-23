# Where Claude fits in the workflow

| Step | What Claude does | Guardrail |
|---|---|---|
| Write SQL faster | Drafts checks and reconciliation queries from a plain-English description | Every query is reviewed, run and tested against known cases before it's added to `sql/` |
| Investigate | Suggests likely causes for a discrepancy (attribution windows, UTMs, time zones, duplicates) | The analyst confirms each cause with a query; nothing is reported on a guess |
| Client update | Turns warehouse facts and QA results into a client-ready email plus internal notes | Prompt says "use only these facts"; the analyst reviews before sending |
| Documentation | Drafts the data dictionary and onboarding notes from the SQL and mapping files | Analyst edits and owns the final version |

## The client-update prompt
The template lives in `app/prompts.py`, so it's versioned and reviewed like code. It gives Claude:
- the week's facts (results, best and weakest campaign types, recommendation) from the warehouse
- the open QA issues for that client
- a fixed structure: headline, what's working, what we're fixing, one recommendation, one question
- rules: plain English, max 180 words, no invented numbers, say when a number is missing
- safety: the instructions come first; the client name, facts and issues sit in delimited `client`, `facts` and `open_issues` blocks with angle brackets escaped, and Claude is told to treat their contents as data, never as instructions

Run it:
```powershell
pip install anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python scripts/draft_client_note.py "B2B SaaS"
```
Without a key, the script prints the prompt so you can paste it into Claude. The app's **Weekly client email** tab shows the same prompt.
