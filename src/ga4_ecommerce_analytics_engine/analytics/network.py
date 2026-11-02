"""Item co-occurrence network: which items form groups, and which items hold them together?

    result = CooccurrenceNetwork().build(matrix, names)       # matrix, names from BasketAnalyzer.basket_matrix
    result.nodes        one row per item in the final network: community, degree, strength, betweenness, hub rank...
    result.edges        one row per edge: co-occurrence, support, confidence both ways, lift, disparity p-value, bridge flag
    result.communities  one row per community: hub item, size, density, edges inside and between
    result.stages       how many edges and items survive each filtering step (and the final modularity)

The steps, each a separate method:

    count_pairs       one-hot basket matrix -> items x items count of baskets holding both (diagonal 0)
    graph             counts -> undirected weighted graph, keeping pairs with a weight above a floor
    disparity_filter  keep an edge when it is surprisingly large for one of its items, or when an item is well connected
    communities       Louvain on the final network, numbered by size
    node_rows / edge_rows / community_rows / stage_rows   the output rows, which build() turns into frames

Filtering order (all thresholds are fields, so they can be changed per run):

    1. every pair bought together at least once      "raw" network G; its busiest items are the hubs
    2. weight > min_cooccurrence (4)                  drops most edges: a pair seen a few times is noise
    3. disparity filter, alpha (0.05)                 keeps the edges that matter for their item (Serrano et al. 2009),
                                                      PLUS every edge of an item with degree >= min_degree (8)

The degree exemption stops the filter cutting the well-connected items to a few edges, so the network keeps its structure.
Degree is counted after the floor (step 2), before the disparity filter. There is no separate degree step: an item
ends up with no edges only if none of its edges is significant and it has fewer than 8 links.

Disparity filter. For an item i with k links and total weight s, an edge of weight w has share p = w / s. Under the
null model (weight spread evenly at random over the links), the chance of a share this large is (1 - p)^(k - 1). An
edge is kept when that p-value is below alpha for EITHER of its two items. An item with a single link cannot judge its
edge (p-value 1), so that edge survives only if the other item finds it significant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import polars as pl
import networkx as nx

from ga4_ecommerce_analytics_engine.schema import DataSchema


class NetworkResult(NamedTuple):
    nodes: pl.DataFrame
    edges: pl.DataFrame
    communities: pl.DataFrame
    stages: pl.DataFrame


@dataclass(frozen=True)
class CooccurrenceNetwork(DataSchema):
    min_cooccurrence: int = 4  # keep pairs bought together MORE than this many times
    alpha: float = 0.05  # disparity filter significance level
    min_degree: int = 8  # items with at least this many links (after the floor) keep ALL their edges
    n_hubs: int = 10  # the busiest items in the raw network are the hubs
    community_seed: int = 42
    community_prefix: str = "Community "

    # ---- Public ---------------------------------------------------------------

    def build(self, items: pl.DataFrame) -> NetworkResult:
        """`matrix`: transactions x items revenue matrix. `names`: its item names (see BasketAnalyzer.basket_matrix)."""
        import networkx as nx

        matrix, counts, names = self.create_basket_matrix(items)
        raw = self.get_modularity(self.create_basket_graph(counts, names))
        pruned = self.get_modularity(self.prune(raw))
        backbone = self.get_modularity(self.extract_backbone(self.disparity_filter(pruned)))
        
        found = self.communities(backbone)
        membership = {item: number for number, members in enumerate(found, start=1) for item in members}
        backbone.graph['modularity'] = nx.community.modularity(backbone, found, weight="weight")

        position = {name: k for k, name in enumerate(names)}
        baskets = (matrix > 0).sum(axis=0)
        revenue = matrix.sum(axis=0)

        layout = self.layout(backbone, found)
        nodes = self.node_rows(backbone, counts, position, baskets, revenue, membership, layout)
        edges = self.edge_rows(backbone, position, baskets, matrix.shape[0], membership)
        communities = self.community_rows(backbone, nodes, edges, found)
        stages = self.stage_rows([("pairs", raw), ("floor", pruned), ("disparity", backbone)])
        return NetworkResult(
            *(pl.DataFrame(rows, schema=schema) for rows, schema in zip((nodes, edges, communities, stages), self._schemas()))
        )

    # ---- 1. Co-occurrence and graphs ------------------------------------------

    def create_basket_matrix(self, items: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        
        # Build adjacency matrix -> get item-pair frequency.
        purchase_items = items.filter(pl.col(self.event_type).eq(self.conversion))
        baskets = purchase_items.with_columns(present=pl.lit(1)).pivot(index=self.transaction_id, on=self.item_id, values='present', aggregate_function='first').fill_null(0)
        baskets = baskets.drop(self.transaction_id)
        item_names = np.array(baskets.columns, dtype=object)
        baskets_np = baskets.to_numpy()
        pairs = baskets_np.T @ baskets_np
        np.fill_diagonal(pairs,0)

        return baskets_np, pairs, item_names

    def create_basket_graph(self, pairs: np.ndarray, names: list[str]) -> nx.Graph:
        graph = nx.from_numpy_array(pairs)
        mapping = {i: name for i, name in enumerate(names)}
        graph = nx.relabel_nodes(graph, mapping)
        return graph

    def graph(self, counts: np.ndarray, names: list[str], floor: int):
        """Undirected graph with an edge for every pair bought together MORE than `floor` times (weight = count)."""
        import networkx as nx

        graph = nx.Graph()
        graph.add_nodes_from(sorted(names))
        i, j = np.nonzero(np.triu(counts > floor, k=1))
        for a, b in zip(i.tolist(), j.tolist()):
            graph.add_edge(names[a], names[b], weight=int(counts[a, b]))
        return graph

    # ---- 2. Filters -----------------------------------------------------------

    def prune(self, graph) -> None:
        pruned_graph = graph.copy()
        weak_edges = [
                (u, v) for u, v, attrs in pruned_graph.edges(data=True)
                if attrs.get("weight", 1) < self.min_cooccurrence
            ]
        pruned_graph.remove_edges_from(weak_edges)
        pruned_graph.remove_nodes_from(list(nx.isolates(pruned_graph)))
        
        return pruned_graph

    def disparity_filter(self, graph) -> None:
        """
        Computes alpha values (local p-values) for each edge based on the disparity filter.
        Handles weighted strength calculations accurately.
        """
        B = nx.Graph()
        
        # Calculate the strength (sum of edge weights) for every node in the graph
        # NetworkX returns this via graph.degree(weight='weight')
        strength_dict = dict(graph.degree(weight='weight'))
        
        for u in graph.nodes():
            k = graph.degree(u)
            s = strength_dict[u]  # Node strength
            
            if k > 1 and s > 0:
                for v in graph.neighbors(u):
                    w = graph[u][v]['weight']
                    p = w / s
                    
                    # Statistical significance value alpha (closer to 0 means highly significant)
                    alpha = (1.0 - p) ** (k - 1)
                    
                    # Maintain the lowest alpha if edge is processed from both sides
                    if B.has_edge(u, v):
                        if alpha < B[u][v]['alpha']:
                            B[u][v]['alpha'] = alpha
                    else:
                        B.add_edge(u, v, weight=w, alpha=alpha)
            elif k == 1:
                # Keep trivial single connections with an alpha of 0 to protect micro-niches
                neighbor = list(graph.neighbors(u))[0]
                B.add_edge(u, neighbor, weight=graph[u][neighbor]['weight'], alpha=0.0)
                
        return B

    def extract_backbone(self, scored_graph):
        graph_backbone = nx.Graph()
        for u, v, attrs in scored_graph.edges(data=True):
            if attrs['alpha'] < self.alpha or attrs['weight'] >= self.min_degree:
                graph_backbone.add_edge(u, v, **attrs)

        graph_backbone.remove_nodes_from(list(nx.isolates(graph_backbone)))
        return graph_backbone

    # ---- 3. Communities -------------------------------------------------------

    def communities(self, graph) -> list[set[str]]:
        """Louvain groups on the final network, biggest first (then by total weight, then by name)."""
        import networkx as nx

        if graph.number_of_edges() == 0:
            return []
        found = nx.community.louvain_communities(graph, weight="weight", seed=self.community_seed)
        strength = dict(graph.degree(weight="weight"))
        return sorted(
            (set(members) for members in found),
            key=lambda members: (-len(members), -sum(strength[item] for item in members), min(members)),
        )

    def get_modularity(self, graph):
        found = self.communities(graph)
        graph.graph['modularity'] = nx.community.modularity(graph, found, weight="weight")
        return graph

    def layout(self, graph, found: list[set[str]], aspect: float = 2.9) -> dict[str, tuple[float, float]]:
        """Fixed x, y for every item, so a report can draw the network without running a layout itself.

        Communities are placed first (spring layout of the graph of communities, so related groups sit close), each
        community is then laid out on its own, and overlapping communities are pushed apart. The result fills
        [0, aspect] x [0, 1], the shape of the report's network card, with the same positions whatever the filters."""
        import networkx as nx

        if not found:
            return {}
        seed = self.community_seed
        where = {item: number for number, members in enumerate(found) for item in members}
        radius = [0.35 * len(members) ** 0.5 for members in found]  # community area grows with its item count

        # 1. the communities as nodes; an edge is the total weight between two communities
        between = nx.Graph()
        between.add_nodes_from(range(len(found)))
        for a, b, weight in graph.edges(data="weight"):
            ca, cb = where[a], where[b]
            if ca != cb:
                total = between[ca][cb]["weight"] + weight if between.has_edge(ca, cb) else weight
                between.add_edge(ca, cb, weight=total)
        if len(found) == 1:
            centre = {0: np.zeros(2)}
        else:
            centre = {c: np.asarray(p) * 4.0 for c, p in nx.spring_layout(between, weight="weight", seed=seed).items()}

        # 2. push overlapping communities apart (circles of the radii above, plus a small gap)
        for _ in range(300):
            moved = False
            for i in range(len(found)):
                for j in range(i + 1, len(found)):
                    gap = centre[j] - centre[i]
                    distance = float(np.hypot(*gap))
                    need = radius[i] + radius[j] + 0.15
                    if distance < need:
                        push = (gap / distance if distance > 1e-9 else np.array([1.0, 0.0])) * (need - distance) / 2
                        centre[i] = centre[i] - push
                        centre[j] = centre[j] + push
                        moved = True
            if not moved:
                break

        # 3. inside each community: spring layout of its own edges, scaled to its radius
        raw: dict[str, np.ndarray] = {}
        for c, members in enumerate(found):
            sub = graph.subgraph(members)
            if len(members) == 1:
                local = {next(iter(members)): np.zeros(2)}
            else:
                local = {k: np.asarray(v) for k, v in nx.spring_layout(sub, weight="weight", seed=seed).items()}
            for item, point in local.items():
                raw[item] = centre[c] + point * radius[c]

        # 4. fit [0, aspect] x [0, 1]
        points = np.array(list(raw.values()))
        low, high = points.min(axis=0), points.max(axis=0)
        span = np.where(high - low > 1e-9, high - low, 1.0)
        return {
            item: (float((p[0] - low[0]) / span[0] * aspect), float((p[1] - low[1]) / span[1]))
            for item, p in raw.items()
        }

    # ---- 4. Output rows -------------------------------------------------------

    def node_rows(self, graph, counts, position, baskets, revenue, membership, layout=None) -> list[dict]:
        """One row per item in the network. Betweenness and closeness treat a stronger link as a shorter distance."""
        import networkx as nx

        if graph.number_of_nodes() == 0:
            return []
        distance = self._distance_graph(graph)
        betweenness = nx.betweenness_centrality(distance, weight="distance")
        closeness = nx.closeness_centrality(distance, distance="distance")
        clustering = nx.clustering(graph)

        # Hubs come from the RAW network: the items bought together with the most other items, weighted by count.
        names = sorted(position, key=position.get)
        raw_strength = counts.sum(axis=1)
        raw_degree = (counts > 0).sum(axis=1)
        order = sorted(range(len(names)), key=lambda k: (-raw_strength[k], names[k]))
        rank = {names[k]: place for place, k in enumerate(order, start=1)}

        layout = layout or {}
        rows = []
        for item in graph.nodes:
            k = position[item]
            number = membership.get(item)
            x, y = layout.get(item, (None, None))
            rows.append(
                {
                    self.item_id: item,
                    self.community: number,
                    self.community_label: None if number is None else f"{self.community_prefix}{number:02d}",
                    self.degree: graph.degree(item),
                    self.strength: graph.degree(item, weight="weight"),
                    self.betweenness: betweenness.get(item, 0.0),
                    self.closeness: closeness.get(item, 0.0),
                    self.clustering: clustering.get(item, 0.0),
                    self.raw_degree: int(raw_degree[k]),
                    self.raw_strength: int(raw_strength[k]),
                    self.hub_rank: rank[item],
                    self.is_hub: int(rank[item] <= self.n_hubs),
                    self.item_baskets: int(baskets[k]),
                    self.item_revenue: int(round(float(revenue[k]))),
                    self.layout_x: x,
                    self.layout_y: y,
                }
            )
        return sorted(rows, key=lambda r: (r[self.community] or 0, -r[self.strength], r[self.item_id]))

    def edge_rows(self, graph, position, baskets, n_transactions, membership) -> list[dict]:
        """One row per edge, the alphabetically first item as `item_a`. Confidence reads a to b, and b to a."""
        import networkx as nx

        if graph.number_of_edges() == 0:
            return []
        between = {
            frozenset(edge): value
            for edge, value in nx.edge_betweenness_centrality(self._distance_graph(graph), weight="distance").items()
        }
        rows = []
        for a, b, data in sorted((min(a, b), max(a, b), data) for a, b, data in graph.edges(data=True)):
            weight, ba, bb = data["weight"], int(baskets[position[a]]), int(baskets[position[b]])
            rows.append(
                {
                    self.network_edge_id: len(rows),
                    self.item_a: a,
                    self.item_b: b,
                    self.cooccurrence: weight,
                    self.support_of_basket: weight / n_transactions,
                    self.confidence_a_to_b: weight / ba,  # of the baskets with a, the share that also hold b
                    self.confidence_b_to_a: weight / bb,
                    self.lift: weight * n_transactions / (ba * bb),
                    self.edge_alpha: data["alpha"],
                    self.edge_betweenness: between[frozenset((a, b))],
                    self.community_a: membership.get(a),
                    self.community_b: membership.get(b),
                    self.is_bridge: int(membership.get(a) != membership.get(b)),
                }
            )
        return rows

    def community_rows(self, graph, nodes: list[dict], edges: list[dict], found: list[set[str]]) -> list[dict]:
        """One row per community: its hub (most weight), size, density and how many edges are inside and leaving."""
        import networkx as nx

        strength = {row[self.item_id]: row[self.strength] for row in nodes}
        rows = []
        for number, members in enumerate(found, start=1):
            inside = [e for e in edges if e[self.community_a] == number and e[self.community_b] == number]
            leaving = [e for e in edges if e[self.is_bridge] == 1 and number in (e[self.community_a], e[self.community_b])]
            hub = sorted(members, key=lambda item: (-strength[item], item))[0]
            label = f"{self.community_prefix}{number:02d}"
            rows.append(
                {
                    self.community: number,
                    self.community_label: label,
                    self.community_hub: hub,
                    self.community_title: f"{label} · {hub}",
                    self.community_item_count: len(members),
                    self.community_edges: len(inside),
                    self.bridge_edges: len(leaving),
                    self.density: nx.density(graph.subgraph(members)),
                    self.total_cooccurrence: sum(e[self.cooccurrence] for e in inside),
                    self.average_lift: sum(e[self.lift] for e in inside) / len(inside) if inside else None,
                    self.community_items: ", ".join(sorted(members)),
                }
            )
        return rows

    def stage_rows(self, graphs: list[tuple[str, object]]) -> list[dict]:
        """How the network shrinks: edges and connected items after each step. Modularity is of the final network."""
        names = {
            "pairs": "Pairs bought together",
            "floor": f"More than {self.min_cooccurrence} baskets",
            "disparity": f"Disparity filter (alpha {self.alpha:g} or degree {self.min_degree}+)",
        }
        return [
            {
                self.stage_order: place,
                self.stage: names[key],
                self.edges: graph.number_of_edges(),
                self.nodes: graph.number_of_nodes(),
                self.modularity: graph.graph['modularity']
            }
            for place, (key, graph) in enumerate(graphs, start=1)
        ]

    # ---- Helpers --------------------------------------------------------------

    @staticmethod
    def _distance_graph(graph):
        """The same graph with a `distance` on each edge: a stronger link is a shorter one."""
        import networkx as nx

        distance = nx.Graph()
        distance.add_nodes_from(graph.nodes)
        distance.add_weighted_edges_from(((a, b, 1.0 / w) for a, b, w in graph.edges(data="weight")), weight="distance")
        return distance

    def _schemas(self) -> tuple[dict, dict, dict, dict]:
        """Column types of the four result tables: nodes, edges, communities, stages."""
        nodes = {
            self.item_id: pl.Utf8, self.community: pl.Int64, self.community_label: pl.Utf8,
            self.degree: pl.Int64, self.strength: pl.Int64, self.betweenness: pl.Float64,
            self.closeness: pl.Float64, self.clustering: pl.Float64,
            self.raw_degree: pl.Int64, self.raw_strength: pl.Int64, self.hub_rank: pl.Int64, self.is_hub: pl.Int8,
            self.item_baskets: pl.Int64, self.item_revenue: pl.Int64,
            self.layout_x: pl.Float64, self.layout_y: pl.Float64,
        }
        edges = {
            self.network_edge_id: pl.Int64, self.item_a: pl.Utf8, self.item_b: pl.Utf8, self.cooccurrence: pl.Int64,
            self.support_of_basket: pl.Float64, self.confidence_a_to_b: pl.Float64, self.confidence_b_to_a: pl.Float64,
            self.lift: pl.Float64, self.edge_alpha: pl.Float64, self.edge_betweenness: pl.Float64,
            self.community_a: pl.Int64, self.community_b: pl.Int64, self.is_bridge: pl.Int8,
        }
        communities = {
            self.community: pl.Int64, self.community_label: pl.Utf8, self.community_hub: pl.Utf8,
            self.community_title: pl.Utf8, self.community_item_count: pl.Int64, self.community_edges: pl.Int64,
            self.bridge_edges: pl.Int64, self.density: pl.Float64, self.total_cooccurrence: pl.Int64,
            self.average_lift: pl.Float64, self.community_items: pl.Utf8,
        }
        stages = {
            self.stage_order: pl.Int64, self.stage: pl.Utf8, self.edges: pl.Int64, self.nodes: pl.Int64,
            self.modularity: pl.Float64,
        }
        return nodes, edges, communities, stages
