from src.ga4_ecommerce_analytics_engine.constants import DATASET, TABLE, REGEX_BASE_URL, REGEX_QUERY_PARAMS
from run_bigquery import BigQuery

class QueriesSQL(BigQuery):

    def __init__(self, start_date: str, end_date: str) -> None:
        super().__init__(start_date, end_date)

    def events(self):
        '''
        SQL query for Google Cloud Platform's BigQuery that 
        extracts the raw events from the specified start_date to end_date.
        '''
        self.query = f"""
            SELECT
                user_pseudo_id,
                CONCAT(
                    user_pseudo_id, 
                    '-',
                    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') 
                ) AS session_id,
                (SELECT value.int value FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS session_number,
                PARSE_DATE('%Y%m%d', event_date) AS event_date,
                TIMESTAMP_MICROS(event_timestamp) AS event_timestamp_micros,
                event_name,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_engaged') AS session_engaged,
                (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec') AS engagement_time_msec,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') AS source,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') AS medium,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign') AS campaign,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_referrer) AS page_referrer,
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
                        r'{REGEX_BASE_URL}', ''
                    ),
                    r'{REGEX_QUERY_PARAMS}', ''
                ) AS page_path,
                FROM `{DATASET}.{TABLE}`
                WHERE _TABLE_SUFFIX BETWEEN '{self.start_date}' AND '{self.end_date}'
                    AND (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id) IS NOT NULL
        """ 
        return self
    