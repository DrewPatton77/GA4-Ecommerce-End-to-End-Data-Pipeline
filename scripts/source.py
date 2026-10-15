'''
Script showing how to run the sources module.
'''

from __future__ import annotations

import logging

import polars as pl

from ga4_ecommerce_analytics_engine.sources.bigquery_source import BigQuerySource

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbose output
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

START_DATE = "2020-11-01" # Start of the dataset. Can be any date as long as it's before the end date.
END_DATE = "2021-01-31" # End of the dataset.
src = BigQuerySource() # Initialize the BigQuerySource object.

cost_estimates = src.estimate_cost(start_date=START_DATE, end_date=END_DATE) # returns the BigQuery cost of all the SQL queries as an object.
columns = src.validate_columns(start_date=START_DATE, end_date=END_DATE)

# If costs look good, then it will run. The budget can be set in the config under: MAXIMUM_BYTES_BILLED (which is in units of gigabytes).
raw_data = src.fetch_all(START_DATE, END_DATE) # Returns a RawData object containing the SQL queries ran.

'''
 Data can be accessed using: raw_data.name, where <name> is the name of the sql file (without the .sql).
 for example,

 - raw_data.events, returns the events data as a polars dataframe.
 - raw_data.items, returns the items dataframe.
 - raw_data.dimensions, returns the dimensions dataframe.
'''
print(raw_data.events)