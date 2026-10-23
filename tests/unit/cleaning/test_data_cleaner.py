'''
Tests for transactions.DataCleaner()
'''

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.cleaning.transactions import DataCleaner

EPOCH = dt.datetime(1970, 1, 1)
T0 = dt.datetime(2020, 12, 1, 9, 0, 0)
T1 = dt.datetime(2020, 12, 1, 9, 5, 0)
T2 = dt.datetime(2020, 12, 1, 9, 10, 0)
DAY = dt.date(2020, 12, 1)

def micros(timestamp: dt.datetime) -> int:
    return (timestamp - EPOCH) // dt.timedelta(microseconds=1)

EVENT_SCHEMA = {
    'user_pseudo_id': pl.Utf8,
    'session_id': pl.Int64,
    'event_timestamp_micros': pl.Datetime,
    'event_name': pl.Utf8,
    'event_date' : pl.Date,
}

ITEM_SCHEMA = {
    'user_pseudo_id': pl.Utf8,
    'session_id': pl.Int64,
    'event_timestamp_micros': pl.Datetime,
    'event_name': pl.Utf8,
    'item_name': pl.Utf8,
    'item_variant': pl.Utf8,
    'item_revenue': pl.Float64,
    'quantity': pl.Int64,
    'transaction_id': pl.Utf8,
    'event_date': pl.Date,
}


def make_events() -> pl.DataFrame:

    rows = [
        ('u1', 1, T0, 'page_view', DAY),
        ('u1', 1, T2, 'purchase', DAY),
        ('u2', 5, T1, 'page_view', DAY),
    ]
    return pl.DataFrame(rows, schema=EVENT_SCHEMA, orient='row')

def make_items() -> pl.DataFrame:
    rows = [
        # (user, session, ts, event, name, variant, revenue, qty, txn, date)
        ('u1', 1, T0, 'view_item', 'A', None,   None,  None, None, DAY),
        ('u1', 1, T2, 'purchase',  'A', 'red',  10.0,  1,    'x1', DAY),
        ('u1', 1, T2, 'purchase',  'B', None,   30.0,  2,    None, DAY),
        ('u1', 1, T2, 'purchase',  'A', 'red',  10.0,  1,    'x1', DAY),   # dup of row 2
        ('u1', 1, T2, 'purchase',  'C', None,   None,  1,    None, DAY),
    ]
    return pl.DataFrame(rows, schema=ITEM_SCHEMA, orient='row')

def purchase_rows(df: pl.DataFrame, event_col: str = 'event_name', value: str = 'purchase') -> pl.DataFrame:
    return df.filter(pl.col(event_col) == value)

@pytest.fixture
def cleaned():      
    return DataCleaner().clean_transactions(make_events(), make_items(), composition_key=True)

# --- Full pipeline ------------------------------------------------

def test_events_are_cleaned(cleaned):
    events = cleaned.events

    # Session ids are combined, and the raw purchases is replaced by one aggregated event.
    assert set(events['session_id']) == {'u1-1', 'u2-5'}
    assert events.height == 3
    purchase = purchase_rows(events).row(0, named=True)
    assert purchase_rows(events).height == 1
    assert purchase['event_value'] == 40.0 
    assert purchase['basket_size'] == 3
    assert purchase['unique_items'] == 2
    assert purchase['transaction_id'] == f"u1-1-{micros(T2)}"
    assert purchase['conversion_timestamp'] == T2

    assert events['user_pseudo_id'].to_list() == ['u1', 'u1', 'u2']
    assert events['event_timestamp_micros'].to_list()[:2] == [T0, T2]
    others = events.filter(pl.col('event_name') != 'purchase')
    assert others['conversion_timestamp'].null_count() == others.height

def test_items_are_cleaned(cleaned):
    items = cleaned.items
    purchases = purchase_rows(items)
   
    assert set(items['session_id']) == {'u1-1'}
    assert items.height == 3
    assert sorted(purchases['item_name'].to_list()) == ['A', 'B']
    event_transaction = purchase_rows(cleaned.events)['transaction_id'][0]
    assert set(purchases['transaction_id']) == {event_transaction}

def test_integer_microsecond_timestamps_give_the_same_result(cleaned):
    def to_micros(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(pl.col('event_timestamp_micros').dt.epoch('us'))

    result = DataCleaner().clean_transactions(
        to_micros(make_events()), to_micros(make_items()), composition_key=True
    )

    assert result.events.equals(cleaned.events)
    assert result.items.equals(cleaned.items)

def test_data_with_no_purchases_passes_through():
    events = make_events().filter(pl.col('event_name') != 'purchase')
    items = make_items().filter(pl.col('event_name') != 'purchase')

    result = DataCleaner().clean_transactions(events, items, composition_key=True)

    assert result.events.height == events.height
    assert result.items.height == items.height
    assert result.events['conversion_timestamp'].null_count() == events.height

def test_custom_column_names_work_end_to_end():
    renames = {
        'user_pseudo_id': 'uid',
        'session_id': 'sid',
        'event_timestamp_micros': 'ts',
        'event_name': 'evt',
        'item_name': 'product',
        'item_revenue': 'revenue',
        'quantity': 'qty',
        'transaction_id': 'txn'
    }

    def rename(df: pl.DataFrame) -> pl.DataFrame:
        df = df.rename({old: new for old, new in renames.items() if old in df.columns})
        return df.with_columns(pl.col('evt').replace({'purchase': 'buy'}))

    custom = DataCleaner(
        timestamp = 'ts',
        user_id = 'uid',
        session_id = 'sid',
        item_id = 'product',
        transaction_id = 'txn',
        event_type = 'evt',
        conversion = 'buy',
        item_value = 'revenue',
        item_quantity = 'qty'
    )

    result = custom.clean_transactions(rename(make_events()), rename(make_items()), composition_key=True)

    purchases = purchase_rows(result.events, event_col='evt', value='buy')
    assert purchases.height == 1
    assert purchases['event_value'][0] == 40.0
    assert purchases['txn'][0] == f'u1-1-{micros(T2)}'

# --- Individual steps --------------------------------------

def test_missing_item_column_raises_a_readable_error():
    with pytest.raises(KeyError, match='quantity'):
        DataCleaner().clean_transactions(make_events(), make_items().drop('quantity'))

def test_composite_session_id_is_safe_to_apply_twice():
    cleaner = DataCleaner()

    once = cleaner.add_composite_session_id(make_events())
    twice = cleaner.add_composite_session_id(once)

    assert once['session_id'].to_list() == ['u1-1', 'u1-1', 'u2-5']
    assert twice.equals(once)

def test_deduplicate_keeps_the_first_row_but_not_rows_from_another_transaction():
    df = pl.DataFrame(
        {
            'user_pseudo_id': ['u', 'u', 'u'],
            'session_id': ['u-1', 'u-1', 'u-1'],
            'transaction_id': ['t1', 't1', 't2'],
            'item_name': ['A', 'A', 'A'],
            'item_variant': ['red', 'red', 'red'],
            'item_revenue': [1.0, 2.0, 3.0],
        }
    )

    result = DataCleaner().deduplicate_items(df)

    assert result['item_revenue'].to_list() == [2.0, 3.0]

