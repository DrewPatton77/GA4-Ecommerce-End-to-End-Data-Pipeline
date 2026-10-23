'''
Test config.

A test config for fake classes, such that no tests will interact with BigQuery. Only
functionality of these classes are tested.
'''

from __future__ import annotations

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.sources.bigquery_client import CostEstimate, Columns
from ga4_ecommerce_analytics_engine.sources.query_loader import QueryLoader

# Each template selects its own name, so the three queries are easy to tell apart.
TEMPLATE = (
    "SELECT '{name}' AS source_name, r'a{{2,}}$' AS regex_sample\n"
    "FROM `{{{{DATASET}}}}.{{{{TABLE}}}}`\n"
    "WHERE _TABLE_SUFFIX BETWEEN '{{{{start_date}}}}' AND '{{{{end_date}}}}'"
)

@pytest.fixture
def sql_dir(tmp_path):
    '''
    A temporary folder holding events.sql, items.sql, and dimensions.sql.
    '''
    folder = tmp_path / "sql"
    folder.mkdir()
    for name in ("events", "items", "dimensions"):
        (folder / f"{name}.sql").write_text(TEMPLATE.format(name=name), encoding='utf-8')
    return folder

@pytest.fixture
def loader(sql_dir):
    '''
    A QueryLoader pointed at the temporary templates, with explicit settings.
    '''
    return QueryLoader(
        sql_dir=sql_dir,
        dataset='proj.dataset',
        table='events_*',
    )

class FakeClient:
    '''
    Stands in for BigQueryClient in BigQuerySource tests. Records every call.
    '''

    def __init__(self, bytes_per_query: int = 1_000_000_000, columns_by_name: dict[str, list[str]] | None = None) -> None:
        self.bytes_per_query = bytes_per_query
        self.run_calls: list[str] = []
        self.estimate_calls: list[str] = []
        self.columns_calls: list[str] = []
        self.columns_by_name = columns_by_name or {
            "events":     ("event_id", "user_pseudo_id", "event_name"),
            "items":      ("event_id", "user_pseudo_id", "event_name", "item_id", "price"),
            "dimensions": ("date_id", "geo_id"),
        }

    def run_query(self, query: str, **kwargs) -> pl.DataFrame:
        self.run_calls.append(query)
        return pl.DataFrame({"query_number": [len(self.run_calls)]})

    def estimate_cost(self, query:str, **kwargs) -> CostEstimate:
        self.estimate_calls.append(query)
        return CostEstimate(
            bytes_scanned = self.bytes_per_query,
            cost_usd = 0.00625,
            cost_cad = 0.00875,
            is_within_budget=True,
        )

    def columns(self, query: str, **kwargs) -> Columns:
        self.columns_calls.append(query)
        for name in ("events", "items", "dimensions"):
            if f"'{name}'" in query:
                return Columns(self.columns_by_name[name])
        raise ValueError(f"FakeClient.columns: unknown query {query!r}")


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()