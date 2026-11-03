# Architecture

![Pipeline](pipeline_flow.png)

    CLI -> loader (BigQuery) -> cleaner -> polars transform, analytics, star schema -> Postgres -> Power BI -> web

`Pipeline().run(raw)` in `pipeline.py` takes the three raw extracts (events, items, user dimensions) and returns the
22 output tables as polars frames. `sources/` fetches and caches, and `writers/` loads.
Each module has a flowchart in [modules.md](modules.md).

## Stages

| Stage | Module | Input -> output |
|---|---|---|
| source | `sources/` | BigQuery SQL templates (`sql/bigquery/`) -> raw frames, cached as parquet in `data/cache` |
| clean | `cleaning/transactions.py` | raw events and items -> one purchase event per transaction with a new transaction id; duplicates and purchases with no revenue are dropped; composite session ids only when `composition_key` is on (`Pipeline` leaves it off) |
| enrich | `enrichment/` | events -> resolved UTM values per session, then a channel from ordered rules |
| aggregate | `aggregation/` | events -> sessions -> user journeys (paths, durations, conversion value) |
| dimensions | `dimensions/` | date, geo, device, traffic source, product, item, transaction; integer keys |
| facts | `facts/` | event, item funnel, session, user, journey tables with keys attached |
| attribution | `analytics/attribution.py` | sessions + `fact_converting_journey` -> credit per session per model (runs after the facts) |
| basket | `analytics/basket.py` | purchased items -> one row per item pair with support, confidence, lift |
| network | `analytics/network.py` | cleaned items -> own 0/1 basket matrix -> pair counts -> floor, backbone, communities, hub and bridge metrics, drawing layout |
| write | `writers/` | frames -> parquet files, or Postgres in one transaction with keys |

## Side routes

- **Cost check.** `--estimate-cost` (`make cost`) shows the BigQuery cost estimate and stops. Nothing is billed.

- **Local cache.** Raw BigQuery results are read from and written to `data/cache`. `--refresh` re-runs the queries;
  `--no-cache` ignores the cache.

- **Parquet.** The star schema can be written as one parquet file per table (`--output-dir`) without Postgres.

- **pgAdmin.** Runs beside Postgres in Docker for inspecting the loaded tables.

## Design rules

- **Stages are *pure* functions (I/O).** Each takes polars frames and returns polars frames, so each is tested with some hard coded rows.

- **Column names are in `schema.py`.** `DataSchema` is a **frozen** dataclass of every column name and event value.
  Stages subclass it, so a rename is one change.

- **Integer surrogate keys.** Dimensions assign keys in sorted order, so keys do not depend on BigQuery row order.
  Facts carry keys, not descriptive columns. `attach_keys` refuses a mapping that would duplicate fact rows.

- **Geo and device are per user** (first sighting); traffic source is per session.

- **One vocabulary for unknowns.** Dimension columns are lower-cased, and `''`, `(not set)`, `<other>`, `(none)` and nulls
  all become `unspecified` (`(direct)` becomes `direct`, `(data deleted)` becomes `redacted`), so one place or device
  has one key. Values in `dim_geo`, `dim_device` and `dim_traffic_source` are therefore lower case.

- **Rules are editable.** Channels come from the ordered list in `enrichment/channel_rules.py`; the first match wins.
  `enrichment/channel_groups.py` collapses small channels for charts.

- **Cheap re-runs.** BigQuery results are cached; `make cost` dry-runs the queries and bills nothing.

- **Safe loads.** Postgres is loaded in one transaction. Primary and foreign keys are created with the tables.

- **Nothing invented.** A purchase with no revenue is dropped, not filled in (see the README, Data quality).

## Item model

A product is a name. An item is a product plus a variant (size, colour). Brand and category belong to the product:
each product takes its most common real value (ties go to the alphabetically first) and every variant inherits it.
A product with no real value gets `Uncategorized` or `Unbranded`, never `(not set)` or `--`.

The item funnel is counted per product because GA4 often records views without a variant. Purchases and baskets use
items (`bridge_transaction_item`, `dim_item`).

## Loading (writers/)

`PostgresWriter.write(tables)` first checks, before touching the database, that every table has a spec in
`writers/warehouse.py` and that each primary key is present and unique. It then works in **one transaction**: create the
schema, drop this run's tables, create them from the polars types, `COPY` the rows in chunks of 200,000, add primary
keys, foreign keys (each with an index) and run `ANALYZE`. Tables load parents first (`load_order`). If anything fails
everything rolls back, and Power BI keeps seeing the old tables until the commit.

Connection settings come from `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD`
(in `.env`). `write_parquet` writes `data/output/<table>.parquet`, one file per table, with no Postgres needed.

## Utilities (utils/)

`binning.py` makes log-spaced bins for skewed columns (journey length, revenue) with readable labels;
`formatting.py` turns hours into `45m` / `5h` / `3d` and values into `$12`; `paths.py` joins a channel path with `" > "`.
The log-bin transform is not called by the pipeline at present.

## Postgres in Docker

`docker-compose.yml` runs Postgres 17 and pgAdmin. Settings come from `.env` (copy `.env.example`).
