# Output tables

All keys are integer surrogate keys unless noted. Key column names come from `DataSchema`.
Every fact carries `geo_id` and `device_id` (resolved per user) and, where listed, `traffic_source_id`.

## Dimensions

| Table | Grain | Key | Notes |
|---|---|---|---|
| `dim_date` | one row per calendar day seen in events | `date_id` (YYYYMMDD int) | day name, week, month, quarter, weekend flag |
| `dim_geo` | one row per distinct continent/country/region/city | `geo_id` | |
| `dim_device` | one row per distinct category/brand/model/OS/OS version | `device_id` | built from each user's first device |
| `dim_traffic_source` | one row per distinct source/medium/campaign/channel | `traffic_source_id` | `channel` is the detailed label from the channel rules; `channel_group` collapses small channels for charts (`enrichment/channel_groups.py`) |
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
| `fact_attribution` | one row per session in a converting journey, per model (zero-credit rows are left out) | `attribution_id` | date (of the touch session), geo, device, traffic source (of the touch session), model, converting journey, session |
| `fact_basket` | one row per item and per item pair | `basket_id` | none (names in `antecedent` / `consequent`) |

`fact_item_funnel` flags (`is_viewed`, `is_added_to_cart`, `is_checked_out`, `is_purchased`) are back-filled:
reaching a later step implies the earlier ones. The funnel is per product because views often carry no variant;
for variant mix use `bridge_transaction_item` with `dim_item`.

`fact_attribution`: `credit` is the session's share of its journey (the shares of one model add up to 1 per journey);
`revenue_credit` is `credit` times the journey's revenue. Always filter to ONE model (or put the model in a legend),
because adding up several models counts the same revenue several times. The date and traffic source are those of the
touch session, so channel and date filters behave like they do for `fact_session`. A channel with several sessions in a
journey shares its credit between them. Time-Decay counts hours before the journey's last session (half-life 7 days),
and Markov Chain splits each journey's credit between its distinct channels in proportion to their removal effects.

`fact_basket`: `is_self_node = 1` rows describe a single item; others describe a pair. `community` is set only
for pairs with enough support and confidence (defaults: support >= 0.002, confidence >= 0.20 in either direction).

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
