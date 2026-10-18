
from __future__ import annotations

import logging

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema


logger = logging.getLogger(__name__)

class SessionBuilder(DataSchema):

    @property
    def funnel_events(self):
        return {
            self.page_views: self.page_view,
            self.item_views: self.view_item,
            self.carts: self.add_to_cart,
            self.checkouts: self.begin_checkout
        }

    def build(self, events: pl.DataFrame, session_channels: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            events, 
            required_values={self.page_view, self.view_item, self.add_to_cart, self.begin_checkout, self.conversion},
            required_columns={
                self.user_id,
                self.session_id,
                self.timestamp,
                self.event_type,
                self.event_date,
                self.session_number,
                self.engagement_time,
                self.session_engaged,
                self.basket_size,
                self.event_value,
                self.conversion_timestamp
            },
        )

        sessions = self.aggregate_events(events)
        sessions = self.join_channels(sessions, session_channels)
        sessions = sessions.join(self.aggregate_conversions(events), on=self.session_id, how='left')
        return self.finalize_flags(sessions)

    def aggregate_events(self, events: pl.DataFrame) -> pl.DataFrame:
        funnel_counts = [
            pl.col(self.event_type).eq(event_name).sum().cast(pl.Int64).alias(column)
            for column, event_name in self.funnel_events.items()
        ]
        return (
            events.sort([self.user_id, self.session_id, self.timestamp], maintain_order=True)
            .group_by(self.user_id, self.session_id, maintain_order=True)
            .agg(
                *funnel_counts,
                pl.col(self.timestamp).first().alias(self.session_start_timestamp),
                pl.col(self.event_date).first().alias(self.session_date),
                pl.col(self.session_number).max().alias(self.session_number),
                pl.col(self.engagement_time).sum().alias(self.session_engagement_time),
                pl.col(self.session_engaged).cast(pl.Int8, strict=False).max().alias(self.session_engaged),
                pl.len().cast(pl.Int64).alias(self.event_count),
            )
        )

    def aggregate_conversions(self, events: pl.DataFrame) -> pl.DataFrame:
        return (
            events.filter(pl.col(self.event_type).eq(self.conversion))
            .sort([self.session_id, self.conversion_timestamp], maintain_order=True)
            .group_by(self.session_id, maintain_order=True)
            .agg(
                pl.col(self.conversion_timestamp).first(),
                pl.col(self.event_value).sum().alias(self.session_value),
                pl.col(self.basket_size).sum().alias(self.item_quantity),
                pl.col(self.event_value).count().alias(self.conversions_in_session),
            )
        )

    def join_channels(self, sessions: pl.DataFrame, session_channels: pl.DataFrame) -> pl.DataFrame:
        if self.channel not in session_channels.columns:
            raise ValueError("'session_channels' requires the column 'channel'")
        if session_channels.select(self.session_id).is_duplicated().any():
            raise ValueError(f"'session_channels' has duplicate '{self.session_id}' rows.")
        return sessions.join(session_channels, on=self.session_id, how='left')

    def finalize_flags(self, sessions: pl.DataFrame) -> pl.DataFrame:
        return sessions.with_columns(
            pl.col(self.conversions_in_session).gt(0).fill_null(False).cast(pl.Int8).alias(self.converted)
        )