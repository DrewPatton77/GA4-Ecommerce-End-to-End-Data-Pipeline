'''
Script showing how to run the enrichment module.
'''

from __future__ import annotations

import logging

import polars as pl
import pandas as pd
import numpy as np

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
from ga4_ecommerce_analytics_engine.aggregating.sessions import SessionBuilder
from ga4_ecommerce_analytics_engine.aggregating.journeys import JourneyBuilder

session_builder = SessionBuilder()
sessions = session_builder.build(utm_data.events, sessions_channel)

journey_builder = JourneyBuilder()
results = journey_builder.build(sessions)
print(results)
sessions = sessions.to_pandas()
print(sessions.columns)

print("==========Session Summary==========")
print(f"Number of sessions in the dataset: {sessions.shape[0]}")
print(f"Average number of session per day: {int(sessions.shape[0] / 92)}")
print(f"Number of users in the dataset   : {sessions['user_pseudo_id'].nunique()}")
print(f"Number of conversions            : {sessions['conversions_in_session'].sum().astype(int)}")
print(f"Percent of sessions that convert : {round(sessions['conversions_in_session'].sum() / sessions.shape[0] * 100, 2)}%")
print(f"Number of unique converters      : {sessions[sessions['converted'].eq(1)]['user_pseudo_id'].nunique()}")
print(f"Average conversions per day      : {int(sessions['conversions_in_session'].sum() / 92)}")
print('\n')

print("=========Engagement Summary========")
print(f"Average time engaged per session : {round(sessions['engagement_time'].mean() / 1000 / 60, 2)} minutes")
print(f"Number of sessions engaged       : {sessions['session_engaged'].sum()}")
print(f"Percent of sessions engaged      : {round(sessions['session_engaged'].sum() / sessions.shape[0] * 100, 2)}%")
print('\n')

print("=========Ecommerce Summary=========")
print(f"Total revenue                    : ${sessions['value'].sum().astype(int)}")
print(f"Average revenue per session      : ${sessions['value'].mean().astype(int)}")
print(f"Total items bought               : {sessions['quantity'].sum().astype(int)}")
print(f"Average items bought per sesison : {int(np.ceil(sessions['quantity'].mean()))}")
print('\n')


print("=========Channel Summary===========")
channel_summary = sessions.groupby('channel').agg(
    sessions = ('user_pseudo_id', 'count'),
    conversions = ('conversions_in_session', 'sum'),
    revenue = ('value', 'sum'),
    
)
channel_summary['percent of data'] = (channel_summary['sessions'] / channel_summary['sessions'].sum() * 100).round(2).astype(int).astype(str) + '%'
print(channel_summary.sort_values('sessions', ascending=False))

print("\n Sessions:")
print(sessions.head())
