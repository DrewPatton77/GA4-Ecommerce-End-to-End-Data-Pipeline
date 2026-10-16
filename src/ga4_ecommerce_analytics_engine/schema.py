from dataclasses import dataclass


@dataclass(frozen=True)
class DataSchema:

    # ---- Required columns. Edit for different column names. -------------------
    
    # Events
    timestamp: str = "event_timestamp_micros"
    user_id: str = "user_pseudo_id"
    session_id: str = "session_id"
    event_type: str = "event_name"

    # Items
    item_id: str = "item_name"
    item_value: str = "item_revenue"
    item_quantity: str = "quantity"
    transaction_id: str = "transaction_id"

    # Sources
    source: str = 'source'
    medium: str = 'medium'
    campaign: str = 'campaign'

    # ---- Column values. Edit for different column value names. -----------------
    conversion: str = "purchase"  
    session_start: str = 'session_start'
    first_visit: str = 'first_visit'