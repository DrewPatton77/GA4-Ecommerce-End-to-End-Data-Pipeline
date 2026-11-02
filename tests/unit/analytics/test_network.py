'''
Tests for analytics/network.py (CooccurrenceNetwork): counting, the two filters, and the output tables.
'''

from __future__ import annotations

import polars as pl
import pytest

pytest.importorskip("networkx")
import networkx as nx  # noqa: E402

from ga4_ecommerce_analytics_engine.analytics.network import CooccurrenceNetwork  # noqa: E402
from ga4_ecommerce_analytics_engine.schema import DataSchema  # noqa: E402

s = DataSchema()


def purchase_items(baskets: list[list[str]], other_events: list[tuple[str, str]] = ()) -> pl.DataFrame:
    '''
    One purchase transaction per basket. `other_events` are (event name, item) rows that must be ignored.
    '''
    rows = [
        {s.event_type: s.conversion, s.transaction_id: f"t{n}", s.item_id: item}
        for n, basket in enumerate(baskets)
        for item in basket
    ]
    rows += [{s.event_type: event, s.transaction_id: None, s.item_id: item} for event, item in other_events]
    return pl.DataFrame(rows)


def two_triangles() -> pl.DataFrame:
    '''
    A, B, C bought together 6 times; D, E, F 6 times; C and D together twice (14 baskets).
    '''
    return purchase_items([["A", "B", "C"]] * 6 + [["D", "E", "F"]] * 6 + [["C", "D"]] * 2)


def relaxed() -> CooccurrenceNetwork:
    # Tiny data: drop pairs seen fewer than 3 times, be lenient on significance, switch the weight exemption off.
    return CooccurrenceNetwork(min_cooccurrence=3, alpha=0.6, min_degree=99, n_hubs=1)


def test_pair_counts_come_from_purchases_only_and_the_diagonal_is_zero():
    items = purchase_items([["A", "B"]] * 3 + [["B", "C"]], other_events=[(s.view_item, "Z")])

    _, counts, names = CooccurrenceNetwork().create_basket_matrix(items)

    at = {name: k for k, name in enumerate(names)}
    assert "Z" not in at
    assert counts[at["A"], at["B"]] == 3 and counts[at["B"], at["C"]] == 1 and counts[at["A"], at["C"]] == 0
    assert counts.diagonal().tolist() == [0, 0, 0]


def test_the_floor_keeps_pairs_at_the_threshold_and_drops_weaker_ones_with_their_isolated_items():
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=3)
    graph.add_edge("c", "d", weight=4)
    graph.add_edge("e", "f", weight=5)

    kept = CooccurrenceNetwork(min_cooccurrence=4).prune(graph)

    assert {frozenset(edge) for edge in kept.edges} == {frozenset("cd"), frozenset("ef")}
    assert set(kept.nodes) == set("cdef")


def test_disparity_score_of_an_edge_is_its_lowest_value_from_either_item():
    graph = nx.Graph()
    graph.add_edge("a", "b", weight=8)
    graph.add_edge("a", "c", weight=1)
    graph.add_edge("b", "c", weight=1)

    scored = CooccurrenceNetwork().disparity_filter(graph)

    # a and b see the heavy edge as 8/9 of their weight: alpha = 1/9. c sees both its edges as half: alpha = 0.5.
    assert scored["a"]["b"]["alpha"] == pytest.approx(1 / 9)
    assert scored["a"]["c"]["alpha"] == pytest.approx(0.5)
    assert scored["b"]["c"]["alpha"] == pytest.approx(0.5)


def test_an_edge_of_an_item_with_a_single_link_always_gets_alpha_zero():
    star = nx.Graph()
    for leaf, weight in enumerate([20, 1, 1, 1, 1]):
        star.add_edge("hub", f"leaf{leaf}", weight=weight)

    scored = CooccurrenceNetwork().disparity_filter(star)

    assert scored.number_of_edges() == 5
    assert all(data["alpha"] == 0.0 for *_, data in scored.edges(data=True))


def test_the_backbone_keeps_significant_edges_and_edges_with_a_large_cooccurrence():
    scored = nx.Graph()
    scored.add_edge("a", "b", weight=8, alpha=0.9)  # not significant, but co-occurrence 8 >= min_degree
    scored.add_edge("c", "d", weight=7, alpha=0.9)  # neither
    scored.add_edge("e", "f", weight=1, alpha=0.01)  # significant

    backbone = CooccurrenceNetwork(alpha=0.05, min_degree=8).extract_backbone(scored)

    assert {frozenset(edge) for edge in backbone.edges} == {frozenset("ab"), frozenset("ef")}


def test_build_finds_the_two_groups_and_records_how_each_step_shrinks_the_network():
    result = relaxed().build(two_triangles())

    assert result.communities[s.community_items].to_list() == ["A, B, C", "D, E, F"]
    assert result.nodes.height == 6
    assert result.stages[s.edges].to_list() == [7, 6, 6]  # the C-D pair (2 baskets) falls below the floor
    assert result.stages[s.nodes].to_list() == [6, 6, 6]
    assert result.stages[s.modularity][-1] == pytest.approx(0.5)  # two equal, separate triangles


def test_edge_and_node_rows_carry_the_basket_measures_and_the_hubs_come_from_the_raw_network():
    result = relaxed().build(two_triangles())

    edge = result.edges.filter((pl.col(s.item_a) == "A") & (pl.col(s.item_b) == "C")).row(0, named=True)
    assert edge[s.cooccurrence] == 6
    assert edge[s.confidence_a_to_b] == pytest.approx(6 / 6)  # every basket with A also holds C
    assert edge[s.confidence_b_to_a] == pytest.approx(6 / 8)  # C is in 8 baskets
    assert edge[s.lift] == pytest.approx(6 * 14 / (6 * 8))
    assert edge[s.is_bridge] == 0

    c = result.nodes.filter(pl.col(s.item_id) == "C").row(0, named=True)
    assert c[s.raw_degree] == 3 and c[s.degree] == 2  # the weak C-D link is gone from the final network
    assert c[s.hub_rank] == 1 and c[s.is_hub] == 1  # raw strength 14, tied with D, wins on name
    assert result.nodes[s.is_hub].sum() == 1