from src.ga4_ecommerce_analytics_engine.constants import DATASET, TABLE
from run_bigquery import BigQuery

class QueriesSQL(BigQuery):

    def __init__(self, start_date: str, end_date: str) -> None:
        super().__init__(start_date, end_date)
        self.regex_1: str = 'https?://[^/]+'
        self.regex_2: str = '\?.*'

    