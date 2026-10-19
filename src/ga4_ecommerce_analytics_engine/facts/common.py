'''
Small helpers shared by the fact builders. They take column names, so they know nothing about the schema
'''

from __future__ import annotations

import polars as pl


def to_date_id(column: str) -> pl.Expr:
    '''
    A date as the integer 20201201. Int32, to match DateDimension's date key so the two join cleanly
    '''
    return pl.col(column).dt.strftime("%Y%m%d").cast(pl.Int32)


def add_id(df: pl.DataFrame, name: str) -> pl.DataFrame:
    '''
    Add a 0-based integer id column (Int64) in the frame's current row order
    '''
    return df.with_row_index(name).with_columns(pl.col(name).cast(pl.Int64))


def drop_present(df: pl.DataFrame, columns: tuple[str, ...]) -> pl.DataFrame:
    '''
    Drop whichever of `columns` exist, so a missing optional column is not an error
    '''
    return df.drop([column for column in columns if column in df.columns])
