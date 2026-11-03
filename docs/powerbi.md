# Power BI setup

## Connect

1. Run `make db-up`, then `make run-pg`.
2. In Power BI choose **Get data > PostgreSQL**, enter `<host>:<port>` and database `ga4`, and import the tables.

## Relationships

Turn **Autodetect relationships off** (Options > Current file > Data load) and create them by hand, one to many,
single direction, from the dimension to the fact:

| From (one) | To (many) |
|---|---|
| `dim_date[date_id]` | every fact's `date_id` |
| `dim_geo[geo_id]` | every fact's `geo_id` |
| `dim_device[device_id]` | every fact's `device_id` |
| `dim_traffic_source[traffic_source_id]` | facts that carry it |
| `dim_product[product_id]` | `fact_item_funnel[product_id]`, `dim_item[product_id]` |
| `dim_date[date_id]` | `fact_attribution[conversion_date_id]` (**inactive**: use `USERELATIONSHIP` to report by purchase date) |
| `dim_attribution_model[attribution_model_id]` | `fact_attribution[attribution_model_id]` |
| `dim_transaction[transaction_id]` | `bridge_transaction_item[transaction_id]` |
| `dim_item[item_id]` | `bridge_transaction_item[item_id]` |
| `dim_network_community[community]` | `dim_network_node[community]` |
| `dim_network_community[community]` | `fact_network_edge[community_a]` (active) |
| `dim_network_community[community]` | `fact_network_edge[community_b]` (inactive) |

`fact_user[first_active_date]` and `[last_active_date]` are date ids but unconstrained: use inactive relationships.
`fact_basket` has no relationships: it is a plain table of item pairs.

## Pages

Seven pages, in this order, with a page navigator rail of icons (Home, Daily, Marketing, Journeys, Products, Basket, Network) on the left with one theme.

| Page | Question | Main visuals |
|---|---|---|
| Home | Where do I start? | Four headline cards and one card per page that opens it |
| Daily | How did each day go? | KPI cards against the 7-day average, daily revenue with previous day and 7-day average, biggest movers table, calendar matrix, day-of-week bars |
| Marketing | Which channels bring quality traffic? | Channel scorecard, volume vs quality scatter, session mix by week, attribution by model, channel by device |
| Journeys | How many touchpoints and how long before someone buys? | Journeys and converted journeys by touchpoints and by duration (log-spaced bins), average conversion revenue, top conversion paths |
| Products | Which products convert and where do shoppers drop off? | Product funnel, conversion scatter, Pareto of revenue, product table, price bands |
| Basket | Which items are bought together more than chance? | Support vs lift scatter, best and worst pairs, pair table, lift bands |
| Network | Which items form buying groups and which connect them? | Deneb network, hubs and connectors scatter, stage chart, communities and strongest links tables |

Import `theme/ga4_dark_cards_v2.json` (or `ga4_dark_transparent_v2.json`) with **View > Themes > Browse for themes**.
Both style the filter pane (`outspacePane`, `filterCard`) so slicer text is readable on the dark background.

**Daily page.** The KPI cards compare the selected day with its 7-day average, because the data has no earlier
period to compare with. Previous day and the 7-day average are measures built on the date table (`DATEADD` and
`DATESINPERIOD`). The biggest-movers table lists dates, not products, ranked by revenue against the 7-day average.

## Credit by purchase date

`fact_attribution[date_id]` is the day of the touch. To report credit on the day of the purchase, use the inactive
relationship:

```
Revenue credit by purchase date =
CALCULATE(SUM(fact_attribution[revenue_credit]), USERELATIONSHIP(dim_date[date_id], fact_attribution[conversion_date_id]))
```

## The network visual (Deneb)

The Network page draws the graph with the Deneb custom visual (Vega), from saved positions (`layout_x`, `layout_y`
in `dim_network_node`), so it looks the same every time and supports pan, zoom (mouse wheel) and double-click to reset.

1. Add the twelve calculated columns in [network_edge_columns.dax](network_edge_columns.dax) to `fact_network_edge`
   one at a time (**Table view > fact_network_edge > New column**). They copy each end's attributes onto the edge row.
2. Add a Deneb visual and put these fields in it, each set to **Don't summarize**: `item_a`, `item_b`, `cooccurrence`,
   `is_bridge`, `community_a`, `community_b`, `hub_a`, `hub_b`, `strength_a`, `strength_b`, `label_a`, `label_b`,
   `title_a`, `title_b`, `x_a`, `y_a`, `x_b`, `y_b`.
3. Paste [network_deneb_spec.json](network_deneb_spec.json) into the Vega editor and apply it. The dataset must be
   named `dataset` (the default).
4. To quiet the links, lower the `strokeOpacity` values in the edge `rule` mark (gold bridge links first), or thin the
   lines by lowering the top of the `ew` scale's range.

## Refreshing without losing measures

Use **Home > Refresh**. If a new column or table does not show up, open **Transform data**, select its query and click
**Refresh Preview**; check that the Source step lists the table. Measures live in the model, so they survive a refresh.
Do not import a table a second time, or Power BI creates a copy named `table (2)`.

## Measure patterns

- **One model only:** `IF(HASONEVALUE(dim_attribution_model[attribution_model]), SUM(fact_attribution[revenue_credit]))`
- **Pareto:** rank with `RANKX(ALLSELECTED(...), [Revenue])` and a cumulative sum over `ALLSELECTED`.
- **Bridges:** use `CROSSFILTER` to filter across a bridge in one measure instead of making the relationship bidirectional.
- **Totals that ignore a slicer:** `REMOVEFILTERS(table[column])`.
- **Home page cards:** make each figure a measure (pairs analysed, pairs above chance, communities, journeys, days in
  the period), so the card and the page it opens always agree.

## Performance

Measured with Performance Analyzer in Power BI Desktop (import mode, other apps running): Home 0.3 s, Daily 0.8 s,
Marketing and Journeys about 1 s, Basket 1.3 s, Network 1.4 s, Products about 4 s. Products has the most visuals
(three list slicers and five cards); using dropdown slicers and one multi-value card cuts it. In the browser the
pages open about instantly.

## Data quality on the report

The last days of the period have purchases with no revenue in the source data (see the README, Data quality), so
revenue, purchases and attributed credit fall from 26 Jan and are zero on 31 Jan. Keep the note on the Daily page, or
end the date range at 25 Jan.
