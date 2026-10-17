'''
Script showing how to run the enrichment module.
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


# --- Extra: Summary ------------------------------------------------

print("\n---- Session UTMs Summary: -----------------------------")
sessions_UTM = utm_data.sessions.to_pandas()
source_counts = sessions_UTM['source_utm'].value_counts()
medium_counts = sessions_UTM['medium_utm'].value_counts()
campaign_counts = sessions_UTM['campaign_utm'].value_counts()
print(f"\nNumber of unique UTM sources  : {len(source_counts)}")
print(f"Number of unique UTM mediums  : {len(medium_counts)}")
print(f"Number of unique UTM campaigns: {len(campaign_counts)}")
print('---')
print('\nUnique UTM mediums:')
print(medium_counts)
print('\nUnique UTM campaigns:')
print(campaign_counts)

print("\n ---- Session Channel Summary: --------------------------")
print(f"\n{sessions_channel.height} rows x {sessions_channel.width} columns")
sessions_channel = sessions_channel.to_pandas()
print("\nSessions with a channel column:")
print(sessions_channel.head(5))
print('\n Number and percent of channels')
channel_summary = sessions_channel['channel'].value_counts().reset_index()
channel_summary['percent of sessions'] = (channel_summary['count'] / channel_summary['count'].sum() * 100).round(2).astype(int).astype(str) + '%'
print(channel_summary)
print(f"\n {sessions_channel.shape}")