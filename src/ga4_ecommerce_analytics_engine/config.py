
from dotenv import dotenv_values

config = dotenv_values(".env")
# For BigQuery
PROJECT_ID = config['GCP_PROJECT_ID']

# For BigQueryClient class
USD_TO_CAD_EXCHANGE_RATE: int = 1.42 # $1 USD ~ $1.42 CAD, as of Oct. 13, 2026. Subject to change.
ONDEMAND_PRICING: int = 6.25 # ~$6.25 USD per TB on-demand. (See:  https://cloud.google.com/bigquery/pricing#on-demand-compute-pricing).
MAXIMUM_BYTES_BILLED: int = 10 # GB. Safety cap.


