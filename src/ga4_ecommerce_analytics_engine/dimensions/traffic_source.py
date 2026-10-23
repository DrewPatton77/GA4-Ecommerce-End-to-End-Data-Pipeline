
from __future__ import annotations

from typing import NamedTuple

import polars as pl

from ga4_ecommerce_analytics_engine.dimensions.base import BaseDimension
from ga4_ecommerce_analytics_engine.enrichment.channel_groups import CHANNEL_GROUPS


class TrafficSourceResult(NamedTuple):
    dimension: pl.DataFrame
    session_mapping: pl.DataFrame  # session -> traffic source key
    user_mapping: pl.DataFrame  # user -> traffic source key (their first session's source)


class TrafficSourceDimension(BaseDimension):
    @property
    def key(self) -> str:
        return self.traffic_source_id

    @property
    def columns(self) -> tuple[str, ...]:
        return (self.source_utm, self.medium_utm, self.campaign_utm, self.channel, self.channel_group)

    @property
    def keep_case(self) -> tuple[str, ...]:
        return (self.source_utm, self.medium_utm, self.campaign_utm, self.channel, self.channel_group)

    def add_channel_group(self, sessions: pl.DataFrame) -> pl.DataFrame:
        return sessions.with_columns(pl.col(self.channel).replace(CHANNEL_GROUPS).alias(self.channel_group))

    def build_with_mappings(self, sessions: pl.DataFrame) -> TrafficSourceResult:
        self.check_required_columns(
            sessions, required_columns={self.user_id, self.session_id, self.session_start_timestamp, self.channel}
        )
        sessions = self.add_channel_group(sessions)
        dimension = self.build(sessions)
        one_row_per_session = sessions.unique(subset=self.session_id, maintain_order=True)
        session_mapping = self.assign_keys(one_row_per_session, dimension, self.session_id)

        first_sessions = self.first_per_entity(sessions, self.user_id, self.session_start_timestamp)
        user_mapping = self.assign_keys(first_sessions, dimension, self.user_id)
        return TrafficSourceResult(dimension, session_mapping, user_mapping)
