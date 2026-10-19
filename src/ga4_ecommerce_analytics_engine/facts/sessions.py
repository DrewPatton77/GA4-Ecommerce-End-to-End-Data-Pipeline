
from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import drop_present, to_date_id
from ga4_ecommerce_analytics_engine.schema import DataSchema


class SessionFacts(DataSchema):
    @property
    def dropped_columns(self) -> tuple[str, ...]:
        return (self.source_utm, self.medium_utm, self.campaign_utm, self.channel, self.session_date)

    def build(self, sessions: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(sessions, required_columns={self.user_id, self.session_id, self.session_date})
        facts = sessions.with_columns(to_date_id(self.session_date).alias(self.date_id))
        return drop_present(facts, self.dropped_columns)
