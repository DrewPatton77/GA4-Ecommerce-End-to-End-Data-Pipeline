from pathlib import Path
from dotenv import dotenv_values

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"   # repo root
config = dotenv_values(_ENV_PATH)

# For BigQuery
PROJECT_ID = config.get('GCP_PROJECT_ID')
if not PROJECT_ID:
    raise RuntimeError(
        f"GCP_PROJECT_ID not found. "
        f"Set it in {_ENV_PATH}"
    )

# For BigQueryClient class
USD_TO_CAD_EXCHANGE_RATE: float = 1.42 # $1 USD ~ $1.42 CAD, as of Oct. 13, 2026. Subject to change.
ONDEMAND_PRICING: float = 6.25 # ~$6.25 USD per TiB on-demand. (See:  https://cloud.google.com/bigquery/pricing#on-demand-compute-pricing).
MAXIMUM_BYTES_BILLED: int = 10 # GB. Safety cap.


