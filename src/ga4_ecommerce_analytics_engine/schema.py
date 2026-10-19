from __future__ import annotations

from dataclasses import dataclass
import logging

import polars as pl

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataSchema:
    # ---- Column names. ---> Edit for different column names. <---------------------

    # --- Event scope:

    # Events
    timestamp: str = 'event_timestamp_micros'
    user_id: str = 'user_pseudo_id'
    event_type: str = 'event_name'
    event_date: str = 'event_date'
    conversion_timestamp: str = 'conversion_timestamp'

    # Ecommerce
    transaction_id: str = 'transaction_id'
    event_value: str = 'event_value'
    basket_size: str = 'basket_size'
    unique_items: str = 'unique_items'

    # Engagement
    engagement_time: str = 'engagement_time_msec'

    # Sources
    source: str = 'source'
    medium: str = 'medium'
    campaign: str = 'campaign'

    # Geography and device (descriptive columns on the events)
    continent: str = 'continent'
    country: str = 'country'
    region: str = 'region'
    city: str = 'city'
    device: str = 'device'
    device_category: str = 'device_category'
    device_brand_name: str = 'device_brand_name'
    device_model_name: str = 'device_model_name'
    device_os: str = 'device_os'
    device_os_version: str = 'device_os_version'

    # --- Item scope:
    # NOTE: item_id is the INPUT column that identifies an item (the item's name).
    #       item_key (below, under Keys) is the OUTPUT key column in the item tables.
    item_id: str = "item_name"
    item_value: str = "item_revenue"
    item_quantity: str = "quantity"
    item_brand: str = 'item_brand'
    item_variant: str = 'item_variant'
    item_category: str = 'item_category'
    item_price: str = 'price'
    not_set: str = '(not set)'          # GA4's placeholder for a missing item name

    # Item-funnel outputs
    is_viewed: str = 'is_viewed'
    is_added_to_cart: str = 'is_added_to_cart'
    is_checked_out: str = 'is_checked_out'
    is_purchased: str = 'is_purchased'
    revenue: str = 'revenue'

    # --- Session scope:

    # Sessions
    session_id: str = "session_id"
    session_number: str = 'session_number'
    session_engaged: str = 'session_engaged'
    session_start_timestamp: str = 'session_start'
    session_date: str = 'session_date'
    session_engagement_time: str = 'engagement_time'
    event_count: str = 'event_count'
    converted: str = 'converted'
    session_value: str = 'value'
    conversions_in_session: str = 'conversions_in_session'

    # UTM Parameters
    source_utm: str = 'source_utm'
    medium_utm: str = 'medium_utm'
    campaign_utm: str = 'campaign_utm'
    channel: str = 'channel'

    # Counts
    page_views: str = 'page_views'
    item_views: str = 'item_views'
    carts: str = 'carts'
    checkouts: str = 'checkouts'

    # --- Journey Scope:
    hours_before_conversion: str = 'hours_before'
    has_conversion: str = 'has_conversion'
    conversion_path: str = 'conversion_path'
    hours_path: str = 'hours_path'
    channel_set: str = 'channel_set'
    journey_start_timestamp: str = 'journey_start'
    journey_end_timestamp: str = 'journey_end'
    timestamp_path: str = 'timestamp_path'
    conversion_count: str = 'conversion_count'
    conversion_value: str = 'conversion_value_usd'
    touchpoints: str = 'touchpoints'
    journey_duration: str = 'duration'
    touchpoint_count: str = 'touchpoint_count'
    path_to_conversion: str = 'path_to_conversion'

    # --- User Scope (outputs of the user facts):
    first_active_date: str = 'first_active_date'
    last_active_date: str = 'last_active_date'
    total_pageviews: str = 'total_pageviews'
    total_engaged_sessions: str = 'total_engaged_sessions'
    total_engagement_time: str = 'total_engagement_time_msec'
    total_sessions: str = 'total_sessions'
    total_lifetime_events: str = 'total_lifetime_events'
    lifetime_revenue: str = 'lifetime_revenue'
    total_purchases: str = 'total_purchases'
    total_items_purchased: str = 'total_items_purchased'
    total_conversions: str = 'total_conversions'
    repeat: str = 'repeat'

    # --- Basket Scope (item pairs bought together):
    antecedent: str = 'antecedent'
    consequent: str = 'consequent'
    basket: str = 'basket'
    number_of_transactions: str = 'number_of_transactions'
    support_of_basket: str = 'support_of_basket'
    confidence_of_first_item: str = 'confidence_of_first_item'
    confidence_of_second_item: str = 'confidence_of_second_item'
    lift: str = 'lift'
    is_self_node: str = 'is_self_node'
    basket_value: str = 'value'
    community: str = 'community'
    basket_id: str = 'basket_id'

    # --- Keys. Each is the name of an id column in a dimension table and in the facts that point at it.
    event_id: str = 'event_id'
    date_id: str = 'date_id'
    geo_id: str = 'geo_id'
    device_id: str = 'device_id'
    traffic_source_id: str = 'traffic_source_id'
    item_key: str = 'item_id'
    item_funnel_id: str = 'item_funnel_id'
    journey_id: str = 'journey_id'
    converting_journey_id: str = 'converting_journey_id'

    # ---- Event type values. ----> Edit for different column value names. <--------------

    # Fires when a conversion event takes place
    conversion: str = "purchase"

    # Fires when a session is started
    session_start_event: str = 'session_start'
    first_visit: str = 'first_visit'

    # Event funnel
    page_view: str = 'page_view'
    view_item: str = 'view_item'
    select_item: str = 'select_item'
    add_to_cart: str = 'add_to_cart'
    begin_checkout: str = 'begin_checkout'

    def check_required_columns(
        self,
        df: pl.DataFrame,
        required_values: set[str] | None = None,
        required_columns: set[str] | None = None,
    ) -> None:
        '''
        Fail early, with a readable message, when the input is missing columns, or (optionally)
        event type values, that the schema requires.
        '''
        missing_cols = set(required_columns or ()) - set(df.columns)
        if missing_cols:
            raise KeyError(
                f'Schema validation failed. '
                f'The following required columns are missing from the input dataframe: {sorted(missing_cols)}'
            )

        if required_values:
            present = set(df.get_column(self.event_type).unique().to_list())
            missing_vals = set(required_values) - present
            if missing_vals:
                raise ValueError(
                    f'Schema validation failed. '
                    f'The following required event type values are missing from the input dataframe: {sorted(missing_vals)}'
                )

        logger.info('Schema validation passed.')
