
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
            self.session_start_event,
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
        '''
        One row per session, with the UTM parameters resolved from the session's
        initialization event (session_start or first_visit).

        Sessions where no event carries UTM parameters get null source_utm,
        medium_utm, and campaign_utm — the "unknown / direct" case.

        Requires: session_start event in the input. first_visit is preferred when present.
        '''
        self.check_required_columns(
            cleaned_events,
            required_values = {self.session_start_event},
            required_columns= {self.user_id, self.session_id, self.source, 
                               self.medium, self.campaign, self.timestamp, 
                               self.event_type}
            )

        ranked = cleaned_events.with_columns(
            pl.col(self.event_type).is_in(self.init_events).cast(pl.Boolean).alias('_is_initialization'),
            pl.col(self.source).is_null().cast(pl.Boolean).alias('_source_is_null'),
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

    def resolve(self, cleaned_events: pl.DataFrame) -> UtmResult:
        '''
        Returns: events with UTM columns, plus the per-session summary
        '''
        sessions_without_start = (
        cleaned_events
        .group_by(self.session_id)
        .agg(pl.col(self.event_type).is_in({self.session_start_event}).any().alias("has_start"))
        .filter(~pl.col("has_start"))
        .height
    )
        if sessions_without_start:
            logger.warning("%d sessions have no session_start event", sessions_without_start)   
            
        utm_outputs = {self.source_utm, self.medium_utm, self.campaign_utm}
        existing = utm_outputs & set(cleaned_events.columns)
        if existing:
            raise ValueError(
                f"Input already has UTM columns: {sorted(existing)}. "
                f"Enrichment is not idempotent; drop them first or skip this step."
            )
        
        session_utm = self.resolve_session_utm(cleaned_events)
        return UtmResult(
            events = self.attach_utm_to_events(cleaned_events, session_utm),
            sessions = session_utm
        )


