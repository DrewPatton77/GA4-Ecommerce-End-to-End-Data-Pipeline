
from __future__ import annotations

from typing import NamedTuple

import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import add_id, drop_present, to_date_id
from ga4_ecommerce_analytics_engine.schema import DataSchema


class JourneyFactsResult(NamedTuple):
    journeys: pl.DataFrame
    converting: pl.DataFrame


class JourneyFacts(DataSchema):
    @property
    def dropped_columns(self) -> tuple[str, ...]:
        return (self.conversion_path, self.channel_set, self.timestamp_path, self.hours_before_conversion)

    def build(self, journeys: pl.DataFrame, converting: pl.DataFrame) -> JourneyFactsResult:
        return JourneyFactsResult(
            self._prepare(journeys, self.journey_id),
            self._prepare(converting, self.converting_journey_id),
        )

    def _prepare(self, df: pl.DataFrame, id_name: str) -> pl.DataFrame:
        self.check_required_columns(
            df, required_columns={self.user_id, self.journey_start_timestamp, self.journey_end_timestamp}
        )
        # Each table converts ITS OWN dates. (The legacy code took the converting table's start dates
        # from the all-journeys table, which lined up the wrong users.)
        df = df.with_columns(
            to_date_id(self.journey_start_timestamp).alias(self.journey_start_timestamp),
            to_date_id(self.journey_end_timestamp).alias(self.journey_end_timestamp),
        )
        return drop_present(add_id(df, id_name), self.dropped_columns)
