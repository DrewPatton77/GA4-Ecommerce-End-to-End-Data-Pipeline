'''
Tests for base.py (BaseSource) and raw_data.py (RawData).

Checks that the abstract class can't be created, a subclass missing a 
method fails immediately, and that `fetch_all` returns `RawData`.
'''

from __future__ import annotations

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.sources.base import BaseSource
from ga4_ecommerce_analytics_engine.sources.raw_data import RawData

class DummySource(BaseSource):
    '''
    A minimal complete source that records how it was called.
    '''

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def _frame(self, name, start, end) -> pl.DataFrame:
        self.calls.append((name, start, end))
        return pl.DataFrame({"table": [name]})

    def fetch_events(self, start_date, end_date):
        return self._frame('events', start_date, end_date)

    def fetch_items(self, start_date, end_date):
        return self._frame('items', start_date, end_date)

    def fetch_dimensions(self, start_date, end_date):
        return self._frame('dimensions', start_date, end_date)


def test_abstract_class_cannot_be_created_directly():
    with pytest.raises(TypeError):
        BaseSource()


def test_subclass_missing_a_method_cannot_be_created():
    class Incomplete(BaseSource):
        def fetch_events(self, start_date, end_date): ...

        def fetch_items(self, start_date, end_date): ...

        # fetch_dimension is missing

    with pytest.raises(TypeError):
        Incomplete()


def test_complete_subclass_can_be_created():
    assert isinstance(DummySource(), BaseSource)

def test_fetch_all_returns_raw_data_with_all_three_tables():
    source = DummySource()

    raw = source.fetch_all("2020-12-01", "2020-12-03")

    assert isinstance(raw, RawData)
    assert raw.events["table"][0] == 'events'
    assert raw.items['table'][0] == 'items'
    assert raw.dimensions['table'][0] == 'dimensions'

def test_fetch_all_passes_the_date_range_to_every_fetch():
    source = DummySource()

    source.fetch_all('2020-12-01', '2020-12-03')

    assert source.calls == [
        ('events', '2020-12-01', '2020-12-03'),
        ('items', '2020-12-01', '2020-12-03'),
        ('dimensions', '2020-12-01', '2020-12-03'),
    ]
