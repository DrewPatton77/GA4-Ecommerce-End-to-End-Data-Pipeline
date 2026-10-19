'''
Date dimension, one row per distinct event date.
'''

from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema


class DateDimension(DataSchema):
    def build(self, events: pl.DataFrame) -> pl.DataFrame:
        '''
        The calendar columns below are this dimension's own vocabulary; only the date and key come from the schema.
        '''
        self.check_required_columns(events, required_columns={self.event_date})
        date = self.event_date
        return (
            events.select(date)
            .unique()
            .sort(date)
            .with_columns(
                pl.col(date).dt.strftime("%Y%m%d").cast(pl.Int32).alias(self.date_id),
                pl.col(date).dt.year().alias("year"),
                pl.col(date).dt.quarter().alias("quarter"),
                pl.col(date).dt.month().alias("month"),
                pl.col(date).dt.strftime("%B").alias("month_name"),
                pl.col(date).dt.day().alias("day"),
                pl.col(date).dt.weekday().alias("day_of_week"),  # Monday = 1 ... Sunday = 7
                pl.col(date).dt.strftime("%A").alias("day_name"),
                pl.col(date).dt.weekday().is_in([6, 7]).alias("is_weekend"),
            )
            .rename({date: "datetime"})
            .select(self.date_id, pl.exclude(self.date_id))
        )
