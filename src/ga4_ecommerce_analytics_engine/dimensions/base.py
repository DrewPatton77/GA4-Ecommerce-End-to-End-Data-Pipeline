'''
Shared machinery for dimension tables.

A dimension is the distinct combinations of some descriptive columns, each given an integer key.
Facts then carry that key instead of the descriptive columns.

    dimension = Dim.build(source)                              # distinct combos + key
    mapping   = Dim.assign_keys(entities, dimension, "user")   # which key does each user / session have?
    facts     = Dim.attach_key(facts, mapping, on="user")

Column names come from the schema (DataSchema), so a subclass only says which schema fields it uses.
'''

from __future__ import annotations

from typing import Sequence

import polars as pl

from ga4_ecommerce_analytics_engine.schema import DataSchema

# Nulls never match in a join, but two sessions with the same missing city should share a key.
_NULL = "\x00null"

# Placeholder values GA4 uses, mapped to one tidy label each (applied after lower-casing).
UNSPECIFIED = 'unspecified'
UNKNOWN_VALUES = {
    '': UNSPECIFIED,
    '(not set)': UNSPECIFIED,
    '<other>': UNSPECIFIED,
    '(none)': UNSPECIFIED,
    '(direct)': 'direct',
    '(organic)': 'organic',
    '(referral)': 'referral',
    '(data deleted)': 'redacted',
}


class BaseDimension(DataSchema):
    @property
    def key(self) -> str:
        '''
        Name of this dimension's id column
        '''
        raise NotImplementedError

    @property
    def columns(self) -> tuple[str, ...]:
        '''
        The descriptive columns that define one row of the dimension
        '''
        raise NotImplementedError

    def build(self, source: pl.DataFrame) -> pl.DataFrame:
        '''
        Distinct combinations of `columns`, with an integer key column first
        '''
        self.check_required_columns(source, required_columns=set(self.columns))
        return (
            self.clean_unknown(source.select(self.columns))  # clean BEFORE de-duplicating, so '(not set)' and '' merge
            .unique(maintain_order=True)
            .with_row_index(self.key)
            .with_columns(pl.col(self.key).cast(pl.Int64))
        )

    def assign_keys(
        self,
        entities: pl.DataFrame,
        dimension: pl.DataFrame,
        entity_cols: str | Sequence[str],
    ) -> pl.DataFrame:
        '''
        Look up each entity's key. `entities` holds `entity_cols` and `columns`, one row per entity
        '''
        entity_cols = [entity_cols] if isinstance(entity_cols, str) else list(entity_cols)
        left = self._null_safe(self.clean_unknown(entities))  # same cleaning as build(), or the keys won't match
        right = self._null_safe(dimension.select(self.key, *self.columns))  # the DIMENSION, not the entities
        return left.join(right, on=list(self.columns), how='left').select(*entity_cols, self.key)

    def clean_unknown(self, df: pl.DataFrame) -> pl.DataFrame:
        '''
        Lower-case the dimension columns and give GA4's placeholders ('(not set)', '', nulls...) one label
        '''
        return df.with_columns(
            pl.col(column)
            .cast(pl.Utf8)
            .str.to_lowercase()
            .replace(UNKNOWN_VALUES)
            .fill_null(UNSPECIFIED)
            for column in self.columns
        )

    @staticmethod
    def attach_key(facts: pl.DataFrame, mapping: pl.DataFrame, on: str | Sequence[str]) -> pl.DataFrame:
        '''
        Add a key column to a fact table. Refuses a mapping that would duplicate fact rows
        '''
        on = [on] if isinstance(on, str) else list(on)
        if mapping.select(on).is_duplicated().any():
            raise ValueError(f'The key mapping has more than one row per {on}; that would duplicate fact rows')
        return facts.join(mapping, on=on, how='left')

    def first_per_entity(self, df: pl.DataFrame, entity: str, order_by: str) -> pl.DataFrame:
        '''
        The earliest row for each entity (every column kept)
        '''
        return df.sort(order_by, maintain_order=True).unique(subset=entity, keep='first', maintain_order=True)

    def _null_safe(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(pl.col(column).cast(pl.Utf8).fill_null(_NULL) for column in self.columns)
