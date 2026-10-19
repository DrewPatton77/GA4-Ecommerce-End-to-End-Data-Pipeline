'''
Minimal tests for the Postgres writer's pure parts (no database needed)
'''

from __future__ import annotations

import polars as pl
import pytest

pytest.importorskip('psycopg')

from ga4_ecommerce_analytics_engine.writers.postgres import PostgresConfig, PostgresWriter, postgres_type
from ga4_ecommerce_analytics_engine.writers.warehouse import ForeignKey, TableSpec, load_order, table_specs


@pytest.mark.parametrize(
    ('dtype', 'expected'),
    [
        pytest.param(pl.Int8, 'SMALLINT', id='int8'),
        pytest.param(pl.Int32, 'INTEGER', id='int32'),
        pytest.param(pl.Int64, 'BIGINT', id='int64'),
        pytest.param(pl.Utf8, 'TEXT', id='text'),
        pytest.param(pl.Date, 'DATE', id='date'),
        pytest.param(pl.Datetime, 'TIMESTAMP', id='datetime'),
    ],
)
def test_polars_types_map_to_postgres_types(dtype, expected):
    assert postgres_type(dtype) == expected


def test_lists_have_no_postgres_type():
    with pytest.raises(TypeError, match='No Postgres type'):
        postgres_type(pl.List(pl.Utf8))


def test_every_table_loads_after_the_tables_it_points_at():
    order = load_order(table_specs())

    for name, spec in table_specs().items():
        assert all(order.index(parent) < order.index(name) for parent in spec.parents), name


def test_a_foreign_key_cycle_is_reported():
    specs = {
        "a": TableSpec("a", foreign_keys=(ForeignKey("x", "b", "x"),)),
        "b": TableSpec("b", foreign_keys=(ForeignKey("x", "a", "x"),)),
    }

    with pytest.raises(ValueError, match="cycle"):
        load_order(specs)


def test_duplicate_primary_keys_are_caught_before_touching_the_database():
    specs = {"dim_x": TableSpec("dim_x", primary_key=("id",))}
    writer = PostgresWriter(PostgresConfig(), specs=specs)

    with pytest.raises(ValueError, match="duplicate"):
        writer.write({"dim_x": pl.DataFrame({"id": [1, 1]})})
