"""Item-funnel facts: for each item in each session, how far down the funnel did it get?"""

from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import add_id, to_date_id
from ga4_ecommerce_analytics_engine.schema import DataSchema


class ItemFunnelFacts(DataSchema):
    def build(self, items: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            items,
            required_columns={
                self.user_id, self.session_id, self.event_type, self.item_id, self.item_value, self.item_quantity,
            },
        )
        if self.date_id not in items.columns:
            self.check_required_columns(items, required_columns={self.event_date})
            items = items.with_columns(to_date_id(self.event_date).alias(self.date_id))

        event = pl.col(self.event_type)
        funnel = (
            items.group_by([self.user_id, self.session_id, self.date_id, self.item_id], maintain_order=True)
            .agg(
                event.is_in([self.select_item, self.view_item]).any().cast(pl.Int8).alias(self.is_viewed),
                event.eq(self.add_to_cart).any().cast(pl.Int8).alias(self.is_added_to_cart),
                event.eq(self.begin_checkout).any().cast(pl.Int8).alias(self.is_checked_out),
                event.eq(self.conversion).any().cast(pl.Int8).alias(self.is_purchased),
                pl.col(self.item_value).sum().alias(self.revenue),
                pl.col(self.item_quantity).filter(event == self.conversion).sum().alias(self.item_quantity),
            )
            .filter(pl.col(self.item_id) != self.not_set)
            .rename({self.item_id: self.item_key})
        )
        return add_id(self._backfill(funnel), self.item_funnel_id)

    def _backfill(self, funnel: pl.DataFrame) -> pl.DataFrame:
        """Make the funnel strictly linear: a purchase implies checkout, cart and view; and so on up."""
        purchased = pl.col(self.is_purchased) == 1
        checked_out = purchased | (pl.col(self.is_checked_out) == 1)
        carted = checked_out | (pl.col(self.is_added_to_cart) == 1)
        viewed = carted | (pl.col(self.is_viewed) == 1)
        return funnel.with_columns(
            viewed.cast(pl.Int8).alias(self.is_viewed),
            carted.cast(pl.Int8).alias(self.is_added_to_cart),
            checked_out.cast(pl.Int8).alias(self.is_checked_out),
        )
