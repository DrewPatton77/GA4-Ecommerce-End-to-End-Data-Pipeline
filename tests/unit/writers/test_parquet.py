
from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.writers.parquet import write_parquet


def test_each_table_is_written_to_its_own_file_and_reads_back(tmp_path):
    tables = {'dim_a': pl.DataFrame({'x': [1, 2]}), 'fact_b': pl.DataFrame({'y': ['u']})}

    paths = write_parquet(tables, tmp_path / 'out')

    assert sorted(p.name for p in paths) == ['dim_a.parquet', 'fact_b.parquet']
    assert pl.read_parquet(tmp_path / 'out' / 'dim_a.parquet')['x'].to_list() == [1, 2]
