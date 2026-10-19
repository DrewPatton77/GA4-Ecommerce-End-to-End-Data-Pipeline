"""User facts: one lifetime row per user, rolled up from the sessions table."""

from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import to_date_id
from ga4_ecommerce_analytics_engine.schema import DataSchema


class UserFacts(DataSchema):
    def build(self, sessions: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            sessions,
            required_columns={
                self.user_id, self.session_start_timestamp, self.session_date, self.page_views,
                self.session_engaged, self.session_engagement_time, self.session_number, self.event_count,
                self.converted, self.conversions_in_session, self.session_value, self.item_quantity,
            },
        )

        return (
            sessions.sort([self.user_id, self.session_start_timestamp], maintain_order=True)
            .group_by(self.user_id, maintain_order=True)
            .agg(
                pl.col(self.session_date).first().alias(self.first_active_date),
                pl.col(self.session_date).last().alias(self.last_active_date),
                pl.col(self.page_views).sum().alias(self.total_pageviews),
                pl.col(self.session_engaged).sum().alias(self.total_engaged_sessions),
                pl.col(self.session_engagement_time).sum().alias(self.total_engagement_time),
                pl.col(self.session_number).max().alias(self.total_sessions),
                pl.col(self.event_count).sum().alias(self.total_lifetime_events),
                pl.col(self.session_value).sum().alias(self.lifetime_revenue),
                pl.col(self.conversions_in_session).sum().alias(self.total_purchases),
                pl.col(self.item_quantity).sum().alias(self.total_items_purchased),
                pl.col(self.converted).sum().alias(self.total_conversions),
                (pl.col(self.converted).sum() > 0).cast(pl.Int8).alias(self.converted),
            )
            .with_columns(
                to_date_id(self.first_active_date).alias(self.first_active_date),
                to_date_id(self.last_active_date).alias(self.last_active_date),
                (pl.col(self.total_conversions) > 1).cast(pl.Int8).alias(self.repeat),
            )
        )
