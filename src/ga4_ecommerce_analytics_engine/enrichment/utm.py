
from __future__ import annotations

from typing import NamedTuple
import logging

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema

logger = logging.getLogger(__name__)

INITIALIZATION_EVENTS = ('session_start', 'first_visit')

SOURCE_UTM = 'source_utm'
MEDIUM_UTM = 'medium_utm'
CAMPAIGN_UTM = 'campaign_utm'


class UtmResult(NamedTuple):
    events: pl.DataFrame # every event with sources
    sessions: pl.DataFrame # one row per session with sources


class DataUtm:
    def __init__(self, **config_overrides) -> None:
        config = DataSchema(**config_overrides)

        # required columns
        self.user_id = config.user_id
        self.session_id = config.session_id
        self.timestamp = config.timestamp
        self.event_type = config.event_type
        self.source = config.source
        self.medium = config.medium
        self.campaign = config.campaign

        # required events
        self.session_start = config.session_start
        self.first_visit = config.first_visit


    def _check_required_columns(self, df: pl.DataFrame) -> None:
        '''
        This will fail early and includes a readable message when the extract is missing any columns
        to ensures that the cleaned data matches the required columns config.
        '''
        exclude_key = {self.session_start, self.first_visit}
        
        required_cols = {
            value
            for key, value in vars(self).items()
            if key not in exclude_key and isinstance(value, str)
        }

        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise KeyError(
                f"Pre-cleaning Schema Validation Failed. " 
                f"The following required columns are missing from the events dataset: {missing_cols}"
            )
        logger.info("Schema validation passed. All required columns are in the events dataset.")

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
        self._check_required_columns(cleaned_events)

        ranked = cleaned_events.with_columns(
            pl.col(self.event_type).is_in(self.init_events).cast(pl.Int8).alias('_is_initialization'),
            pl.col(self.source).is_null().cast(pl.Int8).alias('_source_is_null'),
        ).sort(
            [self.session_id, "_is_initialization", "_source_is_null", self.timestamp],
            maintain_order=True,
        )

        return ranked.group_by(self.session_id, maintain_order=True).agg(
            pl.col(self.source).drop_nulls().first().alias('source_utm'),
            pl.col(self.medium).drop_nulls().first().alias('medium_utm'),
            pl.col(self.campaign).drop_nulls().first().alias('campaign_utm')
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


