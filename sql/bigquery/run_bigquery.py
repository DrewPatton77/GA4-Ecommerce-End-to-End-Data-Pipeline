from src.ga4_ecommerce_analytics_engine.config import GCP_PROJECT_ID
from pandas import pd
from google.cloud import bigquery

class BigQuery:

    def __init__(self, start_date, end_date) -> None:
        self.query: str | None = None
        self.df: pd.DataFrame | None = None
        self.start_date: str = start_date
        self.end_date: str = end_date

    def get_cost(self) -> None:
        '''
        Calculate the cost of a query from google cloud bigquery.

        Parameters:
            - None
        
        Returns: 
            - None
        '''

        client = bigquery.Client(project=GCP_PROJECT_ID) # Initialize the client using google cloud.
        job_config = bigquery.QueryJobConfig(dry_run=True) # Set dry_run=True
        result = client.query(self.query, job_config=job_config) # Dry run the query and waits for query to finish.
        bytes_scanned = result.total_bytes_processed # Calculate the bytes that were scanned.
        cost_usd = (bytes_scanned / 1e12) * 6.25 # ~$6.25 USD per TB on-demand. (See:  https://cloud.google.com/bigquery/pricing#on-demand-compute-pricing).
        cost_cad = cost_usd * 1.42 # 1 usd ~ 1.38 cad. Subject to change as of Aug.20th, 2026. --> Rough estimate costs.
        print(f"Bytes_scanned: {bytes_scanned / 1e9:.2f} GB | Cost: ~${cost_cad:.4f} CAD.")

    def run_query(self) -> pd.DataFrame:
        '''
        Run a query on the Google Cloud Platform BigQuery dataset and transform it to a pandas dataframe.

        Parameters:
            - None

        Returns:
            - df: A pandas DataFrame.
        '''

        client = bigquery.client(project=GCP_PROJECT_ID) # Initialize the client using google cloud.
        df = client.query(self.query).to_dataframe() # Run query and wait for it to finish. Transform BigQuery SQL to pandas DataFrame.
        return df
