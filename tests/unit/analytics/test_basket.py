"""Minimal tests for analytics/basket.py (BasketAnalyzer)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.analytics.basket import BasketAnalyzer

ITEM_SCHEMA = {
    "transaction_id": pl.Utf8,
    "event_name": pl.Utf8,
    "item_name": pl.Utf8,
    "item_revenue": pl.Float64,
}


def make_items(rows: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=ITEM_SCHEMA, orient="row")


def by_basket(df: pl.DataFrame) -> dict[str, dict]:
    return {row["basket"]: row for row in df.iter_rows(named=True)}


# Four transactions: t1 and t2 buy A+B, t3 buys A, t4 buys C.
PURCHASES = [
    ("t1", "purchase", "A", 10.0), ("t1", "purchase", "B", 20.0),
    ("t2", "purchase", "A", 10.0), ("t2", "purchase", "B", 20.0),
    ("t3", "purchase", "A", 10.0),
    ("t4", "purchase", "C", 5.0),
    ("t4", "view_item", "C", 99.0),  # not a purchase: ignored
]


def test_purchase_lines_remove_colour_words_and_merge_the_resulting_duplicates():
    items = make_items(
        [
            ("t1", "purchase", "Hoodie Blue", 10.0),
            ("t1", "purchase", "Hoodie Red", 20.0),
            ("t1", "purchase", "Mug", 5.0),
            ("t1", "view_item", "Mug", 99.0),
        ]
    )

    lines = BasketAnalyzer().purchase_lines(items)

    assert {row["item_name"]: row["item_revenue"] for row in lines.iter_rows(named=True)} == {
        "Hoodie": 30.0,
        "Mug": 5.0,
    }


def test_item_names_are_left_alone_when_the_filter_is_off():
    items = make_items([("t1", "purchase", "Hoodie Blue", 10.0)])

    lines = BasketAnalyzer(use_item_filter=False).purchase_lines(items)

    assert lines["item_name"].to_list() == ["Hoodie Blue"]


def test_basket_matrix_sorts_items_and_drops_items_with_no_revenue():
    lines = pl.DataFrame(
        {
            "transaction_id": ["t1", "t1", "t2"],
            "item_name": ["Zed", "Apple", "Free"],
            "item_revenue": [10.0, 5.0, 0.0],
        }
    )

    matrix, names = BasketAnalyzer().basket_matrix(lines)

    assert names == ["Apple", "Zed"]  # sorted; 'Free' was never bought for money
    assert matrix.shape == (2, 2)  # t2 is still a transaction
    assert matrix.sum(axis=0).tolist() == [5.0, 10.0]


def test_pair_metrics_for_an_item_pair():
    matrix = np.array([[10, 20, 0], [10, 20, 0], [10, 0, 0], [0, 0, 5]], dtype=float)

    rows = by_basket(BasketAnalyzer().pair_metrics(matrix, ["A", "B", "C"]))

    ab = rows["A - B"]
    assert (ab["antecedent"], ab["consequent"], ab["is_self_node"]) == ("A", "B", 0)
    assert ab["number_of_transactions"] == 2
    assert ab["support_of_basket"] == pytest.approx(0.5)
    assert ab["confidence_of_first_item"] == pytest.approx(1.0)  # 2 together / 2 transactions with B
    assert ab["confidence_of_second_item"] == pytest.approx(2 / 3)  # 2 together / 3 transactions with A
    assert ab["lift"] == pytest.approx(0.5 / (0.75 * 0.5))
    assert ab["value"] == 70  # revenue of A (30) plus revenue of B (40)


def test_pair_metrics_has_a_self_row_per_item_and_skips_not_set():
    matrix = np.array([[10, 20, 3], [10, 0, 3]], dtype=float)

    rows = by_basket(BasketAnalyzer().pair_metrics(matrix, ["A", "(not set)", "C"]))

    assert set(rows) == {"A", "A - C", "C"}  # nothing involving '(not set)'
    assert rows["A"]["is_self_node"] == 1
    assert rows["A"]["number_of_transactions"] == 2
    assert rows["A"]["value"] == 20  # A's own revenue, not doubled


def test_build_gives_ids_and_gives_a_cluster_of_items_one_community():
    pytest.importorskip('networkx')
    purchases = [
        (t, 'purchase', item, 10.0) for t in ('t1', 't2', 't3') for item in ('A', 'B', 'C')
    ] + [('t4', 'purchase', 'D', 5.0)]

    result = BasketAnalyzer().build(make_items(purchases))
    rows = by_basket(result)

    assert result.height == 10  # four self rows and six pairs
    assert result['basket_id'].to_list() == list(range(10))
    cluster = {rows[pair]['community'] for pair in ('A - B', 'A - C', 'B - C')}
    assert len(cluster) == 1 and None not in cluster  # one shared community
    assert rows['A - D']['community'] is None  # never bought together
    assert rows['A']['community'] is None  # self rows never take part


def test_no_purchases_gives_an_empty_table_with_the_right_columns():
    pytest.importorskip("networkx")
    items = make_items([("t1", "view_item", "A", 1.0)])

    result = BasketAnalyzer().build(items)

    assert result.height == 0
    assert {"basket", "lift", "community", "basket_id"} <= set(result.columns)

