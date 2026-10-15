'''
Tests for bigquery_source.py using FakeClient from tests/conftest.py.
'''

from __future__ import annotations

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.sources.bigquery_source import BigQuerySource
from ga4_ecommerce_analytics_engine.sources.raw_data import RawData

START, END = "2020-12-01", "2020-12-03"

@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "cache"

@pytest.fixture
def make_source(fake_client, loader, cache_dir):
    def _make(**kwargs) -> BigQuerySource:
        return BigQuerySource(
            client=fake_client, loader=loader, cache_dir=cache_dir, **kwargs
        )

    return _make

# --- Fetching -----------------------------------------

def test_fetch_events_runs_the_rendered_events_query(make_source, fake_client):
    df = make_source().fetch_events(START, END)

    assert isinstance(df, pl.DataFrame)
    assert len(fake_client.run_calls) == 1
    query = fake_client.run_calls[0]
    assert "'events'" in query
    assert "BETWEEN '20201201' AND '20201203'"

def test_fetch_method_uses_its_own_template(make_source, fake_client):
    source = make_source()

    source.fetch_events(START, END)
    source.fetch_items(START, END)
    source.fetch_dimensions(START, END)

    queries = fake_client.run_calls
    assert "'events" in queries[0]
    assert "'items'" in queries[1]
    assert "'dimensions'" in queries[2]

def test_fetch_all_returns_raw_data_with_three_tables(make_source, fake_client):
    raw = make_source().fetch_all(START, END)

    assert isinstance(raw, RawData)
    assert isinstance(raw.events, pl.DataFrame)
    assert isinstance(raw.items, pl.DataFrame)
    assert isinstance(raw.dimensions, pl.DataFrame)
    assert len(fake_client.run_calls) == 3

# ---- Caching ------------------------------------------

def test_second_fetch_reads_from_cache_not_bigquery(make_source, fake_client):
    source = make_source()

    first = source.fetch_events(START, END)
    second = source.fetch_events(START, END)

    assert len(fake_client.run_calls) == 1
    assert first.equals(second)

def test_fetch_writes_a_parquet_file(make_source, cache_dir):
    source = make_source()
    
    source.fetch_events(START, END)
    
    query = source.loader.render('events', START, END)
    cache_path = source._cache_path('events', query)

    assert cache_path.is_file() == True

def test_changing_the_date_range_misses_the_cache(make_source, fake_client, cache_dir):
    source = make_source()

    source.fetch_events(START, END)
    query = source.loader.render('events', START, END)
    counts = source._cache_path('events', query).is_file()
    
    source.fetch_events(START, "2020-12-04")
    query = source.loader.render('events', START, END)
    counts += source._cache_path('events', query).is_file()

    assert len(fake_client.run_calls) == 2
    assert counts == 2

def test_refresh_requeries_even_when_cached(make_source, fake_client):
    make_source().fetch_events(START, END)

    make_source(refresh=True).fetch_events(START, END)

    assert len(fake_client.run_calls) == 2

def test_use_cache_false_never_reads_or_writes(make_source, fake_client, cache_dir):
    source = make_source(use_cache=False)

    source.fetch_events(START, END)
    source.fetch_events(START, END)

    assert len(fake_client.run_calls) == 2
    assert not cache_dir.exists()

# --- Costs --------------------------------------

def test_estimate_cost_covers_all_three_queries_and_runs_nothing(
        make_source, fake_client
):
    estimates = make_source().estimate_cost(START, END)

    assert set(estimates) == {"events", "items", "dimensions"}
    assert len(fake_client.estimate_calls) == 3
    assert fake_client.run_calls == [] # a dry run must never execute a real query