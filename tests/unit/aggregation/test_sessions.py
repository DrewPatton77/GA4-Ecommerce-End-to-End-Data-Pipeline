"""Tests for aggregation/sessions.py (SessionBuilder) on small hand-made frames."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.aggregation.sessions import SessionBuilder

D1 = dt.date(2020, 12, 1)
D2 = dt.date(2020, 12, 2)


def at(minute: int) -> dt.datetime:
    return dt.datetime(2020, 12, 1, 9, minute, 0)


EVENT_SCHEMA = {
    "user_pseudo_id": pl.Utf8,
    "session_id": pl.Utf8,
    "event_timestamp_micros": pl.Datetime,
    "event_name": pl.Utf8,
    "event_date": pl.Date,
    "session_number": pl.Int64,
    "engagement_time_msec": pl.Int64,
    "session_engaged": pl.Utf8,
    "conversion_timestamp": pl.Datetime,
    "event_value": pl.Float64,
    "basket_size": pl.Int64,
}


def event(user, session, minute, name, *, date=D1, session_number=1, engagement=None,
          engaged=None, value=None, basket=None):
    is_purchase = name == "purchase"
    return {
        "user_pseudo_id": user,
        "session_id": f"{user}-{session}",
        "event_timestamp_micros": at(minute),
        "event_name": name,
        "event_date": date,
        "session_number": session_number,
        "engagement_time_msec": engagement,
        "session_engaged": engaged,
        "conversion_timestamp": at(minute) if is_purchase else None,
        "event_value": value,
        "basket_size": basket,
    }


def make_events() -> pl.DataFrame:
    rows = [
        # u1-1: a full funnel ending in one purchase
        event("u1", 1, 0, "page_view", engagement=1000, engaged="1"),
        event("u1", 1, 1, "page_view", engagement=2000, engaged="1"),
        event("u1", 1, 2, "view_item", engagement=500),
        event("u1", 1, 3, "add_to_cart", engagement=500),
        event("u1", 1, 4, "begin_checkout", engagement=0),
        event("u1", 1, 5, "purchase", value=40.0, basket=3),
        # u1-2: a later, non-engaged session
        event("u1", 2, 30, "page_view", date=D2, session_number=2, engagement=300, engaged="0"),
        # u2-1: engagement never reported
        event("u2", 1, 0, "page_view", engagement=100),
        # u3-1: has no row in the channel table
        event("u3", 1, 0, "page_view"),
        # u4-1: two purchases in one session
        event("u4", 1, 0, "purchase", value=10.0, basket=1),
        event("u4", 1, 1, "purchase", value=20.0, basket=2),
    ]
    return pl.DataFrame(rows, schema=EVENT_SCHEMA)


def make_channels() -> pl.DataFrame:
    # Like the real pipeline: one row per session, keyed by session_id only (no user id column).
    return pl.DataFrame(
        {
            "session_id": ["u1-1", "u1-2", "u2-1", "u4-1"],
            "source_utm": ["google", "(direct)", "bing", "some-site.com"],
            "medium_utm": ["cpc", "(none)", "organic", "referral"],
            "campaign_utm": ["", "", "", ""],
            "channel": ["Paid Search", "Direct", "Organic Search", "Referral"],
        }
    )


@pytest.fixture
def sessions():
    result = SessionBuilder().build(make_events(), make_channels())
    return {row["session_id"]: row for row in result.iter_rows(named=True)}


def test_one_row_per_session():
    result = SessionBuilder().build(make_events(), make_channels())

    assert result.height == 5
    assert result["session_id"].n_unique() == 5


def test_funnel_counts(sessions):
    row = sessions["u1-1"]

    assert row["page_views"] == 2
    assert row["item_views"] == 1
    assert row["carts"] == 1
    assert row["checkouts"] == 1
    assert row["event_count"] == 6


def test_timing_and_engagement(sessions):
    row = sessions["u1-1"]

    assert row["session_start"] == at(0)
    assert row["session_date"] == D1
    assert row["session_number"] == 1
    assert row["engagement_time"] == 4000  # null engagement values are ignored
    assert row["session_engaged"] == 1


def test_session_engaged_is_parsed_from_text_and_stays_null_when_unreported(sessions):
    assert sessions["u1-2"]["session_engaged"] == 0
    assert sessions["u2-1"]["session_engaged"] is None


def test_later_session_keeps_its_own_date_and_number(sessions):
    assert sessions["u1-2"]["session_date"] == D2
    assert sessions["u1-2"]["session_number"] == 2


def test_converting_session_totals(sessions):
    row = sessions["u1-1"]

    assert row["converted"] == 1
    assert row["conversions_in_session"] == 1
    assert row["value"] == 40.0
    assert row["quantity"] == 3  # the schema's item_quantity column holds the summed basket size
    assert row["conversion_timestamp"] == at(5)


def test_non_converting_session_has_null_totals_and_is_not_converted(sessions):
    row = sessions["u1-2"]

    assert row["converted"] == 0
    assert row["value"] is None
    assert row["conversions_in_session"] is None


def test_two_purchases_in_one_session_are_summed(sessions):
    row = sessions["u4-1"]

    assert row["conversions_in_session"] == 2
    assert row["value"] == 30.0
    assert row["quantity"] == 3
    assert row["conversion_timestamp"] == at(0)  # the earliest purchase


def test_channel_columns_are_carried_through(sessions):
    row = sessions["u1-1"]

    assert row["channel"] == "Paid Search"
    assert row["source_utm"] == "google"
    assert row["medium_utm"] == "cpc"


def test_session_missing_from_channel_table_gets_null_channel(sessions):
    row = sessions["u3-1"]

    assert row["channel"] is None
    assert row["engagement_time"] == 0  # nothing reported sums to zero


def test_duplicate_channel_rows_are_rejected():
    channels = pl.concat([make_channels(), make_channels().head(1)])

    with pytest.raises(ValueError, match="duplicate"):
        SessionBuilder().build(make_events(), channels)


def test_missing_event_column_raises_a_readable_error():
    with pytest.raises(KeyError, match="basket_size"):
        SessionBuilder().build(make_events().drop("basket_size"), make_channels())


def test_missing_channel_column_raises_a_readable_error():
    with pytest.raises(ValueError, match="channel"):
        SessionBuilder().build(make_events(), make_channels().drop("channel"))


def test_output_column_names_can_be_changed_through_the_schema():
    result = SessionBuilder(page_views="views").build(make_events(), make_channels())

    assert "views" in result.columns
    assert "page_views" not in result.columns
    assert "carts" in result.columns