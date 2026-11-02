from ga4_ecommerce_analytics_engine.sources.bigquery_source import BigQuerySource
start_date = '2020-11-01'
end_date = '2021-01-31'
source = BigQuerySource()
raw = source.fetch_all(start_date, end_date)

from ga4_ecommerce_analytics_engine.cleaning.transactions import DataCleaner
cleaner = DataCleaner()
clean = cleaner.clean_transactions(raw.events, raw.items)

from ga4_ecommerce_analytics_engine.analytics.basket import BasketAnalyzer
basket_analyzer = BasketAnalyzer()
basket = basket_analyzer.build(clean.items)

from ga4_ecommerce_analytics_engine.analytics.network import CooccurrenceNetwork
import networkx as nx
network_builder = CooccurrenceNetwork()
matrix, counts, names = network_builder.create_basket_matrix(clean.items)
G = network_builder.create_basket_graph(counts, names)
G_pruned = network_builder.prune(G)
scored_G = network_builder.disparity_filter(G_pruned)
G_backbone = network_builder.extract_backbone(scored_G)

results = network_builder.build(clean.items)

print(results)