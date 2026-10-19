'''
Command line entry point.

    ga4-pipeline 2020-11-01 2021-01-31                      # run, write parquet to data/output
    uv run --env-file .env ga4-pipeline 2020-11-01 2021-01-31 --to postgres
    ga4-pipeline 2020-11-01 2021-01-31 --estimate-cost      # dry-run the BigQuery queries, then stop
    ga4-pipeline 2020-11-01 2021-01-31 --refresh            # ignore the local cache and re-query
'''

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path
from typing import Sequence

DEFAULT_OUTPUT_DIR = Path("data/output")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='ga4-pipeline', description='Build the GA4 ecommerce tables.')
    parser.add_argument('start_date', type=date.fromisoformat, help='first day to include (YYYY-MM-DD)')
    parser.add_argument('end_date', type=date.fromisoformat, help='last day to include (YYYY-MM-DD)')
    parser.add_argument(
        '--to', choices=('parquet', 'postgres', 'both'), default='parquet', help='where to write the tables'
    )
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR, help='where to write parquet files')
    parser.add_argument('--pg-schema', default='ga4', help='Postgres schema to load into (connection from POSTGRES_* env)')
    parser.add_argument('--no-cache', action='store_true', help='do not read or write the local BigQuery cache')
    parser.add_argument('--refresh', action='store_true', help='re-run the queries even if cached')
    parser.add_argument('--estimate-cost', action='store_true', help='show the BigQuery cost estimate and stop')
    parser.add_argument('-v', '--verbose', action='store_true', help='debug logging')

    args = parser.parse_args(argv)
    if args.end_date < args.start_date:
        parser.error('end_date must not be before start_date')
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    # Imported here so `--help` and argument errors are instant and need no heavy dependencies.
    from ga4_ecommerce_analytics_engine.pipeline import Pipeline
    from ga4_ecommerce_analytics_engine.sources.bigquery_source import BigQuerySource

    source = BigQuerySource(use_cache=not args.no_cache, refresh=args.refresh)

    if args.estimate_cost:
        source.estimate_cost(args.start_date, args.end_date)
        return 0

    raw = source.fetch_all(args.start_date, args.end_date)
    tables = Pipeline().run(raw)

    if args.to in ('parquet', 'both'):
        from ga4_ecommerce_analytics_engine.writers.parquet import write_parquet

        write_parquet(tables, args.output_dir)
    if args.to in ('postgres', 'both'):
        from ga4_ecommerce_analytics_engine.writers.postgres import PostgresWriter

        PostgresWriter(schema_name=args.pg_schema).write(tables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
