# ga4_ecommerce_analytics_engine

Turns the public GA4 sample ecommerce dataset (BigQuery) into a star schema in Postgres for Power BI.

    BigQuery  ->  polars pipeline  ->  parquet and/or Postgres (Docker)  ->  Power BI

## Quick start

    uv sync
    cp .env.example .env            # set POSTGRES_PASSWORD
    make db-up                      # Postgres in Docker
    make cost                       # dry-run the queries first (nothing is billed)
    make run-pg                     # build everything and load Postgres

`make` lists every task. Dates default to the whole sample dataset (2020-11-01 to 2021-01-31); override with
`make run START=2020-12-01 END=2020-12-31`. Raw BigQuery results are cached as parquet in `data/cache`, so
re-runs are free. Use `make refresh` to bypass the cache.

Run it without make: `uv run ga4-pipeline 2020-11-01 2021-01-31 --to both`.

## How it works

`Pipeline().run(raw)` (in `pipeline.py`) takes the three raw extracts and returns 15 polars tables. It does no
file or database access; the writers do that. Each stage is a module you can use and test on its own:

| Stage | Module | What it does |
|---|---|---|
| source | `sources/` | Fetch events, items and user dimensions from BigQuery (with parquet cache and cost estimate) |
| clean | `cleaning/transactions.py` | Deduplicate purchases, build composite session ids and transaction ids |
| enrich | `enrichment/` | Resolve each session's UTM values, then classify the marketing channel from ordered rules |
| aggregate | `aggregation/` | Events -> sessions -> user journeys (paths, durations, conversion value, log bins) |
| dimensions | `dimensions/` | Date, geo, device, traffic source, item, transaction; integer keys and key mappings |
| facts | `facts/` | Event, item funnel, session, user, journey tables with dimension keys attached |
| attribution | `analytics/attribution.py` | Credit for conversions under eight models (first, last, last non-direct, linear, position, time-decay, Shapley, Markov) |
| basket | `analytics/basket.py` | Items bought together: support, confidence, lift, Louvain communities |
| write | `writers/` | Parquet files, or Postgres in one transaction with primary and foreign keys |

### Column names live in one place

`schema.py` holds `DataSchema`, a frozen dataclass of every column name and event-type value. Every stage
subclasses it, so renaming a column is one change, and tests can override names per instance:

    SessionFacts(date_id="day_key")
    Pipeline(schema=DataSchema(country="nation"))

### Channel rules are data

`enrichment/channel_rules.py` is an ordered list of rules. The first match wins. A rule's clauses are OR-ed,
and the criteria inside one clause are AND-ed. Edit the list to change a channel; no code changes needed.

## Output tables

See [docs/tables.md](docs/tables.md) for the grain, keys and relationships of all 15 tables.

## Tests

    make test

Tests are deliberately few and focused: a handful per module. Pure-Python logic (CLI, load order, type mapping)
is tested directly. Polars transformations are tested on tiny hand-built frames. The Postgres `COPY` and
constraint code is exercised by a real run (`make run-pg`), not by unit tests.

## Known differences from the original notebook code

Worth knowing when you compare against a golden dataset:

- Geo is mapped per user from their first sighting; device from each user's first row.
- Converting-journey dates are converted from the converting table itself (the original used the wrong frame).
- Event facts get a `date_id`; the event-item bridge is an inner join.
- `total_lifetime_events` sums each session's `event_count`.
- Basket item columns are sorted alphabetically; items with no revenue are dropped; community numbers can differ
  from the original run, so compare the groupings, not the labels.

## Layout

    src/ga4_ecommerce_analytics_engine/
        schema.py  pipeline.py  cli.py
        sources/  cleaning/  enrichment/  aggregation/  dimensions/  facts/  analytics/  writers/  utils/
    sql/bigquery/                 query templates
    tests/unit/                   mirrors src/
    docker-compose.yml  Makefile  .env.example
