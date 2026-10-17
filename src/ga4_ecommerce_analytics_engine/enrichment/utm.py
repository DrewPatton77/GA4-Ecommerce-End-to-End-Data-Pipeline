
from __future__ import annotations

from typing import NamedTuple
import logging

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema

logger = logging.getLogger(__name__)


class UtmResult(NamedTuple):
    events: pl.DataFrame # every event with sources
    sessions: pl.DataFrame # one row per session with sources


class DataUtm(DataSchema):

    @property
    def init_events(self) -> list[str]:
        return [
            self.session_start,
            self.first_visit
        ]

    @property
    def source_cols(self) -> list[str]:
        return [
            self.source,
            self.medium,
            self.campaign,
        ]

    def resolve_session_utm(self, cleaned_events: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            cleaned_events,
            required_values = {self.session_start, self.first_visit},
            required_columns= {self.user_id, self.session_id, self.source, self.medium, self.campaign}
            )

        ranked = cleaned_events.with_columns(
            pl.col(self.event_type).is_in(self.init_events).cast(pl.Int8).alias('_is_initialization'),
            pl.col(self.source).is_null().cast(pl.Int8).alias('_source_is_null'),
        ).sort(
            [self.session_id, "_is_initialization", "_source_is_null", self.timestamp],
            maintain_order=True,
        )

        return ranked.group_by(self.session_id, maintain_order=True).agg(
            pl.col(self.source).drop_nulls().first().alias(self.source_utm),
            pl.col(self.medium).drop_nulls().first().alias(self.medium_utm),
            pl.col(self.campaign).drop_nulls().first().alias(self.campaign_utm)
        )

    def attach_utm_to_events(self, cleaned_events: pl.DataFrame, session_utm: pl.DataFrame) -> pl.DataFrame:
        return cleaned_events.join(session_utm, on=self.session_id, how='left').sort(
            [self.session_id, self.timestamp], maintain_order=True
        )

    # Bring this to its own Enrich class in another file.
    def enrich_events_with_utm(self, cleaned_events: pl.DataFrame) -> UtmResult:
        session_utm = self.resolve_session_utm(cleaned_events)
        return UtmResult(
            events = self.attach_utm_to_events(cleaned_events, session_utm),
            sessions = session_utm
        )


