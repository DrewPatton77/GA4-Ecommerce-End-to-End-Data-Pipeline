'''
Abstract interface every data source implements (BigQuery CSV, ...).
'''

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

import polars as pl

from ga4_ecommerce_analytics_engine.sources.raw_data import RawData

DateLike = str | date | datetime


class BaseSource(ABC):
    '''
    A source knows how to fetch the three raw tables for a date range.
    '''

    @abstractmethod
    def fetch_events(self, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        '''
        Raw events, one row per event.
        '''

    @abstractmethod
    def fetch_items(self, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        '''
        Raw item events, one row per item per event.
        '''

    @abstractmethod
    def fetch_dimensions(self, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        '''
        Raw dimension attributes (geo, device, ...).
        '''

    def fetch_all(self, start_date: DateLike, end_date: DateLike) -> RawData:
        '''
        Fetch all three tables. Shared by every source.
        '''
        return RawData(
            events = self.fetch_events(start_date, end_date),
            items=self.fetch_items(start_date, end_date),
            dimensions=self.fetch_dimensions(start_date, end_date)
        )