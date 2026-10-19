'''
Script showing how to run the analytics module.
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

# ==== Analysis ===========================================
from ga4_ecommerce_analytics_engine.analytics.basket import BasketAnalyzer
basket_analyzer = BasketAnalyzer()
basket_analysis = basket_analyzer.build(cleaned_data.items)

print("Basket Analysis:")
print(basket_analysis)