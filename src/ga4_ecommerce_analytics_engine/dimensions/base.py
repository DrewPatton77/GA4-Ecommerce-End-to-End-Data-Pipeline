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
            source.select(self.columns)
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
        left = self._null_safe(entities)
        right = self._null_safe(dimension.select(self.key, *self.columns))  # the DIMENSION, not the entities
        return left.join(right, on=list(self.columns), how="left").select(*entity_cols, self.key)

    @staticmethod
    def attach_key(facts: pl.DataFrame, mapping: pl.DataFrame, on: str | Sequence[str]) -> pl.DataFrame:
        '''
        Add a key column to a fact table. Refuses a mapping that would duplicate fact rows
        '''
        on = [on] if isinstance(on, str) else list(on)
        if mapping.select(on).is_duplicated().any():
            raise ValueError(f'The key mapping has more than one row per {on}; that would duplicate fact rows.')
        return facts.join(mapping, on=on, how='left')

    def first_per_entity(self, df: pl.DataFrame, entity: str, order_by: str) -> pl.DataFrame:
        '''
        The earliest row for each entity (every column kept)
        '''
        return df.sort(order_by, maintain_order=True).unique(subset=entity, keep='first', maintain_order=True)

    def _null_safe(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(pl.col(column).cast(pl.Utf8).fill_null(_NULL) for column in self.columns)
