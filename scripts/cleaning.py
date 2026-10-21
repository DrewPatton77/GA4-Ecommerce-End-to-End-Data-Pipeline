'''
Script showing how to run the cleaning module.
'''

from __future__ import annotations

import logging

import polars as pl

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

### --- Cleaner --------------------------------
# Initialize the cleaner object
cleaner = DataCleaner()

# Main function that combines everything
cleaned_data = cleaner.clean_transactions(raw_data.events, raw_data.items, composition_key=False)

'''
 Data can be accessed using: cleaned_data.name, where <name> is the name of the sql file (without the .sql).
 for example,

 - raw_data.events, returns the events data as a polars dataframe.
 - raw_data.items, returns the items dataframe.
 - raw_data.dimensions, returns the dimensions dataframe.
'''
print('\n Events DataFrame Cleaning...')
n_before = raw_data.events.height
print(f"Rows before cleaning: {n_before}")
n_after = cleaned_data.events.height
print(f"Rows after cleaning : {n_after} (dropped: {n_before - n_after} | {round((n_before - n_after) / n_before * 100, 2)}%)")

print('\n Items DataFrame Cleaning...')
n_before = raw_data.items.height
print(f"Rows before cleaning: {n_before}")
n_after = cleaned_data.items.height
print(f"Rows after cleaning : {n_after} (dropped: {n_before - n_after} | {round((n_before - n_after) / n_before * 100, 2)}%)\n")



# - Main function is made up of these methods:

# normalize timestamps to Datetime
raw_events = cleaner.normalize_timestamps(raw_data.events)
raw_items = cleaner.normalize_timestamps(raw_data.items)

# add a composition key
raw_events = cleaner.add_composite_session_id(raw_events)
raw_items = cleaner.add_composite_session_id(raw_items)

# grab the purchase events, since this contains the transaction data
purchase_items = cleaner.extract_purchase_items(raw_items)

# Fix the transaction_id with its own composite key rather than using GA4's, since it breaks.
purchase_items = cleaner.add_transaction_id(purchase_items)

# deduplicate the transactions by taking only the first unique.
purchase_items = cleaner.deduplicate_items(purchase_items)

# Aggregrate from the items-level scope to the events-level scope 
# and make this the new events transaction rows
purchase_events = cleaner.aggregate_items_to_events(purchase_items, raw_events)

# concatenate the aggregated items-to-event level scope with the non-purchase
# events to create a single events dataframe with now no duplicated transactions.
events = cleaner.merge_purchases_into_events(raw_events, purchase_events)

# Same with the items, concatenate the deduplicated items to the non-purchase raw items.
items = cleaner.rebuild_items(raw_items, purchase_items)




