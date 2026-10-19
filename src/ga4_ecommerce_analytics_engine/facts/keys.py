'''
Attach dimension keys to a fact table
'''

from __future__ import annotations

from typing import Sequence

import polars as pl

from ga4_ecommerce_analytics_engine.dimensions.base import BaseDimension


def attach_keys(fact: pl.DataFrame, mappings: Sequence[tuple[pl.DataFrame, str]]) -> pl.DataFrame:
    '''
    Left-join each (mapping, join_column) onto the fact. Row count never changes (attach_key checks).

        schema = DataSchema()
        fact = attach_keys(fact, [(geo_mapping, schema.user_id), (traffic.session_mapping, schema.session_id)])
    '''
    for mapping, on in mappings:
        fact = BaseDimension.attach_key(fact, mapping, on)
    return fact
