# GA4 Ecommerce Analytics Engine

![Pipeline](docs/ga4_analytics_pipeline.svg)

[![Open the interactive dashboard](https://img.shields.io/badge/%E2%96%B6%20Open%20the%20interactive%20dashboard-D5AA60?style=for-the-badge)](PASTE_PUBLISH_TO_WEB_LINK_HERE)

Turns the public GA4 sample ecommerce data (Google Merchandise Store, 1 Nov 2020 to 31 Jan 2021) into a star schema
in Postgres and a seven-page Power BI report: daily performance, marketing and attribution, customer journeys,
products and funnel, basket analysis and an item network.

## Stack

| Layer | Tools |
|---|---|
| Source | Google BigQuery |
| Transform and analytics | Python, polars, NumPy, NetworkX |
| Warehouse | PostgreSQL 17 and pgAdmin in Docker, loaded with psycopg |
| Report | Power BI, with a Deneb (Vega) network visual |
| Tooling | uv, make, pytest |

## Quick start

```bash
uv sync
cp .env.example .env      # set POSTGRES_PASSWORD
make db-up                # Postgres in Docker
make cost                 # dry-run the BigQuery queries (nothing is billed)
make run-pg               # build everything and load Postgres
```

`make` lists every task. Run `uv run ga4-pipeline --help` for the options.

> [!WARNING]
> From 26 Jan 2021 the source drops purchase revenue (38% of purchases on 26 Jan, 100% on 31 Jan), so revenue and
> purchases fall at the end of the period. This is a direct data quality issue. See:
> [docs/development.md](docs/development.md#reading-the-data).

## Documentation

|                                        |                                                  |
| -------------------------------------- | ------------------------------------------------ |
| [Module flowcharts](docs/modules.md)   | One chart per module                             |
| [Output tables](docs/tables.md)        | Every table, grain, and key                      |
| [Architecture](docs/architecture.md)   | Stages and design rules                          |
| [Analytics methods](docs/analytics.md) | Attribution, basket, and network                 |
| [Power BI](docs/powerbi.md)            | Setup, relationships, measures,  and screenshots |
| [Development](docs/development.md)     | Tests and changing things                        |
|                                        |                                                  |
