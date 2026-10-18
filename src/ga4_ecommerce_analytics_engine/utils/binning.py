'''
Log-spaced binning for skewed columns, such as journey length and revenue.
'''

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ga4_ecommerce_analytics_engine.utils.formatting import format_dollars, format_duration

if TYPE_CHECKING:
    import polars as pl

LABEL_FORMATS = (None, 'timestamp', 'value')

def log_space_bins(data: np.ndarray, n_bins: int = 20) -> np.ndarray:
    data = np.asarray(data, dtype=float)
    if data.size == 0:
        raise ValueError("Cannot make bins from an empty column")

    low, high = data.min(), data.max()
    edges = np.expm1(np.linspace(np.log1p(low), np.log1p(high), n_bins + 1))
    return edges

def assign_bins(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    n_bins = len(edges) - 1
    index = np.clip(np.searchsorted(edges, values, side='right') - 1, 0, n_bins - 1)
    return np.where(np.isnan(values), -1, index)

def bin_labels(edges: np.ndarray, format: str | None = None, precision: int = 0) -> list[str]:
    if format not in LABEL_FORMATS:
        raise ValueError(f"Unknown label format '{format}'. Use one of {LABEL_FORMATS}")

    pairs = list(zip(edges[:-1], edges[1:]))
    if format == 'timestamp':
        return [f"{format_duration(a)} - {format_duration(b)}" for a, b in pairs]
    if format == 'value':
        return [f"{format_dollars(a)} - {format_dollars(b)}" for a,b in pairs]
    return [f"{round(float(a), precision)} - {round(float(b), precision)}" for a,b in pairs]

def transform_log_bin(
    df: 'pl.DataFrame', 
    column: str, 
    name: str, 
    n_bins: int = 20, 
    format: str | None = None,
    precision: int = 0,
) -> 'pl.DataFrame':
    import polars as pl

    bins_column, labels_column = f"{name}_bins", f"{name}_labels"
    values = df[column].cast(pl.Float64)
    data = values.drop_nulls().drop_nans()

    if data.len() == 0:
        return df.with_columns(
            pl.lit(None, dtype=pl.Int64).alias(bins_column),
            pl.lit(None, dtype=pl.Utf8).alias(labels_column),
        )

    edges = log_space_bins(data.to_numpy(), n_bins)
    labels = bin_labels(edges, format=format, precision=precision)
    index = assign_bins(values.fill_null(float("nan")).to_numpy(), edges)

    return df.with_columns(
        pl.Series(bins_column, index, dtype=pl.Int64)).with_columns(
            pl.when(pl.col(bins_column) >= 0)
            .then(pl.col(bins_column))
            .otherwise(None)
            .alias(bins_column)
        ).with_columns(
            pl.col(bins_column)
            .replace_strict(dict(enumerate(labels)), default=None, return_dtype=pl.Utf8)
            .alias(labels_column)
        )
