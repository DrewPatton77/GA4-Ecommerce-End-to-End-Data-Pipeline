# GA4 Ecommerce Analytics Report

Nov 4, 2026

## Executive summary

Between 1 Nov 2020 and 25 Jan 2021 the Google Merchandise Store turned 338K sessions into 5,192 purchases and $358K of revenue; the biggest openings are checkout drop-off, an unclassified third of traffic and an under-used referral channel.

|                  |                                        |
| ---------------- | -------------------------------------- |
| Metric           | Value                                  |
| Sessions         | 338K                                   |
| Purchases        | 5,192 (about 1.5% of sessions)         |
| Journeys         | 254K, of which 4.02K converted (1.59%) |
| Revenue          | $358K, about $69 per purchase          |
| Product views    | 1.06M                                  |
| View to cart     | 25.4%                                  |
| Cart to purchase | 5.05%                                  |

The five findings, each with an action:

1. **A third of sessions (33.6%) have no channel** and convert at 0.1%, so channel results cover only two thirds of traffic.
2. **Referral converts best**: 4.5% of sessions and about $4 of revenue per session, on only 20K sessions.
3. **Checkout is the biggest leak**: 92% of add-to-carts never reach checkout.
4. **Revenue is concentrated in higher-priced products**: 121 products make 80% of revenue, and the strongest basket pairs are natural bundles.
5. **Weekdays outsell weekends** (Wednesday about $63K against Sunday about $28K), and sales peak in early December.

The analysis stops at 25 Jan 2021, because the source loses purchase revenue from 26 Jan (see Context and data).

## Context and data

The data is Google's public GA4 sample ecommerce dataset from the Google Merchandise Store, covering 1 Nov 2020 to 31 Jan 2021 (92 days), and it is obfuscated by Google.

A pipeline builds the report in four steps: BigQuery extracts the events, polars cleans and aggregates them, the result is loaded into a PostgreSQL star schema (22 tables), and a seven-page Power BI report reads it. The pipeline and every module are documented in the project repository.

**Data quality.** From 26 Jan 2021 the source sends many purchase events without a transaction id or revenue. A purchase with no revenue cannot be counted, so it is dropped and nothing is filled in. This report therefore covers 1 Nov 2020 to 25 Jan 2021 (85 days).

|   |   |   |   |   |   |   |   |
|---|---|---|---|---|---|---|---|
|Date (Jan 2021)|25|26|27|28|29|30|31|
|Purchases with no revenue|5%|38%|78%|86%|75%|70%|100%|

Before 26 Jan the share is 1% to 5% a day. Revenue falling at the end of January is a data effect, likely pointing to issues with the website tracking that needed to be fixed.

## Findings

### 1. A third of traffic has no channel

Unclassified sessions are 33.6% of all sessions (113K) and convert at 0.1%, so channel conclusions rest on the other two thirds of traffic. These sessions are genuinely unclassified: no source, medium or campaign rule matches them.

|   |   |   |   |   |
|---|---|---|---|---|
|Channel group|Sessions|Conversion rate|Revenue|Revenue per session|
|Direct|92K|1.7%|$140K|$2|
|Organic search|92K|1.6%|$112K|$1|
|Referral|20K|4.5%|$75K|$4|
|Non-marketing|11K|2.1%|$16K|$1|
|Unclassified|113K|0.1%|$9K|under $1|

**Action:** report channel results as "for classified traffic", and mark the unclassified share as a measurement gap to fix for better tracking.

### 2. Referral is the best-converting large channel

Referral sessions convert at 4.5%, about three times the 1.6% to 1.7% of direct and organic search, and earn about $4 per session against $1 to $2. Referral is only 6% of sessions. Direct and organic search receive the most credit under all eight attribution models, with referral next.

**Action:** grow referral partnerships and test them with a small budget, then compare against organic search growth.

### 3. Checkout is the biggest leak in the funnel

25.4% of product views end in an add-to-cart, but 92% of add-to-carts never reach checkout. Once a shopper starts checkout, 66% go on to buy.

|   |   |   |
|---|---|---|
|Stage|Count|Lost from the previous stage|
|Product views|1.06M||
|Add to cart|268K|75% of views|
|Begin checkout|20.7K|92% of add-to-carts|
|Purchase|13.6K|34% of checkouts|

**Action:** test earlier shipping-cost display, guest checkout and cart reminders. Treat the 92% as an upper bound, since checkout events can be under-recorded in the sample.

### 4. Revenue sits in higher-priced products, and baskets suggest bundles

121 products make 80% of revenue. Items under $10 are about 38% of products but about 9% of revenue, while items from $50 to $100 are about 8% of products and about 31% of revenue.

The basket analysis covers 5K transactions and 171 item pairs above the support cut-off, and 162 of them are bought together more often than chance. The strongest pair is the Kirkland Mug with the Seattle Mug (lift 70.5x), and city-matched mugs, stickers and Android collectibles dominate the top ranked. By volume, pens pair most often: Metallic Notebook Set with Pen (44 transactions) and Clear Pen 4-Pack with Pen (38). Sweatshirts with pens are the clearest pair that is bought together less than chance (lift 0.4x).

The item network groups 191 items into 27 communities (with a modularity of 0.67), so the pairs form real buying groups and not isolated coincidences.

**Action:** test bundles built from the strongest pairs, and feature $50 to $100 items on the pages that already convert.

### 5. Weekdays outsell weekends, and December is the peak

|   |   |
|---|---|
|Weekday|Revenue|
|Wednesday|$63K|
|Monday|$62K|
|Tuesday|$59K|
|Friday|$58K|
|Thursday|$51K|
|Saturday|$37K|
|Sunday|$28K|

Daily revenue peaks near $10K in early December and falls to $2K to $3K a day in January, which fits holiday gifting.

**Action:** schedule campaigns and email sends for the middle of the week, and plan stock and promotions around the early-December peak. Email campaigns also earn the most revenue per conversion, though not the most in total, so they are worth keeping.

### Journey behaviour

Most shoppers decide quickly. Of 254K journeys, about 82% have a single touchpoint, and about 25% of converting journeys also have one. About 30% of converting journeys complete within the first hour. The most common conversion path is a single Organic Search visit (495 purchases), then a single Referral visit (251) and a single Direct visit (158). It is also worthy to note that conversions increase at around the 30 day mark, but taper off afterwards.

**Action:** put effort into the landing and first-visit experience, because most purchases happen in the first session. In addition, re-engage customers between the 20-30 day mark by sending reminders.

## Recommendations

Fix checkout first: it is the largest leak and the cheapest to test. Each action below names the measure that would show whether it worked.

|   |   |   |   |   |
|---|---|---|---|---|
|Priority|Action|Why|Effort|Measure of success|
|1|Test checkout changes: shipping cost shown earlier, guest checkout, cart reminders|92% of add-to-carts never reach checkout|Medium|Cart-to-purchase rate (now 5.05%)|
|2|Test bundles from the strongest item pairs|Pairs bought together up to 70 times more than chance; pens pair with many items|Low|Items per order, revenue per order (now about $69)|
|3|Grow referral partnerships|4.5% conversion and about $4 per session, on 6% of sessions|Medium|Referral sessions and revenue share|
|4|Shift campaigns and emails to midweek, and plan for the early-December peak|Wednesday revenue is about 2.3 times Sunday's|Low|Revenue per campaign day|
|5|Improve the first-visit experience|About 82% of journeys have one touchpoint, and 30% of converting journeys finish within an hour|Medium|First-session conversion rate|
|6|Track and shrink the unclassified share|33.6% of sessions have no channel and convert at 0.1%|Low|Unclassified share of sessions (now 33.6%)|

## Limitations and next steps

These findings describe one store over 85 days of obfuscated sample data, so treat them as directions to test, not proof of cause.

- **Short, partial period.** The data covers about three months and loses revenue from 26 Jan, so seasonal claims rest on a single holiday season.
- **Unclassified traffic.** A third of sessions have no channel, so channel and attribution results describe the classified two thirds only.
- **Attribution is a set of assumptions.** The eight models share each purchase's value differently and none measures cause. Credit only goes to sessions up to the user's last purchase.
- **Checkout counts.** Checkout events can be under-recorded in the sample, so the 92% drop is an upper bound.
- **Basket cut-off.** Pairs seen in fewer than about 10 baskets are dropped, which favours pairs with lift above 1. Network groups depend on filter settings and community numbers can change between runs.
- **Observation, not experiment.** Every action above needs an A/B test before it is treated as a result.

**Next steps:** run the checkout and bundle tests, extend the data past January if a complete source is available, and investigate what the unclassified sessions have in common.

## Appendix

All figures come from the Power BI report built on the project's PostgreSQL star schema, for 1 Nov 2020 to 25 Jan 2021. Full definitions are in the repository's `docs/` folder.

|   |   |
|---|---|
|Term|Definition|
|Session conversion|Sessions with a purchase divided by all sessions|
|Journey conversion|Users with a purchase divided by all users with a journey (1.59%)|
|Attribution models|First-click, last-click, last non-direct click, linear, position-based (40% first, 40% last, 20% middle), time-decay (7-day half-life), Shapley value (from cooperative game theory: a channel's credit is its average marginal contribution to conversion across every order in which the channels of a journey could be added; this project approximates it as equal credit to each distinct channel in the journey) and Markov chain (credit by each channel's removal effect)|
|Lift|How much more often a pair is bought together than chance predicts; above 1 means more often|
|Network|Items are nodes, and a link means two items were bought together unusually often; Louvain finds the communities and modularity says how clearly they separate (above 0.3 is clear)|
|Unclassified|A session whose source, medium and campaign match no channel rule|

Repository documents: `docs/tables.md` (every output table), `docs/analytics.md` (attribution, basket and network methods), `docs/powerbi.md` (report setup and measures) and `docs/modules.md` (a flowchart for each module).