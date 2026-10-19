"""Minimal tests for the concrete dimensions."""

from __future__ import annotations

import datetime as dt

import polars as pl

from ga4_ecommerce_analytics_engine.dimensions.date import DateDimension
from ga4_ecommerce_analytics_engine.dimensions.device import DeviceDimension
from ga4_ecommerce_analytics_engine.dimensions.geo import GeoDimension
from ga4_ecommerce_analytics_engine.dimensions.items import ItemDimension, TransactionDimension
from ga4_ecommerce_analytics_engine.dimensions.traffic_source import TrafficSourceDimension

T = [dt.datetime(2020, 12, 1, 9, m) for m in range(3)]


def test_geo_user_mapping_uses_the_first_location_and_never_duplicates_users():
    rows = pl.DataFrame(
        {
            "user_pseudo_id": ["u1", "u1", "u2"],
            "event_timestamp_micros": [T[1], T[0], T[0]],
            "continent": ["Europe", "Americas", "Asia"],
            "country": ["FR", "US", "JP"],
            "region": ["x", "y", "z"],
            "city": ["Paris", "Austin", "Tokyo"],
        }
    )

    dim, mapping = GeoDimension().build_with_user_mapping(rows)

    assert dim.height == 3  # every location seen
    assert mapping.height == 2  # but one row per user
    austin = dim.filter(pl.col("city") == "Austin")["geo_id"][0]
    assert mapping.filter(pl.col("user_pseudo_id") == "u1")["geo_id"][0] == austin  # u1's first sighting


def test_device_dimension_is_built_from_each_users_first_device():
    rows = pl.DataFrame(
        {
            "user_pseudo_id": ["u1", "u1"],
            "event_timestamp_micros": [T[0], T[1]],
            "device_category": ["mobile", "desktop"],
            "device_brand_name": ["a", "b"],
            "device_model_name": ["m", "n"],
            "device_os": ["ios", "mac"],
            "operating_system_version": ["1", "2"],
        }
    )

    dim, mapping = DeviceDimension().build_with_user_mapping(rows)

    assert dim["device_category"].to_list() == ["mobile"]
    assert mapping["device_id"].to_list() == [0]


def test_traffic_source_gives_sessions_and_users_a_key():
    sessions = pl.DataFrame(
        {
            "user_pseudo_id": ["u1", "u1", "u2"],
            "session_id": ["u1-1", "u1-2", "u2-1"],
            "session_start": [T[0], T[1], T[0]],
            "source_utm": ["google", "(direct)", "google"],
            "medium_utm": ["cpc", "(none)", "cpc"],
            "campaign_utm": ["", "", ""],
            "channel": ["Paid Search", "Direct", "Paid Search"],
        }
    )

    result = TrafficSourceDimension().build_with_mappings(sessions)

    assert result.dimension.height == 2  # Paid Search and Direct
    assert result.session_mapping.height == 3
    assert result.user_mapping.height == 2
    paid = result.dimension.filter(pl.col("channel") == "Paid Search")["traffic_source_id"][0]
    first_u1 = result.user_mapping.filter(pl.col("user_pseudo_id") == "u1")["traffic_source_id"][0]
    assert first_u1 == paid  # u1's first session was Paid Search


def test_date_dimension_columns():
    events = pl.DataFrame({"event_date": [dt.date(2020, 12, 5), dt.date(2020, 12, 5), dt.date(2020, 12, 7)]})

    dim = DateDimension().build(events)

    assert dim.height == 2
    saturday = dim.row(0, named=True)
    assert saturday["date_id"] == 20201205
    assert saturday["day_name"] == "Saturday"
    assert saturday["is_weekend"] is True
    assert dim.row(1, named=True)["is_weekend"] is False  # Monday


def test_item_dimension_skips_not_set_and_takes_the_highest_price():
    items = pl.DataFrame(
        {
            "item_name": ["A", "A", "(not set)"],
            "item_brand": ["b", "b", None],
            "item_variant": [None, None, None],
            "item_category": ["c", "c", None],
            "price": [5.0, 7.0, 1.0],
        }
    )

    dim = ItemDimension().build(items)

    assert dim["item_id"].to_list() == ["A"]
    assert dim["price"].to_list() == [7.0]


def test_transaction_dimension_keeps_purchases_only():
    events = pl.DataFrame(
        {
            "event_name": ["page_view", "purchase"],
            "transaction_id": [None, "t1"],
            "conversion_timestamp": [None, T[0]],
            "basket_size": [None, 2],
            "event_value": [None, 40.0],
            "unique_items": [None, 2],
        }
    )
    items = pl.DataFrame(
        {
            "event_name": ["view_item", "purchase", "purchase", "purchase"],
            "transaction_id": [None, "t1", "t1", "t1"],
            "item_name": ["A", "A", "A", "B"],
        }
    )

    result = TransactionDimension().build(events, items)

    assert result.transactions["transaction_id"].to_list() == ["t1"]
    assert result.transaction_items["item_name"].to_list() == ["A", "B"]  # duplicate A removed
