
from __future__ import annotations

from dataclasses import dataclass
import logging

import polars as pl

logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class DataSchema:
    # ---- Required columns. ---> Edit for different column names. <---------------
    
    #--- Event Scope:

    # Events
    timestamp: str = "event_timestamp_micros"
    user_id: str = "user_pseudo_id"
    event_type: str = "event_name"
    event_date: str = 'event_date'
    conversion_timestamp: str = 'conversion_timestamp'

    # Ecommerce
    transaction_id: str = 'transaction_id'

    # Engagement
    engagement_time: str = 'engagement_time_msec'

    # Sources
    source: str = 'source'
    medium: str = 'medium'
    campaign: str = 'campaign'

    # Items
    event_value: str = 'event_value'
    basket_size: str = 'basket_size'


    # --- Item Scope: 
    item_id: str = "item_name"
    item_value: str = "item_revenue"
    item_quantity: str = "quantity"


    # --- Session Scope:

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
    journey_id: str = 'journey_id'
    hours_before_conversion: str = 'hours_before'
    has_conversion: str = 'has_conversion'
    conversion_path: str = 'conversion_path'
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
    hours_path: str = 'hours_path'
    
    # ---- Event type values. ----> Edit for different column value names. <--------------
    
    # Fires when a conversion event takes place
    conversion: str = "purchase"  

    # Fires when a session is started
    session_start_event: str = 'session_start'
    first_visit: str = 'first_visit'

    # Event funnel
    page_view: str = 'page_view'
    view_item: str = 'view_item'
    add_to_cart: str = 'add_to_cart'
    begin_checkout: str = 'begin_checkout'

    def check_required_columns(self, df: pl.DataFrame, required_values: set[str] | None = None, required_columns: set[str] | None = None) -> None:
        '''
        This will fail early and includes a readable message when the extract is missing any columns
        to ensure that the data matches the required columns schema.
        '''

        missing_cols = set(required_columns or ()) - set(df.columns)
        if missing_cols:
            raise KeyError(
                f" Schema Validation Failed. " 
                f"Thes following required columns are missing from the input dataframe: {sorted(missing_cols)}"
            )

        if required_values != None:
            missing_vals = set(required_values) - set(df.get_column(self.event_type).unique().to_list())
            if missing_vals:
                raise ValueError(
                    f"Session-aggregation Schema Validation Failed. "
                    f"The following required event type values are missing from the input dataframe: {sorted(missing_vals)}"
                )
        logger.info("Schema validation passed.")
        
