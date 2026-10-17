
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
    transaction_id: str = "transaction_id"


    # --- Session Scope:

    # Sessions
    session_id: str = "session_id"
    session_number: str = 'session_number'
    session_engaged: str = 'session_engaged'
    session_start_timestamp: str = 'session_start'
    session_date: str = 'session_date'
    session_engagement_time: str = 'engagement_time'
    session_engaged: str = 'session_engaged'
    event_count: str = 'event_count'

    conversions_in_session: str = 'conversions_in_session'


    # UTM Parameters
    source_utm: str = 'source_utm'
    medium_utm: str = 'medium_utm'
    campaign_utm: str = 'campaign_utm'

    #


    
    # ---- Event type values. ----> Edit for different column value names. <--------------
    
    # Fires when a conversion event takes place
    conversion: str = "purchase"  

    # Fires when a session is started
    session_start: str = 'session_start'
    first_visit: str = 'first_visit'

    # Event funnel
    page_view: str = 'page_view'
    view_item: str = 'view_item'
    add_to_cart: str = 'add_to_cart'
    begin_checkout: str = 'begin_checkout'

    def check_required_columns(self, df: pl.DataFrame, required_values: dict[str], required_columns: dict[str]) -> None:
        '''
        This will fail early and includes a readable message when the extract is missing any columns
        to ensure that the data matches the required columns schema.
        '''
        
        missing_cols = required_columns - set(df.columns)
        if missing_cols:
            raise KeyError(
                f" Schema Validation Failed. " 
                f"The following required columns are missing from the input dataframe: {missing_cols}"
            )
        
        missing_vals = required_values in df.select(pl.col(self.event_type).unique())
        if missing_vals:
            raise ValueError(
                f"Session-aggregation Schema Validation Failed. "
                f"The following required event type values are missing from the input dataframe: {missing_vals}"
            )
        logger.info("Schema validation passed. All required columns and values are in the input dataframe.")
        
