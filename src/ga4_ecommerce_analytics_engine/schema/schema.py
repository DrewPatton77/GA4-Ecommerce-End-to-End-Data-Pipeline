"""Minimal tests for DataUtm (enrichment/utm.py)."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.enrichment.utm import DataUtm

T = [dt.datetime(2020, 12, 1, 9, m) for m in range(5)]

COLUMNS = dict(
    session_id="session_id",
    timestamp="event_timestamp_micros",
    event_type="event_name",
    source="source",
    medium="medium",
    campaign="campaign",
)

SCHEMA = {
    "session_id": pl.Utf8,
    "event_timestamp_micros": pl.Datetime,
    "event_name": pl.Utf8,
    "source": pl.Utf8,
    "medium": pl.Utf8,
    "campaign": pl.Utf8,
}


def make_events() -> pl.DataFrame:
    rows = [
        # s1: session_start carries 'direct'; the first real event carries google/cpc, no campaign;
        # a later event supplies the campaign.
        ("s1", T[0], "session_start", "(direct)", "(none)", None),
        ("s1", T[1], "page_view", "google", "cpc", None),
        ("s1", T[2], "view_item", "bing", "organic", "spring"),
        # s2: no utm anywhere
        ("s2", T[0], "page_view", None, None, None),
    ]
    return pl.DataFrame(rows, schema=SCHEMA, orient="row")


@pytest.fixture
def utm():
    return DataUtm(**COLUMNS)


def sessions_by_id(df: pl.DataFrame) -> dict[str, dict]:
    return {row["session_id"]: row for row in df.iter_rows(named=True)}


def test_first_non_null_per_column_with_initialization_events_ranked_last(utm):
    result = sessions_by_id(utm.resolve_session_utm(make_events()))

    assert result["s1"]["source_utm"] == "google"  # not the session_start '(direct)'
    assert result["s1"]["medium_utm"] == "cpc"
    assert result["s1"]["campaign_utm"] == "spring"  # each column is resolved independently


def test_session_without_utm_gets_nulls(utm):
    result = sessions_by_id(utm.resolve_session_utm(make_events()))

    assert result["s2"]["source_utm"] is None
    assert result["s2"]["campaign_utm"] is None


def test_enrich_keeps_every_event_and_copies_session_values(utm):
    events = make_events()

    result = utm.enrich_events_with_utm(events)

    assert result.events.height == events.height
    assert set(result.events.filter(pl.col("session_id") == "s1")["source_utm"]) == {"google"}
    assert result.sessions.height == 2
    assert not any(c.startswith("_") for c in result.events.columns)  # helper columns don't leak


def test_check_required_columns_names_the_missing_ones(utm):
    with pytest.raises(KeyError, match="campaign"):
        utm._check_required_columns(make_events().drop("campaign"))