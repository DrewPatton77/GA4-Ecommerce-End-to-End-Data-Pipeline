'''
Basket analysis: which items are bought together?

    BasketAnalyzer().build(items)  ->  one row per item (a "self" row) and per item pair, with
                                       transactions, support, confidence, lift, value and a community.

The steps are separate methods so each can be tested on its own:

    purchase_lines   purchase rows -> (transaction, item, revenue), with colour/size words removed from names
    basket_matrix    lines -> transactions x items revenue matrix (numpy) and the item names
    pair_metrics     matrix -> one row per item pair with the association metrics
    add_communities  group strongly-associated items into communities (Louvain)
'''

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import add_id
from ga4_ecommerce_analytics_engine.schema import DataSchema

PAIR_SEPARATOR = ' - '

# Words removed from item names so "Hoodie Blue" and "Hoodie Red" count as the same item.
# (These are regex fragments, exactly as in the legacy code, so '(Blue/Green)' matches the text Blue/Green.)
DEFAULT_FILTERED_TERMS: tuple[str, ...] = (
    'Black', 'Blue', 'Red', 'Yellow', 'White', '(Blue/Green)', '(Multicolored)', '(Red/Yellow)', 'Charcoal', 'Coral',
    'Gray', 'Green', 'Grey', 'Ivory', 'Mint', 'Moss', 'Navy', 'Olive', 'Orange', 'Pink', 'Grass', 'Neon', 'Light',
    'Citron', 'Lilac', 'Cloud', 'Confetti', '24 oz', '24oz',
)


@dataclass(frozen=True)
class BasketAnalyzer(DataSchema):
    # Communities are built from pairs with at least this support and this confidence (in either direction).
    min_support: float = 0.002
    min_confidence: float = 0.20
    community_seed: int = 42

    use_item_filter: bool = True
    filtered_terms: tuple[str, ...] = DEFAULT_FILTERED_TERMS

    def build(self, items: pl.DataFrame) -> pl.DataFrame:
        lines = self.purchase_lines(items)
        matrix, names = self.basket_matrix(lines)
        baskets = add_id(self.pair_metrics(matrix, names), self.basket_id)
        return self.add_communities(baskets)

    # ---- 1. Purchase lines ----------------------------------------------------

    def purchase_lines(self, items: pl.DataFrame) -> pl.DataFrame:
        self.check_required_columns(
            items, required_columns={self.event_type, self.transaction_id, self.item_id, self.item_value}
        )
        lines = items.filter(pl.col(self.event_type) == self.conversion).select(
            self.transaction_id, self.item_id, self.item_value
        )

        name = pl.col(self.item_id)
        if self.use_item_filter:
            name = name.str.replace_all(self._filter_pattern(), "").str.strip_chars()
            name = name.str.replace_all("  ", " ", literal=True)
        lines = lines.with_columns(name.str.strip_chars().alias(self.item_id))

        # After filtering, several rows can share a name within one transaction: add their revenue together.
        return lines.group_by([self.transaction_id, self.item_id], maintain_order=True).agg(
            pl.col(self.item_value).sum()
        )

    def _filter_pattern(self) -> str:
        terms = [*self.filtered_terms, *(f"Light {t}" for t in self.filtered_terms),
                 *(f"Bright {t}" for t in self.filtered_terms)]
        return r"(?i)\b(" + "|".join(terms) + r")\b"

    # ---- 2. Basket matrix -----------------------------------------------------

    def basket_matrix(self, lines: pl.DataFrame) -> tuple[np.ndarray, list[str]]:
        '''
        A (transactions x items) revenue matrix. Items are sorted by name; items never bought are dropped
        '''
        if lines.height == 0:
            return np.zeros((0, 0)), []

        wide = lines.pivot(
            on=self.item_id, index=self.transaction_id, values=self.item_value, aggregate_function="sum"
        )
        names = sorted(column for column in wide.columns if column != self.transaction_id)
        matrix = wide.select(names).fill_null(0).to_numpy().astype(float)

        # An item with no positive revenue anywhere is in no basket; its metrics would be 0/0.
        bought = (matrix > 0).any(axis=0)
        return matrix[:, bought], [name for name, keep in zip(names, bought) if keep]

    # ---- 3. Pair metrics ------------------------------------------------------

    def pair_metrics(self, matrix: np.ndarray, items: list[str]) -> pl.DataFrame:
        '''
        One row per item (is_self_node = 1) and per pair of different items, ordered by (i, j) with i <= j
        '''
        if not items:
            return self._empty()

        n_transactions = matrix.shape[0]
        revenue = matrix.sum(axis=0)
        pair_revenue = revenue[:, None] + revenue[None, :]  # outer sum

        present = (matrix > 0).astype(np.int64)  # one-hot basket
        together = present.T @ present  # number of transactions containing both items
        support = together / n_transactions
        confidence = together / np.diag(together)  # [i, j] = together[i, j] / (transactions containing j)
        diagonal = np.diag(support)
        lift = support / np.outer(diagonal, diagonal)  # support[i, j] / (support[i] * support[j])

        names = np.array(items, dtype=object)
        i, j = np.triu_indices(len(items))
        keep = (names[i] != self.not_set) & (names[j] != self.not_set)
        i, j = i[keep], j[keep]
        is_self = i == j

        antecedent, consequent = names[i].tolist(), names[j].tolist()
        basket = [a if same else f"{a}{PAIR_SEPARATOR}{c}" for a, c, same in zip(antecedent, consequent, is_self)]
        value = np.where(is_self, pair_revenue[i, j] / 2, pair_revenue[i, j]).astype(np.int64)

        return pl.DataFrame(
            {
                self.antecedent: antecedent,
                self.consequent: consequent,
                self.basket: basket,
                self.number_of_transactions: together[i, j],
                self.support_of_basket: support[i, j],
                self.confidence_of_first_item: confidence[i, j],
                self.confidence_of_second_item: confidence[j, i],
                self.lift: lift[i, j],
                self.is_self_node: is_self.astype(np.int8),
                self.basket_value: value,
            }
        )

    def _empty(self) -> pl.DataFrame:
        return pl.DataFrame(
            schema={
                self.antecedent: pl.Utf8, self.consequent: pl.Utf8, self.basket: pl.Utf8,
                self.number_of_transactions: pl.Int64, self.support_of_basket: pl.Float64,
                self.confidence_of_first_item: pl.Float64, self.confidence_of_second_item: pl.Float64,
                self.lift: pl.Float64, self.is_self_node: pl.Int8, self.basket_value: pl.Int64,
            }
        )

    # ---- 4. Communities -------------------------------------------------------

    def add_communities(self, baskets: pl.DataFrame) -> pl.DataFrame:
        '''
        Add a `community` column: items strongly associated with each other share a community number.

        Only pairs with enough support and confidence take part. Every other row gets null. A pair whose two
        items sit in different communities gets the higher community number
        '''
        import networkx as nx

        no_communities = baskets.with_columns(pl.lit(None, dtype=pl.Int64).alias(self.community))

        strong = (
            baskets.filter(
                (pl.col(self.is_self_node) == 0)
                & (pl.col(self.support_of_basket) >= self.min_support)
                & (
                    (pl.col(self.confidence_of_first_item) >= self.min_confidence)
                    | (pl.col(self.confidence_of_second_item) >= self.min_confidence)
                )
            )
            .sort(
                [self.confidence_of_first_item, self.confidence_of_second_item],
                descending=[True, True],
                maintain_order=True,
            )
        )
        if strong.height == 0:
            return no_communities

        graph = nx.DiGraph()
        for row in strong.iter_rows(named=True):
            graph.add_edge(
                row[self.antecedent],
                row[self.consequent],
                lift=row[self.lift],
                transactions=row[self.number_of_transactions],
            )

        communities = nx.community.louvain_communities(graph, seed=self.community_seed)
        membership = {item: number for number, members in enumerate(c for c in communities if c) for item in members}

        strong = strong.with_columns(
            pl.max_horizontal(
                pl.col(self.antecedent).replace_strict(membership, return_dtype=pl.Int64),
                pl.col(self.consequent).replace_strict(membership, return_dtype=pl.Int64),
            ).alias(self.community)
        )
        
        return baskets.join(
            strong.select(self.basket, self.community), on=self.basket, how="left", maintain_order="left"
        )
