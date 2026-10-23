'''
Item dimension (one row per item) and the transaction dimension with its item bridge.

Product dimension (one row per product).
'''

from __future__ import annotations

from typing import NamedTuple

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema

MISSING_LABELS = ["", '(not set)', 'not set', '--', '-', '(none)', 'n/a']

def clean_label(column: str) -> pl.Expr:
    text = pl.col(column).cast(pl.Utf8).str.strip_chars()
    return pl.when(text.str.to_lowercase().is_in(MISSING_LABELS)).then(None).otherwise(text)


class ProductDimension(DataSchema):
    def build(self, items: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(items, required_columns={self.item_id, self.item_brand, self.item_category})
        known = items.filter(pl.col(self.item_id).is_not_null() & (pl.col(self.item_id).ne(self.not_set)))
        return (
            known.group_by(self.item_id)
            .agg(
                self._most_common(self.item_brand).fill_null(self.unbranded).alias('brand'),
                self._most_common(self.item_category).fill_null(self.uncategorized).alias('category'),
            )
            .sort(self.item_id)
            .with_row_index(self.product_key)
            .with_columns(pl.col(self.product_key).cast(pl.Int64))
        )

    def attach_key(self, df: pl.DataFrame, dimension: pl.DataFrame) -> pl.DataFrame:
        return df.join(dimension.select(self.product_key, self.item_id), on=self.item_id, how='left')

    @staticmethod
    def _most_common(column: str) -> pl.Expr:
        return clean_label(column).drop_nulls().mode().sort().first()

class ItemDimension(DataSchema):

    def normalize_variant(self, items: pl.DataFrame) -> pl.DataFrame:
        variant = pl.col(self.item_variant).cast(pl.Utf8).str.strip_chars()
        return items.with_columns(
            pl.when(variant.is_null() | (variant == "")).then(pl.lit(self.not_set)).otherwise(variant).alias(self.item_variant)
        )

    def build(self, items: pl.DataFrame, products: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            items,
            required_columns={self.item_id, self.item_variant, self.item_price},
        )
        known = self.normalize_variant(
            items.filter(pl.col(self.item_id).is_not_null() & (pl.col(self.item_id) != self.not_set))
        )
        return (
            known.group_by([self.item_id, self.item_variant])
            .agg(pl.col(self.item_price).max().alias('price'))
            .sort([self.item_id, self.item_variant])
            .with_row_index(self.item_key)
            .with_columns(pl.col(self.item_key).cast(pl.Int64))
            .join(products.select(self.product_key, self.item_id), on=self.item_id, how='left')
            .select(self.item_key, self.product_key, self.item_id, self.item_variant, 'price')
        )
    
    def attach_key(self, df: pl.DataFrame, dimension: pl.DataFrame) -> pl.DataFrame:
        lookup = dimension.select(self.item_key, self.item_id, self.item_variant)
        return self.normalize_variant(df).join(lookup, on=[self.item_id, self.item_variant], how='left')


class TransactionResult(NamedTuple):
    transactions: pl.DataFrame
    transaction_items: pl.DataFrame  # transaction <-> item


class TransactionDimension(DataSchema):
    def build(self, events: pl.DataFrame, items: pl.DataFrame, item_dimension: pl.DataFrame) -> TransactionResult:
        self.check_required_columns(
            events,
            required_columns={
                self.event_type, self.transaction_id, self.conversion_timestamp,
                self.basket_size, self.event_value, self.unique_items,
            },
        )
        self.check_required_columns(items, required_columns={self.event_type, self.transaction_id, self.item_id, self.item_variant})

        transactions = events.filter(pl.col(self.event_type) == self.conversion).select(
            self.transaction_id, self.conversion_timestamp, self.basket_size, self.event_value, self.unique_items
        )
        purchases = items.filter(pl.col(self.event_type).eq(self.conversion)).select(
            self.transaction_id, self.item_id, self.item_variant
        )
        transaction_items = (
            ItemDimension().attach_key(purchases, item_dimension)
            .filter(pl.col(self.item_key).is_not_null())
            .select(self.transaction_id, self.item_key)
            .unique(maintain_order=True)
        )
        return TransactionResult(transactions, transaction_items)
