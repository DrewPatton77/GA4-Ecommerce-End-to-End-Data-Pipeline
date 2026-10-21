
from __future__ import annotations

from typing import NamedTuple

import polars as pl

#from ga4_ecommerce_analytics_engine.utils.binning import transform_log_bin
from ga4_ecommerce_analytics_engine.utils.paths import PATH_SEPARATOR
from ga4_ecommerce_analytics_engine.schema import DataSchema

MICROS_PER_HOUR = 3_600_000_000

class JourneyResult(NamedTuple):
    journeys: pl.DataFrame
    converting: pl.DataFrame

class JourneyBuilder(DataSchema):

    def __init__(
        self,
        n_duration_bins: int = 20,
        n_value_bins: int = 20,
        separator: str = PATH_SEPARATOR,
    ) -> None:
        self.n_duration_bins = n_duration_bins
        self.n_value_bins = n_value_bins
        self.separator = separator

    def build(self, sessions: pl.DataFrame) -> JourneyResult:
        self.check_required_columns(
            sessions,
            required_columns={self.user_id, self.session_date, self.session_start_timestamp, self.channel, self.converted, self.session_value}
        )
        journeys = self.build_all_journeys(sessions)
        return JourneyResult(journeys, self.build_converting_journeys(journeys))

    def build_all_journeys(self, sessions: pl.DataFrame) -> pl.DataFrame:

        ordered = (
            sessions.select((self.user_id, self.session_start_timestamp, self.session_date, self.channel, self.converted, self.session_value, self.channel_group))
            .sort([self.user_id, self.session_start_timestamp], maintain_order=True)
            .with_columns(
                (
                    (pl.col(self.session_start_timestamp).max().over(self.user_id) - pl.col(self.session_start_timestamp))
                    .dt.total_microseconds() / MICROS_PER_HOUR
                ).alias(self.hours_before_conversion)
            )
        )

        journeys = ordered.group_by(self.user_id, maintain_order=True).agg(
            pl.col(self.channel).alias(self.conversion_path),
            pl.col(self.channel).unique().sort().alias(self.channel_set),
            pl.col(self.channel_group).alias(self.channel_group_list),
            pl.col(self.session_date).first().alias(self.journey_start_timestamp),
            pl.col(self.session_date).last().alias(self.journey_end_timestamp),
            pl.col(self.session_start_timestamp).alias(self.timestamp_path),
            pl.col(self.converted).sum().alias(self.conversion_count),   
            pl.col(self.session_value).sum().alias(self.conversion_value),
            pl.col(self.hours_before_conversion),
            pl.len().cast(pl.Int64).alias(self.touchpoints),
        )

        journeys = journeys.with_columns(
            pl.col(self.conversion_count).gt(0).alias(self.has_conversion),
            pl.col(self.hours_before_conversion).list.first().alias(self.journey_duration),
            #pl.len().over(self.touchpoints).cast(pl.Int64).alias(self.touchpoint_count),
        )
        return journeys #transform_log_bin(
        #    journeys, self.journey_duration, self.journey_duration, n_bins=self.n_duration_bins, format='timestamp'
        #)

    def build_converting_journeys(self, journeys: pl.DataFrame) -> pl.DataFrame:
        converting = journeys.filter(pl.col(self.has_conversion)).with_columns(
            pl.col(self.hours_before_conversion)
            .list.eval(pl.element().round(0).cast(pl.Int32).cast(pl.Utf8))
            .list.join(self.separator)
            .alias(self.hours_path),
            pl.col(self.channel_group_list).list.join(self.separator).alias(self.channel_group_path),
            pl.col(self.conversion_path).list.join(self.separator).alias(self.path_to_conversion),
            pl.when(pl.col(self.conversion_value).eq(0))
            .then(None)
            .otherwise(pl.col(self.conversion_value))
            .alias(self.conversion_value)
        )
        return converting #transform_log_bin(
            #converting,
            #self.conversion_value,
            #'value',
            #n_bins=self.n_value_bins,
            #format='value'
        #)
        