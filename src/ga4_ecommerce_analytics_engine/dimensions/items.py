'''
Item dimension (one row per item) and the transaction dimension with its item bridge.
'''

from __future__ import annotations

from typing import NamedTuple

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema


class ItemDimension(DataSchema):
    def build(self, items: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            items,
            required_columns={self.item_id, self.item_brand, self.item_variant, self.item_category, self.item_price},
        )
        return (
            items.filter(pl.col(self.item_id) != self.not_set)
            .group_by(self.item_id, maintain_order=True)
            .agg(
                pl.col(self.item_brand).first().alias("brand"),
                pl.col(self.item_variant).first().alias("variant"),
                pl.col(self.item_category).first().alias("category"),
                pl.col(self.item_price).max().alias("price"),
            )
            .rename({self.item_id: self.item_key})
        )


class TransactionResult(NamedTuple):
    transactions: pl.DataFrame
    transaction_items: pl.DataFrame  # transaction <-> item


class TransactionDimension(DataSchema):
    def build(self, events: pl.DataFrame, items: pl.DataFrame) -> TransactionResult:
        self.check_required_columns(
            events,
            required_columns={
                self.event_type, self.transaction_id, self.conversion_timestamp,
                self.basket_size, self.event_value, self.unique_items,
            },
        )
        self.check_required_columns(items, required_columns={self.event_type, self.transaction_id, self.item_id})

        transactions = events.filter(pl.col(self.event_type) == self.conversion).select(
            self.transaction_id, self.conversion_timestamp, self.basket_size, self.event_value, self.unique_items
        )
        transaction_items = (
            items.filter(pl.col(self.event_type) == self.conversion)
            .select(self.transaction_id, self.item_id)
            .unique(maintain_order=True)
        )
        return TransactionResult(transactions, transaction_items)
