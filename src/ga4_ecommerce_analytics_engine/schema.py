
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSchema:

    # ---- Required columns. ---> Edit for different column names. <---------------
    
    # Events
    timestamp: str = "event_timestamp_micros"
    user_id: str = "user_pseudo_id"
    event_type: str = "event_name"
    event_date: str = 'event_date'

    # Sessions
    session_id: str = "session_id"
    session_number: str = 'session_number'
    session_engaged: str = 'session_engaged'

    # Engagement
    engagement_time: str = 'engagement_time_msec'


    # Items
    item_id: str = "item_name"
    item_value: str = "item_revenue"
    item_quantity: str = "quantity"
    transaction_id: str = "transaction_id"

    # Sources
    source: str = 'source'
    medium: str = 'medium'
    campaign: str = 'campaign'

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
