"""Minimal tests for DataUtm (enrichment/utm.py)."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.enrichment.utm import DataUtm
from ga4_ecommerce_analytics_engine.schema import DataSchema

T = [dt.datetime(2020, 12, 1, 9, m) for m in range(5)]

# NOTE: resolve_session_utm hardcodes pl.col('source'), so the source column must be called 'source'.
COLUMNS = dict(
    user_id='user_pseudo_id',
    session_id="session_id",
    timestamp="event_timestamp_micros",
    event_type="event_name",
    source="source",
    medium="medium",
    campaign="campaign",
)

SCHEMA = {
    'user_pseudo_id': pl.Utf8,
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
        ('u1', "s1", T[0], "session_start", "(direct)", "(none)", None),
        ('u1', "s1", T[1], "page_view", "google", "cpc", None),
        ('u1', "s1", T[2], "view_item", "bing", "organic", "spring"),
        # s2: no utm anywhere
        ('u1', "s2", T[0], "page_view", None, None, None),
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
    assert result["s2"]["medium_utm"] is None
    assert result["s2"]["campaign_utm"] is None


def test_enrich_keeps_every_event_and_copies_session_values(utm):
    events = make_events()

    result = utm.resolve(events)

    assert result.events.height == events.height
    assert set(result.events.filter(pl.col("session_id") == "s1")["source_utm"]) == {"google"}
    assert result.sessions.height == 2
    result = utm.resolve_session_utm(make_events())
    assert set(result.columns) == {'session_id', 'source_utm', 'medium_utm', 'campaign_utm'}

def test_custom_utm_column_names_are_respected():
    events = make_events().rename({
        'source': 'src', 'medium': 'med', 'campaign': 'cmp',
    })
    custom = DataUtm(**{**COLUMNS, 'source': 'src', 'medium': 'med', 'campaign': 'cmp'})
    result = sessions_by_id(custom.resolve_session_utm(events))

    assert result['s1']['source_utm'] == 'google'
    assert result['s1']['medium_utm'] == 'cpc'
    assert result['s1']['campaign_utm'] == 'spring'

def test_session_with_only_session_start_uses_that_event():
    events = pl.DataFrame([
        ('u1', 's1', T[0], 'session_start', 'google', 'cpc', 'spring'),
    ], schema=SCHEMA, orient='row')
    result = sessions_by_id(DataUtm(**COLUMNS).resolve_session_utm(events))
    assert result['s1']['source_utm'] == 'google'
    assert result['s1']['campaign_utm'] == 'spring'

def test_direct_placeholder_preserved_when_no_real_source_exists():
    events = pl.DataFrame([
        ('u1', 's1', T[0], 'session_start', '(direct)', '(none)', None),
        ('u1', 's1', T[1], 'page_view', '(direct)', '(none)', None),
    ], schema=SCHEMA, orient='row')
    result = sessions_by_id(DataUtm(**COLUMNS).resolve_session_utm(events))
    assert result['s1']['source_utm'] == '(direct)'
    assert result['s1']['campaign_utm'] is None

def test_double_resolve_raises_or_is_idempotent():
    utm = DataUtm(**COLUMNS)
    first = utm.resolve(make_events())
    with pytest.raises(Exception):   # or whatever your fix does
        utm.resolve(first.events)