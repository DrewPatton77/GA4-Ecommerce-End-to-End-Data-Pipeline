"""Minimal tests for the concrete dimensions."""

from __future__ import annotations

import datetime as dt

import polars as pl

from ga4_ecommerce_analytics_engine.dimensions.date import DateDimension
from ga4_ecommerce_analytics_engine.dimensions.device import DeviceDimension
from ga4_ecommerce_analytics_engine.dimensions.geo import GeoDimension
from ga4_ecommerce_analytics_engine.dimensions.items import ItemDimension, TransactionDimension, ProductDimension
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
    austin = dim.filter(pl.col("city") == "austin")["geo_id"][0]
    assert mapping.filter(pl.col("user_pseudo_id") == "u1")["geo_id"][0] == austin  # u1's first sighting


def test_key_and_column_names_come_from_the_schema():
    rows = pl.DataFrame(
        {
            'user_pseudo_id': ['u1'],
            'event_timestamp_micros': [T[0]],
            'continent': ['Asia'],
            'nation': ['JP'],
            'region': ['z'],
            'city': ['Tokyo'],
        }
    )

    dim, mapping = GeoDimension(country='nation', geo_id='location_key').build_with_user_mapping(rows)

    assert dim.columns == ['location_key', 'continent', 'nation', 'region', 'city']
    assert mapping.columns == ['user_pseudo_id', 'location_key']

def test_device_dimension_is_built_from_each_users_first_device():
    rows = pl.DataFrame(
        {
            "user_pseudo_id": ["u1", "u1"],
            "event_timestamp_micros": [T[0], T[1]],
            "device_category": ["mobile", "desktop"],
            "device_brand_name": ["a", "b"],
            "device_model_name": ["m", "n"],
            "device_os": ["ios", "mac"],
            "device_os_version": ["1", "2"],
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
    assert set(result.dimension['channel']) == {'direct', 'paid search'}
    assert set(result.dimension['channel_group']) == {'direct', 'paid search'}
    assert result.session_mapping.height == 3
    assert result.user_mapping.height == 2
    paid = result.dimension.filter(pl.col("channel") == "paid search")["traffic_source_id"][0]
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

def test_channel_groups_collapse_small_channels_but_keep_the_detailed_channel():
    sessions = pl.DataFrame(
        {
            "user_pseudo_id": ["u1", "u2", "u3"],
            "session_id": ["s1", "s2", "s3"],
            "session_start": [T[0], T[0], T[0]],
            "source_utm": ["a", "b", "c"],
            "medium_utm": ["x", "y", "z"],
            "campaign_utm": ["", "", ""],
            "channel": ["Newsletter", "Email", "Unclassified"],
        }
    )

    dim = TrafficSourceDimension().build_with_mappings(sessions).dimension

    assert dict(zip(dim['channel'], dim['channel_group'])) == {
        "newsletter": "email", "email": "email", "unclassified": "unclassified",
    }

def test_product_gets_its_most_common_real_category_and_a_readable_fallback():
    items = pl.DataFrame(
        {
            "item_name": ["Tee", "Tee", "Tee", "Tee", "Bag", "Cup", "(not set)"],
            "item_brand": ["g", "g", None, "(not set)", None, None, "x"],
            "item_category": ["", "Apparel", "Apparel", "--", "(not set)", "Drinkware", "Junk"],
        }
    )

    products = ProductDimension().build(items)
    by_name = {row['item_name']: row for row in products.iter_rows(named=True)}

    assert products['item_name'].to_list() == ['Bag', 'Cup', 'Tee']
    assert products['product_id'].to_list() == [0, 1, 2]
    assert by_name['Tee']['category'] == "Apparel"
    assert by_name['Tee']['brand'] == 'g'
    assert by_name['Bag']['category'] == 'Uncategorized'
    assert by_name['Bag']['brand'] == 'Unbranded'
    assert "(not set)" not in products['category'].to_list() and "--" not in products['category'].to_list()

def test_item_dimension_has_one_row_per_variant_and_points_at_its_product():
    items = pl.DataFrame(
        {
            "item_name": ["Tee", "Tee", "Tee", "Bag", "(not set)"],
            "item_brand": ["g", "g", "g", None, None],
            "item_variant": [" MD", " LG", " MD", None, "x"],
            "item_category": ["", "Apparel", "Apparel", "Bags", None],
            "price": [14.0, 14.0, 15.0, 5.0, 1.0],
        }
    )
    products = ProductDimension().build(items)
    dimension = ItemDimension()

    dim = dimension.build(items, products)

    assert dim.columns == ['item_id', 'product_id', 'item_name', 'item_variant', 'price']
    assert dim['item_name'].to_list() == ['Bag', 'Tee', 'Tee']
    assert dim['item_variant'].to_list() == ['(not set)', 'LG', 'MD']
    assert dim['item_id'].to_list() == [0, 1, 2]
    assert dim['product_id'].to_list() == [0, 1, 1]
    assert dim.filter(pl.col('item_variant') == 'MD')['price'][0] == 15.0

    keyed = dimension.attach_key(items, dim)
    assert keyed['item_id'].to_list() == [2, 1, 2, 0, None]


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

    products = ProductDimension().build(items)
    dim = ItemDimension().build(items, products)

    assert dim["item_name"].to_list() == ["A"]
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
            "item_variant": [None, "S", "S", None],
            "item_brand": [None, "b", "b", "b"],
            "item_category": [None, "c", "c", "c"],
            "price": [1.0, 1.0, 1.0, 2.0],
        }
    )

    products = ProductDimension().build(items)
    item_dimension = ItemDimension().build(items, products)
    result = TransactionDimension().build(events, items, item_dimension)

    bought = result.transaction_items.join(item_dimension, on="item_id")
    assert bought.select("item_name", "item_variant").rows() == [("A", "S"), ("B", "(not set)")]
    assert result.transaction_items.columns == ["transaction_id", "item_id"]
