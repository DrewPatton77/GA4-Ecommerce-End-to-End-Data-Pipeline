"""Minimal tests for the fact builders."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.facts.events import EventFacts, EventItemBridge
from ga4_ecommerce_analytics_engine.facts.item_funnel import ItemFunnelFacts
from ga4_ecommerce_analytics_engine.facts.journeys import JourneyFacts
from ga4_ecommerce_analytics_engine.facts.keys import attach_keys
from ga4_ecommerce_analytics_engine.facts.sessions import SessionFacts
from ga4_ecommerce_analytics_engine.facts.users import UserFacts

T0 = dt.datetime(2020, 12, 1, 9, 0)
T1 = dt.datetime(2020, 12, 1, 9, 5)
D1 = dt.date(2020, 12, 1)
D2 = dt.date(2020, 12, 2)
D3 = dt.date(2020, 12, 3)


# ---- Events and the bridge ---------------------------------------------------


def make_events() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "user_pseudo_id": ["u2", "u1", "u1"],
            "session_id": ["u2-1", "u1-1", "u1-1"],
            "event_timestamp_micros": [T0, T1, T0],
            "event_name": ["purchase", "page_view", "purchase"],
            "event_date": [D1, D1, D1],
            "session_engaged": ["1", None, "0"],
            "transaction_id": ["t2", None, "t1"],
            "country": ["US", "US", "FR"],
        }
    )


def test_event_ids_follow_the_original_row_order_and_facts_are_sorted_by_user_then_time():
    event_facts = EventFacts()

    facts = event_facts.build(event_facts.add_event_ids(make_events()))

    assert facts["user_pseudo_id"].to_list() == ["u1", "u1", "u2"]
    assert facts["event_timestamp_micros"].to_list()[:2] == [T0, T1]
    assert facts["event_id"].to_list() == [2, 1, 0]  # ids were given before sorting


def test_event_facts_drop_dimension_columns_and_add_date_id():
    event_facts = EventFacts()

    facts = event_facts.build(event_facts.add_event_ids(make_events()))

    assert "country" not in facts.columns
    assert "transaction_id" not in facts.columns
    assert "event_date" not in facts.columns
    assert set(facts["date_id"]) == {20201201}
    assert facts.schema["session_engaged"] == pl.Int8


def test_bridge_links_events_to_items_and_skips_not_set():
    events = EventFacts().add_event_ids(make_events())
    items = pl.DataFrame(
        {
            "user_pseudo_id": ["u2", "u1", "u1"],
            "session_id": ["u2-1", "u1-1", "u1-1"],
            "event_timestamp_micros": [T0, T0, T0],
            "event_name": ["purchase", "purchase", "purchase"],
            "item_name": ["B", "A", "(not set)"],
        }
    )

    bridge = EventItemBridge().build(events, items)

    assert bridge.columns == ["event_id", "item_id"]
    assert sorted(zip(bridge["event_id"], bridge["item_id"])) == [(0, "B"), (2, "A")]


# ---- Item funnel -------------------------------------------------------------


def test_item_funnel_backfills_earlier_steps_and_ignores_not_set():
    rows = [
        # A: viewed, carted, purchased -> everything 1
        ("u1", "s1", D1, "view_item", "A", None, None),
        ("u1", "s1", D1, "add_to_cart", "A", None, None),
        ("u1", "s1", D1, "purchase", "A", 10.0, 2),
        # C: only reached checkout -> viewed and carted are filled in
        ("u1", "s1", D1, "begin_checkout", "C", None, None),
        ("u1", "s1", D1, "view_item", "(not set)", None, None),
    ]
    items = pl.DataFrame(
        rows,
        schema={
            "user_pseudo_id": pl.Utf8, "session_id": pl.Utf8, "event_date": pl.Date, "event_name": pl.Utf8,
            "item_name": pl.Utf8, "item_revenue": pl.Float64, "quantity": pl.Int64,
        },
        orient="row",
    )

    result = {row["item_id"]: row for row in ItemFunnelFacts().build(items).iter_rows(named=True)}

    assert set(result) == {"A", "C"}
    assert [result["A"][c] for c in ("is_viewed", "is_added_to_cart", "is_checked_out", "is_purchased")] == [1, 1, 1, 1]
    assert [result["C"][c] for c in ("is_viewed", "is_added_to_cart", "is_checked_out", "is_purchased")] == [1, 1, 1, 0]
    assert result["A"]["revenue"] == 10.0
    assert result["A"]["quantity"] == 2
    assert result["A"]["date_id"] == 20201201
    assert sorted(r["item_funnel_id"] for r in result.values()) == [0, 1]


# ---- Sessions and users ------------------------------------------------------

SESSION_SCHEMA = {
    "user_pseudo_id": pl.Utf8, "session_id": pl.Utf8, "session_start": pl.Datetime, "session_date": pl.Date,
    "page_views": pl.Int64, "session_engaged": pl.Int8, "engagement_time": pl.Int64, "session_number": pl.Int64,
    "event_count": pl.Int64, "converted": pl.Int8, "conversions_in_session": pl.Int64, "value": pl.Float64,
    "quantity": pl.Int64, "channel": pl.Utf8, "source_utm": pl.Utf8,
}


def make_sessions() -> pl.DataFrame:
    rows = [
        # u1: a converting session, then a later one that did not convert
        ("u1", "u1-1", T0, D1, 2, 1, 4000, 1, 6, 1, 1, 40.0, 3, "Direct", "(direct)"),
        ("u1", "u1-2", T1, D2, 1, 0, 300, 2, 1, 0, None, None, None, "Direct", "(direct)"),
        # u2: never converted
        ("u2", "u2-1", T0, D1, 1, 1, 100, 1, 2, 0, None, None, None, "Organic Search", "google"),
        # u3: converted twice
        ("u3", "u3-1", T0, D1, 1, 1, 100, 1, 3, 1, 1, 10.0, 1, "Direct", "(direct)"),
        ("u3", "u3-2", T1, D3, 1, 1, 100, 2, 3, 1, 1, 20.0, 2, "Direct", "(direct)"),
    ]
    return pl.DataFrame(rows, schema=SESSION_SCHEMA, orient="row")


def test_session_facts_get_a_date_id_and_lose_traffic_source_columns():
    facts = SessionFacts().build(make_sessions())

    assert facts.filter(pl.col("session_id") == "u1-2")["date_id"][0] == 20201202
    for column in ("channel", "source_utm", "session_date"):
        assert column not in facts.columns
    assert facts.height == 5


def test_key_column_names_come_from_the_schema():
    facts = SessionFacts(date_id="day_key").build(make_sessions())

    assert "day_key" in facts.columns
    assert "date_id" not in facts.columns


def test_user_facts_roll_sessions_up_to_one_row_per_user():
    facts = {row["user_pseudo_id"]: row for row in UserFacts().build(make_sessions()).iter_rows(named=True)}

    u1 = facts["u1"]
    assert (u1["first_active_date"], u1["last_active_date"]) == (20201201, 20201202)
    assert u1["total_pageviews"] == 3
    assert u1["total_engaged_sessions"] == 1
    assert u1["total_engagement_time_msec"] == 4300
    assert u1["total_sessions"] == 2
    assert u1["total_lifetime_events"] == 7
    assert u1["lifetime_revenue"] == 40.0
    assert (u1["total_purchases"], u1["total_items_purchased"]) == (1, 3)
    assert (u1["converted"], u1["repeat"]) == (1, 0)


def test_user_facts_converted_and_repeat_flags():
    facts = {row["user_pseudo_id"]: row for row in UserFacts().build(make_sessions()).iter_rows(named=True)}

    assert (facts["u2"]["converted"], facts["u2"]["repeat"]) == (0, 0)
    assert (facts["u3"]["total_conversions"], facts["u3"]["repeat"]) == (2, 1)


# ---- Journeys ----------------------------------------------------------------


def test_journey_facts_convert_each_tables_own_dates_and_drop_path_columns():
    journeys = pl.DataFrame(
        {
            "user_pseudo_id": ["u1", "u2"],
            "journey_start": [D1, D3],
            "journey_end": [D2, D3],
            "conversion_path": [["Direct"], ["Direct"]],
            "hours_before": [[0.0], [0.0]],
            "touchpoints": [1, 1],
        }
    )
    converting = journeys.filter(pl.col("user_pseudo_id") == "u2")  # only u2 converted

    result = JourneyFacts().build(journeys, converting)

    assert result.journeys["journey_id"].to_list() == [0, 1]
    assert result.journeys["journey_start"].to_list() == [20201201, 20201203]
    assert result.converting["converting_journey_id"].to_list() == [0]
    assert result.converting["journey_start"].to_list() == [20201203]  # u2's own start, not u1's
    assert "conversion_path" not in result.journeys.columns
    assert "hours_before" not in result.converting.columns


# ---- Keys --------------------------------------------------------------------


def test_attach_keys_adds_each_key_without_adding_rows():
    fact = pl.DataFrame({"user_pseudo_id": ["u1", "u1", "u2"], "session_id": ["s1", "s2", "s3"]})
    geo = pl.DataFrame({"user_pseudo_id": ["u1", "u2"], "geo_id": [0, 1]})
    traffic = pl.DataFrame({"session_id": ["s1", "s2", "s3"], "traffic_source_id": [5, 5, 6]})

    result = attach_keys(fact, [(geo, "user_pseudo_id"), (traffic, "session_id")])

    assert result.height == 3
    assert result["geo_id"].to_list() == [0, 0, 1]
    assert result["traffic_source_id"].to_list() == [5, 5, 6]


def test_attach_keys_refuses_a_mapping_that_would_duplicate_rows():
    fact = pl.DataFrame({"user_pseudo_id": ["u1"]})
    geo = pl.DataFrame({"user_pseudo_id": ["u1", "u1"], "geo_id": [0, 1]})

    with pytest.raises(ValueError, match="more than one row"):
        attach_keys(fact, [(geo, "user_pseudo_id")])
