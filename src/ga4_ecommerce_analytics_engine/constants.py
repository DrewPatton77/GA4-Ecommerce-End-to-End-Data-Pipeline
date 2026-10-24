# Google Cloud BigQuery Information
DATASET: str = 'bigquery-public-data.ga4_obfuscated_sample_ecommerce'
TABLE: str = 'events_*' # Dataset table name.
START_DATE: str = '20201101' # November 01, 2020. Start of dataset
END_DATE: str = '20210131' # January. 31, 2021. End of dataset
BYTES_PER_TIB: int = 1024**4
BYTES_PER_GB: int = 10**9

# Channels
UNCLASSIFIED = "Unclassified"
SOURCE = 'source_utm'
MEDIUM = 'medium_utm'
CAMPAIGN = 'campaign_utm'

