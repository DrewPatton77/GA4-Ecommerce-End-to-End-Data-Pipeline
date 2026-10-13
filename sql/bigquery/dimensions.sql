SELECT  
    user_pseudo_id,
    TIMESTAMP_MICROS(event_timestamp_micros) AS event_timestamp_micros,
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    geo.continent,
    geo.country,
    geo.region,
    geo.city,
    TIMESTAMP_MICROS(user_first_touch_timestamp) AS first_touch,
    device.category AS device_category,
    device.language AS device_language,
    device.mobile_brand_name AS device_brand_name,
    device.mobile_model_name AS device_model_name,
    device.operating_system AS device_os,
    device.os_version AS device_os_version
FROM `{DATASET}.{TABLE}`
WHERE _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
    AND (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') IS NOT NULL