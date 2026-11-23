"""Build the DuckDB warehouse from data/raw and data/seeds by running sql/*.sql in order.

    python scripts/build_warehouse.py                 # builds data/warehouse.duckdb
    python scripts/build_warehouse.py --root DIR --db FILE

Exits with code 1 and a one-line explanation if any input or step fails; the previous
warehouse is left untouched in that case.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import config  # noqa: E402
from warehouse import WarehouseError, build  # noqa: E402

log = logging.getLogger("clearsignal.build")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, build the warehouse and return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=config.ROOT, help="folder that contains data/raw and data/seeds")
    parser.add_argument("--db", type=Path, default=config.DB_PATH, help="warehouse file to write")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        build(db_path=args.db, root=args.root)
    except WarehouseError as err:
        log.error("%s", err)
        return 1
    log.info("warehouse ready: %s", args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
