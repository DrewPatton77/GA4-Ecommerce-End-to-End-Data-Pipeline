"""Write the finished tables to parquet files, one per table."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


def write_parquet(tables: dict[str, pl.DataFrame], directory: Path | str) -> list[Path]:
    """Write each table to <directory>/<table name>.parquet and return the paths."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    paths = []
    for name, table in tables.items():
        path = directory / f"{name}.parquet"
        table.write_parquet(path)
        logger.info("Wrote %-26s %9d rows -> %s", name, table.height, path)
        paths.append(path)
    return paths
