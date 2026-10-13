import os
from google.cloud import bigquery
from dotenv import dotenv_values

config = dotenv_values(".env")

class BigQueryClient:

    def __init__(self):
        self.PROJECT_ID: str = config['GCP_PROJECT_ID'] # The Google Cloud Platform Project ID.
        self.USD_TO_CAD_EXCHANGE_RATE: str = config['USD_TO_CAD_EXCHANGE_RATE'] # Subject to change.
        self.ONDEMAND_PRICING: str = config['ONDEMAND_PRICING'] # The standard pricing for a bigquery scan at 1TB.
        self.MAXIMUM_BYTES_BILLED: int = config['MAXIMUM_BYTES_BILLED'] # Safety cap.
        
    def estimate_cost(self, query):
        '''
        Calculates the cost of a query from Google Cloud Platform's BigQuery.

        Parameters:
            - query
                - type: str
                - desc: The SQL query to be dry ran for an estimated cost.
        
        Returns:
            - cost
        '''
        client = bigquery.Client(project=self.PROJECT_ID) # Initialize the client.
        job_config = bigquery.QueryJobConfig(dry_run=True) # Set dry_run=True.
        result = client.query(query, job_config=job_config) # Dry run the query and waits for query to finish.
        bytes_scanned = result.total_bytes_processed # Calculates the bytes that were scanned.
        cost_usd = (bytes_scanned / 1e12) * self.ONDEMAND_PRICING # ~$6.25 USD per TB on-demand. (See: https://cloud.google.com/bigquery/pricing#on-demand-compute-pricing).
        cost_cad = cost_usd * self.USD_TO_CAD_EXCHANGE_RATE # $1 USD ~ $1.42 CAD.

        bytes_scanned /= 1e9
        return bytes_scanned, cost_cad
