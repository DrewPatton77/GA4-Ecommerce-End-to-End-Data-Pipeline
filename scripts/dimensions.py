'''
Script showing how to run the dimensions module.
'''

from __future__ import annotations

import logging

import polars as pl
import pandas as pd

# Change True to False to turn of logging.
if True:
    logging.basicConfig(
        level=logging.INFO,  # Change to DEBUG for more verbose output
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# ==== Sources ===========================================
# See `source.py` in /scripts/. 
from ga4_ecommerce_analytics_engine.sources.bigquery_source import BigQuerySource

START_DATE = "2020-11-01" # Start of the dataset. Can be any date as long as it's before the end date.
END_DATE = "2021-01-31" # End of the dataset.
src = BigQuerySource()

# ==== # **FIX THIS ** Should make the validation implicity =========
columns = src.validate_columns(start_date=START_DATE, end_date=END_DATE) 
# ==== # **FIX THIS ** Should make the validation implicity =========

raw_data = src.fetch_all(START_DATE, END_DATE)


# ==== Cleaning =========================================
from ga4_ecommerce_analytics_engine.cleaning.transactions import DataCleaner

cleaner = DataCleaner()
cleaned_data = cleaner.clean_transactions(raw_data.events, raw_data.items, composition_key=False)

# ==== Enrichment  =======================================

# --- UTM classification and aggregation
from ga4_ecommerce_analytics_engine.enrichment.utm import DataUtm
utmer = DataUtm()
utm_data = utmer.enrich_events_with_utm(cleaned_data.events)


# --- Channel classification -------------------------------
from ga4_ecommerce_analytics_engine.enrichment.channels import DataChannelClassifier
channel_classifier = DataChannelClassifier()
sessions_channel = channel_classifier.classify(utm_data.sessions)

# --- Session & Journey Aggregation
from ga4_ecommerce_analytics_engine.aggregation.sessions import SessionBuilder
from ga4_ecommerce_analytics_engine.aggregation.journeys import JourneyBuilder

session_builder = SessionBuilder()
sessions = session_builder.build(utm_data.events, sessions_channel)

journey_builder = JourneyBuilder()
results = journey_builder.build(sessions)
journeys = results.journeys
conversion_journeys = results.converting

# --- Building dimension relational tables ------------------------

# date
from ga4_ecommerce_analytics_engine.dimensions.date import DateDimension
date_dimension_builder = DateDimension()
date_dimension_table = date_dimension_builder.build(utm_data.events)

# device
from ga4_ecommerce_analytics_engine.dimensions.device import DeviceDimension
device_dimension_builder = DeviceDimension()
device_dimension_table = device_dimension_builder.build(raw_data.dimensions)

# geography
from ga4_ecommerce_analytics_engine.dimensions.geo import GeoDimension
geo_dimension_builder = GeoDimension()
geo_dimension_table = geo_dimension_builder.build(raw_data.dimensions)

# items
from ga4_ecommerce_analytics_engine.dimensions.items import ItemDimension
item_dimension_builder = ItemDimension()
item_dimension_table = item_dimension_builder.build(cleaned_data.items)

# transactions
from ga4_ecommerce_analytics_engine.dimensions.items import TransactionDimension
transaction_dimension_builder = TransactionDimension()
transaction_results = transaction_dimension_builder.build(utm_data.events, cleaned_data.items)
transaction_dimension_table = transaction_results.transactions
transaction_item_bridge_table = transaction_results.transaction_items

# traffic source
from ga4_ecommerce_analytics_engine.dimensions.traffic_source import TrafficSourceDimension
traffic_source_dimension_builder = TrafficSourceDimension()
traffic_source_results = traffic_source_dimension_builder.build_with_mappings(sessions)
traffic_source_dimension_table = traffic_source_results.dimension
traffic_source_session_bridge_table = traffic_source_results.session_mapping
traffic_source_user_bridge_table = traffic_source_results.user_mapping

print("Date Dimension Table:")
print(date_dimension_table)

print("Device Dimension Table:")
print(device_dimension_table)

print("Geography Dimension Table:")
print(geo_dimension_table)

print("Item Dimension Table:")
print(item_dimension_table)

print("Transaction Dimension Table:")
print(transaction_dimension_table)

print("Transaction-Item Bridge Table:")
print(transaction_item_bridge_table)

print("Traffic Source Dimension Table:")
print(traffic_source_dimension_table)

print("Traffic Source-Session Bridge Table:")
print(traffic_source_session_bridge_table)

print("Traffic Source-User Bridge Table:")
print(traffic_source_user_bridge_table)