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
    assert "'events'" in queries[0]
    assert "'items'" in queries[1]
    assert "'dimensions'" in queries[2]

def test_fetch_all_returns_raw_data_with_three_tables(make_source, fake_client):
    raw = make_source().fetch_all(START, END)

    assert isinstance(raw, RawData)
    assert isinstance(raw.events, pl.DataFrame)
    assert isinstance(raw.items, pl.DataFrame)
    assert isinstance(raw.dimensions, pl.DataFrame)
    assert len(fake_client.run_calls) == 3

def test_validate_columns_passes_when_events_is_subset_of_items(make_source):
    make_source().validate_columns(START, END)     # events cols ⊆ items cols → no raise

def test_validate_columns_raises_when_events_has_a_column_missing_from_items(make_source, fake_client):
    fake_client.columns_by_name = {
        "events": ["a", "b", "only_in_events"],
        "items": ["a", "b"],
        "dimensions": ['date_id'],
    }
    with pytest.raises(KeyError, match="only_in_events"):
        make_source().validate_columns(START, END)

def test_validate_columns_fails_if_columns_are_empty(make_source, fake_client):
    fake_client.columns_by_name = {"events": [], "items": [], "dimensions": []}
    with pytest.raises(RuntimeError, match="no columns"):
        make_source().validate_columns(START, END)

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

def test_changing_the_date_range_misses_the_cache(make_source, fake_client, loader):
    source = make_source()
    source.fetch_events(START, END)
    source.fetch_events(START, "2020-12-04")

    old_path = source._cache_path('events', loader.render('events', START, END))
    new_path = source._cache_path('events', loader.render('events', START, "2020-12-04"))

    assert len(fake_client.run_calls) == 2
    assert old_path.is_file() and new_path.is_file()
    assert old_path != new_path

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

def test_cache_file_uses_parquet_extension(make_source, fake_client):
    source = make_source()
    source.fetch_events(START, END)

    written = list(source.cache_dir.glob("*"))
    assert len(written) == 1
    assert written[0].suffix == ".parquet"     # fails today with ".parquest"

def test_write_cache_leaves_no_partial_file_on_failure(make_source, monkeypatch):
    source = make_source()
    source.cache_dir.mkdir(parents=True)

    def boom(self, path):
        raise OSError("disk full")
    monkeypatch.setattr(pl.DataFrame, "write_parquet", boom)

    with pytest.raises(OSError):
        source._fetch("events", START, END)

    # only a temp file (or nothing), never a half-written .parquet
    stray = [p for p in source.cache_dir.iterdir() if p.suffix == ".parquet"]
    assert stray == []

# --- Costs --------------------------------------

def test_estimate_cost_covers_all_three_queries_and_runs_nothing(
        make_source, fake_client
):
    estimates = make_source().estimate_cost(START, END)

    assert set(estimates) == {"events", "items", "dimensions"}
    assert len(fake_client.estimate_calls) == 3
    assert fake_client.run_calls == [] # a dry run must never execute a real query

def test_estimate_cost_logs_a_single_cad_total(make_source, caplog):
    with caplog.at_level("INFO", logger="ga4_ecommerce_analytics_engine.sources.bigquery_source"):
        make_source().estimate_cost(START, END)

    total_lines = [r for r in caplog.records if "Total estimate" in r.message]
    assert len(total_lines) == 1
    assert "CAD" in total_lines[0].message
    # FakeClient returns cost_usd=0.00625, cost_cad=0.00875 → 3 × 0.00875 = 0.02625
    expected_total = f"{3 * 0.00875:.4f}"
    assert expected_total in total_lines[0].message