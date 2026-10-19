'''
Event facts and the event <-> item bridge.

Both need the SAME event id, so give the events their ids once:

    event_facts = EventFacts()
    events = event_facts.add_event_ids(events)        # id = row position in the cleaned events
    facts = event_facts.build(events)
    bridge = EventItemBridge().build(events, items)
'''

from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import add_id, drop_present, to_date_id
from ga4_ecommerce_analytics_engine.schema import DataSchema


class EventFacts(DataSchema):
    @property
    def dropped_columns(self) -> tuple[str, ...]:
        '''
        Columns that live in dimensions or other facts rather than on every event row
        '''
        return (
            self.transaction_id, self.country, self.device, self.event_date,
            self.source_utm, self.medium_utm, self.campaign_utm,
            self.source, self.medium, self.campaign,
        )

    def add_event_ids(self, events: pl.DataFrame) -> pl.DataFrame:
        return add_id(events, self.event_id)

    def build(self, events: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            events,
            required_columns={self.event_id, self.user_id, self.timestamp, self.event_date, self.session_engaged},
        )
        facts = events.with_columns(
            to_date_id(self.event_date).alias(self.date_id),
            pl.col(self.session_engaged).cast(pl.Int8, strict=False),
        )
        return drop_present(facts, self.dropped_columns).sort([self.user_id, self.timestamp], maintain_order=True)


class EventItemBridge(DataSchema):
    '''
    One row per (event, item) pair, so events and items can be joined many-to-many
    '''

    def build(self, events: pl.DataFrame, items: pl.DataFrame) -> pl.DataFrame:
        keys = [self.user_id, self.session_id, self.timestamp, self.event_type]
        self.check_required_columns(events, required_columns={self.event_id, *keys})
        self.check_required_columns(items, required_columns={*keys, self.item_id})

        return (
            events.select(self.event_id, *keys)
            .join(items.select(*keys, self.item_id), on=keys, how="inner")
            .filter(pl.col(self.item_id).is_not_null() & (pl.col(self.item_id) != self.not_set))
            .select(self.event_id, pl.col(self.item_id).alias(self.item_key))
            .sort(self.event_id, maintain_order=True)
        )
