# Output tables

All keys are integer surrogate keys unless noted. Key column names come from `DataSchema`.
Every fact carries `geo_id` and `device_id` (resolved per user) and, where listed, `traffic_source_id`.

## Dimensions

| Table | Grain | Key | Notes |
|---|---|---|---|
| `dim_date` | one row per calendar day seen in events | `date_id` (YYYYMMDD int) | day name, week, month, quarter, weekend flag |
| `dim_geo` | one row per distinct continent/country/region/city | `geo_id` | |
| `dim_device` | one row per distinct category/brand/model/OS/OS version | `device_id` | built from each user's first device |
| `dim_traffic_source` | one row per distinct source/medium/campaign/channel | `traffic_source_id` | channel comes from the channel rules |
| `dim_item` | one row per item (name) | `item_id` (item name) | brand, variant, category, highest price seen; `(not set)` excluded |
| `dim_transaction` | one row per purchase transaction | `transaction_id` | basket size, value, unique items, conversion timestamp |

## Facts

| Table | Grain | Key | Points at |
|---|---|---|---|
| `fact_event` | one row per event | `event_id` | date, geo, device, traffic source |
| `fact_item_funnel` | one row per user, session, day, item | `item_funnel_id` | date, geo, device, traffic source, item |
| `fact_session` | one row per session | `session_id` (text) | date, geo, device, traffic source |
| `fact_user` | one row per user | `user_pseudo_id` (text) | geo, device, traffic source (first session) |
| `fact_journey` | one row per user (all users) | `journey_id` | geo, device, traffic source |
| `fact_converting_journey` | one row per user with a conversion | `converting_journey_id` | geo, device, traffic source |
| `fact_basket` | one row per item and per item pair | `basket_id` | none (names in `antecedent` / `consequent`) |

`fact_item_funnel` flags (`is_viewed`, `is_added_to_cart`, `is_checked_out`, `is_purchased`) are back-filled:
reaching a later step implies the earlier ones.

`fact_basket`: `is_self_node = 1` rows describe a single item; others describe a pair. `community` is set only
for pairs with enough support and confidence (defaults: support >= 0.002, confidence >= 0.20 in either direction).

## Bridges

| Table | Links | Notes |
|---|---|---|
| `bridge_event_item` | `fact_event.event_id` <-> `dim_item.item_id` | no primary key: an item can repeat within an event |
| `bridge_transaction_item` | `dim_transaction.transaction_id` <-> item name | no item foreign key: GA4 can record `(not set)` |

## Relationships for Power BI

Each fact joins the dimensions on the shared key name (`date_id`, `geo_id`, `device_id`, `traffic_source_id`,
`item_id`). Create relationships from dimension (one) to fact (many). `fact_user.first_active_date` and
`last_active_date` are date ids too, but are not constrained, so use inactive relationships if you need them.
The dimension tables carry primary keys and the facts carry foreign keys with indexes, so Power BI's
auto-detect should pick most of these up.
