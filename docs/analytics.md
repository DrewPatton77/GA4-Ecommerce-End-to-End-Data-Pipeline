# Analytics methods

## Attribution (`analytics/attribution.py`)

`AttributionAnalyzer().build(sessions, converting_journeys)` returns `facts` (one row per session in a converting
journey, per model) and `models` (one row per model). Every model gives each converting journey a total credit of 1,
so every model's revenue adds up to the same total.

| Model | Rule |
|---|---|
| First-Click | all credit to the first session |
| Last-Click | all credit to the last session |
| Last-Click Non-Direct | last session that was not Direct (the last session if all were Direct) |
| Linear | equal credit to every session |
| Position-Based | one session: 100%; two: 50% each; three or more: 40% first, 40% last, 20% shared by the middle |
| Time-Decay | weights halve every 168 hours before the journey's last session |
| Shapley Value | equal credit to every distinct channel, shared between that channel's sessions |
| Markov Chain | credit split between the journey's distinct channels by removal effect |

**Only sessions up to the user's last purchase session will get credit.** A visit after the last purchase cannot have
caused that purchase. Position, count and the hours used by Time-Decay are measured on the sessions that are left, so **a path
ends at the purchase**. Users who never convert keep every session, since they only shape the Markov chain.

**Direct.** The Direct channel is matched ignoring case and spaces, so `Direct` and `direct` are one channel. Under
Last-Click Non-Direct, a journey that was Direct all the way to the purchase falls back to Direct (this is how Google
Analytics treats it), so *some* Direct credit under that model is expected. Direct credit on a journey that had a
non-Direct session before its purchase would be a bug; the check found none.

**Dates.** `date_id` is the day of the touch; `conversion_date_id` is the day of the purchase. Credit by touch date
can sit on a day with no purchases because earlier touches of a journey keep their own dates. Use `conversion_date_id`
to report credit on the day it was earned.

**Markov removal effect.** Every user's path (converting or not) becomes Start -> channel -> ... -> Conversion or
Null. The conversion probability from Start is solved exactly with `np.linalg.solve`, then again with each channel's
incoming transitions removed. A channel's effect is the share of conversions lost without it, normalised to sum to 1.

Markov credit is allocated per journey, so channel totals differ from "removal effect x total revenue". Use
`removal_effects` for that.

**Using it in Power BI.** Always filter `fact_attribution` to one model (or put the model in a legend). Summing
several models counts the same revenue several times.

## Basket analysis (`analytics/basket.py`)

Each transaction becomes a row of a one-hot matrix (1 if the item was bought). Multiplying the matrix by its transpose
counts how many transactions hold each pair. The result is one row per item pair (the alphabetically first item is the
antecedent), with:

- **Support** = baskets with the pair / all baskets.
- **Confidence** in each direction. `confidence_of_second_item` is the share of baskets with the FIRST item that also
  hold the second; `confidence_of_first_item` is the reverse.
- **Lift** = support of the pair / (support of A x support of B). Above 1 the pair is bought together more than chance
  predicts, 1 is exactly as expected, below 1 it is bought together less.
- **Value** = revenue of both items, summed over every transaction.

Pairs with support below 0.002 (about 10 baskets) are dropped: most pairs almost never occur
together, and a lift from a handful of baskets is noise. Because the cut-off is on how often a pair occurs, the pairs
that are kept lean towards lift >= 1. A kept pair with lift < 1 is therefore informative: both items are popular, yet
shoppers rarely combine them.

Colour and size words are removed from item names (the `filtered_terms` list in `basket.py`, plus `Light` and `Bright` variants) so `Hoodie Blue` and `Hoodie Red` count as one item; revenue of merged rows in a transaction is added together. Items named `(not set)` are skipped. Extreme lift
(15 or more) is worth a manual look. The basket table has no communities: groups of items come from the network.

## Item statistics

The Pareto view ranks products by revenue with cumulative share and A/B/C tiers at 80%, 95% and 100%. Tier and price
band effects on view-to-cart and cart-to-purchase rates were tested with Kruskal-Wallis, pairwise Mann-Whitney with
Bonferroni correction and epsilon-squared effect sizes. These tests live in the analysis (data exploration) notebooks, not the pipeline.

## Co-occurrence network (`analytics/network.py`)

The pair statistics above say how strong each pair is. The network shows how pairs fit together: which items are hubs,
which items connect groups, and which groups exist.

1. **Graph.** The network builds its own 0/1 basket matrix from the purchase item rows (it does not reuse the basket
   module's matrix, and it does not remove colour words). The matrix times its transpose counts baskets per pair, an
   undirected weighted graph. Hubs are the busiest items in this raw graph (total count, ties by name).

2. **Floor.** Drop edges with co-occurrence below `min_cooccurrence` (4), so an edge of exactly 4 is kept, then drop items
   left with no edges. A pair bought together a handful of times is noise; this removes most edges.

3. **Disparity score.** For an item with k links and total weight s, an edge of weight w is a share p = w / s. If weight
   were spread evenly at random, the chance of a share this large is alpha = (1 - p)^(k - 1). Each edge keeps the lower
   alpha of its two items. An item with exactly one link gives its edge alpha 0, so single-link edges are always kept
   at this step.

4. **Backbone.** Keep an edge when alpha is below `alpha` (0.05) **or** its co-occurrence is at least `min_degree` (8).
   Despite its name, `min_degree` is compared with the edge's co-occurrence, so it keeps every pair bought together 8 or
   more times. This stops the filter cutting the busy items to a few edges. Items left with no edges are dropped.
5. **Communities.** Louvain on the final weighted graph, seed 42, numbered by size (then total weight, then name).
   Modularity says how clearly the groups separate (above about 0.3 is meaningful structure). It is recorded for
   every stage in `fact_network_stage`, each computed on that stage's own graph.

6. **Metrics.** Degree, strength, betweenness (which items sit between groups), closeness and clustering per item;
   co-occurrence, support, confidence both ways, lift and edge betweenness per edge. Betweenness and closeness treat a
   stronger link as a shorter distance (1 / co-occurrence). Support, confidence and lift use the baskets of the
   0/1 matrix.

7. **Layout.** Fixed drawing positions are computed in the pipeline (`layout_x`, `layout_y`, x from 0 to 2.9, y from 0 to
   1): communities are placed first, pushed apart where their circles overlap, then the items are laid out inside each
   community's circle. The positions are saved, so the Deneb visual draws the same picture every time instead of
   recomputing a force layout.

Betweenness-high, degree-low items are the connectors between communities. `fact_network_stage` shows how many edges
and items survive each step, so a reader can see what the filters did.

**Result of the last full run** (it changes whenever a filter does): 191 items, 338 links kept of the pairs bought together, 27 communities,
modularity 0.67.

### Choosing the Louvain resolution

Louvain has a resolution parameter (gamma). The pipeline uses the default (1.0). To check that the groups are not an
accident of that setting, scan it instead of picking a value by eye:

1. Scan gamma on a log scale (for example 0.3 to 3, 25 values) with many seeds per value.

2. For each gamma record the number of communities, the number of singletons, the largest community's share and the
   stability across seeds (average normalised mutual information between runs).

3. Do not compare modularity across different gammas; it is only comparable at one value.

4. Look for a plateau: a range of gamma where the community count and the stability barely move. Choose inside it.

5. Check the groups against something independent, such as product category, and check that two random halves of the
   baskets give similar groups (adjusted Rand index).

6. If there is no plateau, report two levels (a coarse and a fine grouping) instead of one.

7. Scan the final backbone (after the filters), not the unfiltered graph, and drop isolated items first.

This is an analysis step and **not** part of the pipeline.
