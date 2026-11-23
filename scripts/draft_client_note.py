"""
Draft the weekly client email with Claude from the warehouse facts.

  pip install anthropic
  $env:ANTHROPIC_API_KEY = "sk-ant-..."        # PowerShell  (macOS/Linux: export ANTHROPIC_API_KEY=...)
  python scripts/draft_client_note.py "DTC Skincare"

Without an API key it prints the prompt so you can paste it into Claude yourself.
The analyst always reviews the draft before anything is sent to a client.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import config  # noqa: E402
import warehouse  # noqa: E402
from analytics import fit_response_curves, load, optimize_budget, weekly_summary  # noqa: E402
from prompts import client_note_prompt  # noqa: E402

log = logging.getLogger("clearsignal.draft")


def load_dotenv(path: Path = config.ROOT / ".env") -> None:
    """Read KEY=VALUE lines from a local .env file (git-ignored) without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#") and key not in os.environ and value.strip():
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def build_prompt(client: str) -> str:
    """The Claude prompt for one client, from the current warehouse. Raises ValueError for an unknown client."""
    df = load()
    qa = warehouse.read_table("qa_results")
    clients = sorted(df["client"].unique())
    if client not in clients:
        raise ValueError(f"Unknown client {client!r}. Choose one of: {', '.join(clients)}")
    client_df = df[df["client"] == client]
    summary = weekly_summary(client_df, client, qa, optimize_budget(fit_response_curves(client_df)))
    return client_note_prompt(client, summary, qa[qa["client"] == client])


def main(argv: list[str] | None = None) -> int:
    """Print the Claude draft (with an API key) or the prompt (without one). Returns an exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    args = sys.argv[1:] if argv is None else argv
    client = args[0] if args else "DTC Skincare"
    if warehouse.missing_tables():
        log.error("The warehouse isn't built yet. Run: python scripts/build_warehouse.py")
        return 1
    try:
        prompt = build_prompt(client)
    except (ValueError, warehouse.WarehouseError) as err:
        log.error("%s", err)
        return 1

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.info("ANTHROPIC_API_KEY is not set: printing the prompt to paste into Claude.")
        print(prompt)
        return 0

    try:
        import anthropic
    except ImportError:
        log.error("The anthropic package isn't installed. Run: pip install anthropic")
        return 1
    model = os.environ.get("CLAUDE_MODEL", config.DEFAULT_CLAUDE_MODEL)
    log.info("Drafting the %s update with %s", client, model)  # never log the key or the prompt contents
    try:
        msg = anthropic.Anthropic().messages.create(
            model=model, max_tokens=1200, messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.APIError as err:
        log.error("Claude API call failed: %s", type(err).__name__)
        return 1
    print("".join(block.text for block in msg.content if block.type == "text"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
