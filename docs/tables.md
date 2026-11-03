# Output tables

22 tables. Purchase events with no revenue are dropped (see the README, 'Data Quality' section).

All keys are integer surrogate keys unless noted. Key column names come from `DataSchema`.
Every fact has the dimension keys `geo_id` and `device_id` (which is resolved per user) and, where listed, `traffic_source_id`.

## Dimensions

| Table | Grain | Key | Notes |
|---|---|---|---|
| `dim_date` | one row per calendar day seen in events | `date_id` (YYYYMMDD int) | day name, week, month, quarter, weekend flag |
| `dim_geo` | one row per distinct continent/country/region/city | `geo_id` | values are lower case; `''`, `(not set)` and nulls become `unspecified` |
| `dim_device` | one row per distinct category/brand/model/OS/OS version | `device_id` | built from each user's first device; same lower-casing as `dim_geo` |
| `dim_traffic_source` | one row per distinct source/medium/campaign/channel | `traffic_source_id` | `channel` is the more detailed label from the channel rules; `channel_group` collapses small channels for charts (`enrichment/channel_groups.py`); all values are lower case (`paid search`, `direct`), unlike the proper-case channel names in the Enrichment output |
| `dim_product` | one row per product name | `product_id` (integer) | `item_name`, brand, category: the product's most common real value, else `Unbranded` / `Uncategorized` (never `(not set)` or `--`); `(not set)` names excluded |
| `dim_item` | one row per item variant (name + variant) | `item_id` (integer) | `product_id`, `item_name`, `item_variant`, highest price seen; keys are assigned in name, variant order so they are stable |
| `dim_attribution_model` | one row per attribution model | `attribution_model_id` (integer) | model name and a one-line description; keys follow the order First-Click, Last-Click, Last-Click Non-Direct, Linear, Position-Based, Time-Decay, Shapley Value, Markov Chain |
| `dim_transaction` | one row per purchase transaction | `transaction_id` | basket size, value, unique items, conversion timestamp |

## Facts

| Table | Grain | Key | Points at |
|---|---|---|---|
| `fact_event` | one row per event | `event_id` | date, geo, device, traffic source |
| `fact_item_funnel` | one row per user, session, day, PRODUCT (variants collapsed) | `item_funnel_id` | date, geo, device, traffic source, product |
| `fact_session` | one row per session | `session_id` (text) | date, geo, device, traffic source |
| `fact_user` | one row per user | `user_pseudo_id` (text) | geo, device, traffic source (first session) |
| `fact_journey` | one row per user (all users) | `journey_id` | geo, device, traffic source |
| `fact_converting_journey` | one row per user with a conversion | `converting_journey_id` | geo, device, traffic source |
| `fact_attribution` | one row per session in a converting journey, per model (zero-credit rows are left out) | `attribution_id` | date (of the touch session), conversion date (of the purchase), geo, device, traffic source (of the touch session), model, converting journey, session |
| `fact_basket` | one row per item pair with support of at least `min_support` (0.002, about 10 baskets) | `basket_id` | none; items are named in `antecedent` / `consequent` |

`fact_item_funnel` flags (`is_viewed`, `is_added_to_cart`, `is_checked_out`, `is_purchased`) are back-filled:
reaching a later step implies the earlier ones. The funnel is per product because views often carry no variant;
for variant mix use `bridge_transaction_item` with `dim_item`.

`fact_attribution`: `credit` is the session's share of its journey (the shares of one model add up to 1 per journey);
`revenue_credit` is `credit` times the journey's revenue. Always filter to ONE model,
because adding up several models counts the same revenue several times. The `date_id` and traffic source are those of
the touch session, so channel and date filters behave like they do for `fact_session`; `conversion_date_id` is the day
of the purchase (use it to report credit on the day it was earned). A channel with several sessions in a journey shares
its credit between them. Only sessions up to the user's last purchase session get credit (a later visit cannot have
caused it). The Direct channel is matched ignoring case. Time-Decay counts hours before that purchase session
(half-life 7 days), and Markov Chain splits each journey's credit between its distinct channels in proportion to their
removal effects.

`fact_basket`: one row per item pair, with `number_of_transactions`, `support_of_basket`, `confidence_of_first_item`, `confidence_of_second_item`, `lift` and `basket_value`. Pairs below `min_support` (0.002) are not stored: most pairs are almost never bought together and their lift is noise. Names in a pair are alphabetical. `confidence_of_second_item` is the share of baskets with the FIRST item that also hold the second (first -> second); `confidence_of_first_item` is the vice versa. `lift` = support of the pair / (support of first x support of second): above 1 means bought together more often than chance, below 1 means less often.

## Network tables

The co-occurrence network (`analytics/network.py`): items are nodes, an edge joins two items bought together, weight is
the number of baskets with both. Pairs bought together fewer than 4 times are dropped (the floor keeps 4 and above), then a disparity filter
(alpha 0.05) keeps the edges that are a surprisingly large share of one of their items' weight, and also every edge
with a co-occurrence of 8 or more (`min_degree`), so the filter does not cut the busy items and the network keeps its overall
structure. Louvain finds the communities. The network builds its own 0/1 (one-hot encoded) basket matrix from the purchase items.

| Table | Grain | Key | Notes |
|---|---|---|---|
| `dim_network_node` | one row per item in the final network | `item_name` | `community`, `degree`, `strength` (total co-occurrence), `betweenness`, `closeness`, `clustering`, `raw_degree` / `raw_strength` / `hub_rank` / `is_hub` (hubs are the busiest items in the network BEFORE filtering), `item_baskets`, `item_revenue`, `layout_x` / `layout_y` (a fixed position for drawing the network: communities placed first, then items inside each; x spans 0 to 2.9, y 0 to 1) |
| `dim_network_community` | one row per community | `community` | `community_title` (label plus its hub), size, `community_edges`, `bridge_edges` (edges to other communities), `density`, `total_cooccurrence`, `average_lift`, `community_items` |
| `fact_network_edge` | one row per edge | `network_edge_id` | `item_a` and `item_b` (alphabetical), `cooccurrence`, support, `confidence_a_to_b` and `confidence_b_to_a`, `lift`, `edge_alpha` (disparity p-value), `edge_betweenness`, `community_a`, `community_b`, `is_bridge` |
| `fact_network_stage` | one row per filtering step (pairs, floor, disparity) | `stage_order` | edges and items left after each step; `modularity` of each step's own graph on every row |

Betweenness and closeness treat a stronger link as a shorter distance (1 / co-occurrence).

## Bridges

| Table | Links | Notes |
|---|---|---|
| `bridge_event_item` | `fact_event.event_id` <-> `dim_item.item_id` | no primary key: an item can repeat within an event |
| `bridge_transaction_item` | `dim_transaction.transaction_id` <-> `dim_item.item_id` | purchased items whose name is `(not set)` are left out |

## Relationships for Power BI

Each fact joins the dimensions on the shared key name (`date_id`, `geo_id`, `device_id`, `traffic_source_id`,
`product_id` for the funnel, `item_id` for the bridges, `attribution_model_id` for attribution). `dim_item[product_id]` points at `dim_product`. Create relationships from dimension (one) to fact (many). `fact_user.first_active_date` and
`last_active_date` are date ids too, but are not constrained, so use inactive relationships if you need them.
The dimension tables carry primary keys and the facts carry foreign keys with indexes, so Power BI's
auto-detect should pick most of these up.
