"""Run the SQL files in order into a local DuckDB warehouse:  python scripts/build_warehouse.py"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "warehouse.duckdb"

con = duckdb.connect(str(DB))
for sql_file in sorted((ROOT / "sql").glob("*.sql")):
    con.execute(f"set file_search_path = '{ROOT.as_posix()}'")
    con.execute(sql_file.read_text())
    print(f"ran {sql_file.name}")

for t in ["fct_ads_daily", "mart_campaign_daily", "qa_results", "reconciliation_summary"]:
    print(f"  {t}: {con.execute(f'select count(*) from {t}').fetchone()[0]:,} rows")
con.close()
