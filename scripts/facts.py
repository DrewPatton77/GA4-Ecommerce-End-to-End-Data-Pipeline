'''
Script showing how to run the facts module.
'''

from __future__ import annotations

import logging

import polars as pl
import pandas as pd
import numpy as np

from ga4_ecommerce_analytics_engine.schema import DataSchema

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
columns = src.validate_columns(start_date=START_DATE, end_date=END_DATE) 
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
sessions_channel = channel_classifier.grouping(channel_classifier.classify(utm_data.sessions))


# ===== Session & Journey Aggregation ==========================
from ga4_ecommerce_analytics_engine.aggregation.sessions import SessionBuilder
from ga4_ecommerce_analytics_engine.aggregation.journeys import JourneyBuilder

session_builder = SessionBuilder()
sessions = session_builder.build(utm_data.events, sessions_channel)

journey_builder = JourneyBuilder()
results = journey_builder.build(sessions)
journeys = results.journeys
conversion_journeys = results.converting

# === Relational Fact Table Building =====================================

# events
from ga4_ecommerce_analytics_engine.facts.events import (EventFacts, EventItemBridge)
event_fact_builder = EventFacts()
events = event_fact_builder.add_event_ids(cleaned_data.events)
event_fact_table = event_fact_builder.build(events)
event_item_builder = EventItemBridge()
event_item_bridge_table = event_item_builder.build(events, cleaned_data.items)

# item-funnel
from ga4_ecommerce_analytics_engine.facts.item_funnel import ItemFunnelFacts
item_funnel_fact_builder = ItemFunnelFacts()
item_funnel_fact_table = item_funnel_fact_builder.build(cleaned_data.items)

# journeys
from ga4_ecommerce_analytics_engine.facts.journeys import JourneyFacts
journey_fact_builder = JourneyFacts()
journey_fact_results = journey_fact_builder.build(journeys, conversion_journeys)
journey_fact_table = journey_fact_results.journeys
conversion_journeys_fact_table = journey_fact_results.converting

# Sessions
from ga4_ecommerce_analytics_engine.facts.sessions import SessionFacts
session_fact_builder = SessionFacts()
session_fact_table = session_fact_builder.build(sessions)

# Users
from ga4_ecommerce_analytics_engine.facts.users import UserFacts
user_fact_builder = UserFacts()
user_fact_table = user_fact_builder.build(sessions)


print('Event Fact Table:')
print(event_fact_table)

print('Event-Item Bridge Table:')
print(event_item_bridge_table)

print('Item-Funnel Fact Table:')
print(item_funnel_fact_table)

print('Journey Fact Table:')
print(journey_fact_table)

print('Conversion Journeys Fact Table:')
print(conversion_journeys_fact_table)

print('Session Fact Table:')
print(session_fact_table)

print('User Fact Table:')
print(user_fact_table)