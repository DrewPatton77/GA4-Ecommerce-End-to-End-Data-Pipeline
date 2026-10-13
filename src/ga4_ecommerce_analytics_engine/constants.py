from config import GCP_PROJECT_ID, POSTGRES_USERNAME, POSTGRES_PASSWORD, POSTGRES_DB, PORT, HOST

# Google Cloud BigQuery Information
GCP_PROJECT_ID = GCP_PROJECT_ID
DATASET = 'bigquery-public-data.ga4_obfuscated_sample_ecommerce'
TABLE = 'events_*' # Dataset table name.
START_DATE = '20201101' # November 01, 2020. Start of dataset
END_DATE = '20210131' # January. 31, 2021. End of dataset

# PostgreSQL database information
POSTGRES_USERNAME = POSTGRES_USERNAME
POSTGRES_PASSWORD = POSTGRES_PASSWORD
POSTGRES_DB = POSTGRES_DB
PORT = PORT
HOST = HOST
PROJECT_ID = GCP_PROJECT_ID