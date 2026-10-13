from src.ga4_ecommerce_analytics_engine.constants import GCP_PROJECT_ID
from pandas import PeriodDtype
from google.cloud import bigquery

class BigQuery:

    def __init__(self, start_date, end_date) -> None:
        self.query: str | None = None
        self.df: pd.DataFrame | None = None
        self.start_date: str = start_date
        self.end_date: str = end_date

    