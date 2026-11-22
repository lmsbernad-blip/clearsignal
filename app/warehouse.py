"""Build and read the DuckDB warehouse.

The build is atomic: it writes to a temporary file and only replaces the real warehouse when every
SQL step succeeded and every required table exists. A failed build therefore never leaves a
half-built warehouse behind for the app to trip over.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import duckdb
import pandas as pd

import config

log = logging.getLogger("clearsignal.warehouse")


class WarehouseError(RuntimeError):
    """A build or read problem, with a message written for the person running ClearSignal."""


def _sql_literal(value: float | int | str) -> str:
    """Render a config value as a SQL literal (strings quoted and escaped)."""
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return repr(value)


def _explain(err: Exception) -> str:
    """Turn a DuckDB error into one plain sentence that names the file and the fix."""
    text = str(err)
    for path in (*config.RAW_FILES.values(), *config.SEED_FILES.values()):
        if path in text and ("No files found" in text or "No such file" in text):
            return f"Input file is missing: {path}. Run `python scripts/generate_data.py` or add the export."
    if "column0" in text or "empty" in text.lower():
        return "An input file is empty or has no header row. " + _first_line(text)
    if isinstance(err, duckdb.BinderException):
        return "An input file is missing a required column (was a column renamed?). " + _first_line(text)
    if isinstance(err, duckdb.ConversionException | duckdb.InvalidInputException):
        return "An input file has a value that can't be read (wrong date or number format). " + _first_line(text)
    return f"The warehouse build failed: {_first_line(text)}"


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0][:300] if text.strip() else ""


def missing_tables(db_path: Path = config.DB_PATH) -> list[str]:
    """Required tables that are not in the warehouse (all of them if the file doesn't exist)."""
    if not Path(db_path).exists():
        return list(config.REQUIRED_TABLES)
    try:
        with duckdb.connect(str(db_path), read_only=True) as con:
            present = {r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()}
    except duckdb.Error:
        return list(config.REQUIRED_TABLES)
    return [t for t in config.REQUIRED_TABLES if t not in present]


def build(db_path: Path = config.DB_PATH, root: Path = config.ROOT, sql_dir: Path = config.SQL_DIR) -> dict[str, int]:
    """Run sql/*.sql in order into `db_path`, reading inputs relative to `root`.

    Returns row counts per required table. Raises WarehouseError with a readable message on failure;
    the existing warehouse (if any) is left untouched.
    """
    db_path, root = Path(db_path), Path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(f"{db_path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    sql_files = sorted(Path(sql_dir).glob("*.sql"))
    if not sql_files:
        raise WarehouseError(f"No SQL files found in {sql_dir}.")
    try:
        con = duckdb.connect(str(tmp))
        try:
            con.execute(f"set file_search_path = {_sql_literal(root.as_posix())}")
            for name, value in config.sql_variables().items():
                con.execute(f"set variable {name} = {_sql_literal(value)}")
            for sql_file in sql_files:
                try:
                    con.execute(sql_file.read_text(encoding="utf-8"))
                except duckdb.Error as err:
                    raise WarehouseError(f"{sql_file.name}: {_explain(err)}") from err
                log.info("ran %s", sql_file.name)
            counts = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in config.REQUIRED_TABLES}  # noqa: S608 - names from config
        finally:
            con.close()
        try:
            os.replace(tmp, db_path)
        except PermissionError as err:
            raise WarehouseError(
                f"Couldn't replace {db_path.name}: it is open in another program (stop the Streamlit app and retry)."
            ) from err
    finally:
        for leftover in (tmp, tmp.with_name(tmp.name + ".wal")):
            leftover.unlink(missing_ok=True)
    for table, n in counts.items():
        log.info("  %s: %s rows", table, f"{n:,}")
    return counts


def read_table(name: str, db_path: Path = config.DB_PATH) -> pd.DataFrame:
    """Read one allow-listed table, read-only. Unknown names are refused, never put into SQL."""
    if name not in config.APP_TABLES:
        raise ValueError(f"Table {name!r} is not one the app may read.")
    try:
        with duckdb.connect(str(db_path), read_only=True) as con:
            return con.execute(f"select * from {name}").df()  # noqa: S608 - name checked against allowlist
    except duckdb.Error as err:
        raise WarehouseError(f"Couldn't read {name} from the warehouse: {_first_line(str(err))}") from err
