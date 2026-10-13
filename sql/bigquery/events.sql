SELECT
    user_pseudo_id,
    CONCAT(
        user_pseudo_id, 
        '-',
        CAST(
            (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING
        )
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
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_referrer') AS page_referrer,
    REGEXP_REPLACE(
        REGEXP_REPLACE(
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'),
            'https?://[^/]+', ''
        ),
        '\?.*', ''
    ) AS page_path,
FROM `{DATASET}.{TABLE}`
WHERE _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
    AND (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') IS NOT NULL