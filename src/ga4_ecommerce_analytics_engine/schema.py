'''
Column names and event values used across the pipeline.

Every module reads its column names from DataSchema, so renaming a column means editing it here only.
Each section is one scope; the Keys section holds the id columns that tables share.
'''

from __future__ import annotations

from dataclasses import dataclass
import logging

import polars as pl

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataSchema:

    # ====================================================================
    # Events
    # One row per GA4 event
    # ====================================================================
    timestamp:            str = 'event_timestamp_micros'  # microseconds since the epoch in the source; a Datetime after cleaning
    user_id:              str = 'user_pseudo_id'
    event_type:           str = 'event_name'              # the event's name, e.g. purchase
    event_date:           str = 'event_date'
    conversion_timestamp: str = 'conversion_timestamp'    # set on purchase events only
    page_referrer:        str = 'page_referrer'
    page_path:            str = 'page_path'
    first_touch:          str = 'first_touch'

    # ====================================================================
    # Ecommerce
    # Purchase values on an event
    # ====================================================================
    transaction_id: str = 'transaction_id'
    event_value:    str = 'event_value'     # sum of the item revenue
    basket_size:    str = 'basket_size'     # sum of the quantities
    unique_items:   str = 'unique_items'    # distinct items in the purchase

    # ====================================================================
    # Engagement
    # ====================================================================
    engagement_time: str = 'engagement_time_msec'

    # ====================================================================
    # Marketing source
    # Raw values, before enrichment
    # ====================================================================
    source:   str = 'source'
    medium:   str = 'medium'
    campaign: str = 'campaign'

    # ====================================================================
    # Geography and device
    # Descriptive columns on the events
    # ====================================================================
    continent:         str = 'continent'
    country:           str = 'country'
    region:            str = 'region'
    city:              str = 'city'
    device:            str = 'device'
    device_category:   str = 'device_category'
    device_brand_name: str = 'device_brand_name'
    device_model_name: str = 'device_model_name'
    device_os:         str = 'device_os'
    device_os_version: str = 'device_os_version'
    device_language:   str = 'device_language'

    # ====================================================================
    # Items
    # NOTE: item_id is the INPUT column that names an item. item_key (under Keys) is the OUTPUT key in the item tables.
    # ====================================================================
    item_id:       str = 'item_name'      # the item's name
    item_value:    str = 'item_revenue'   # revenue
    item_quantity: str = 'quantity'
    item_brand:    str = 'item_brand'
    item_variant:  str = 'item_variant'
    item_category: str = 'item_category'
    item_price:    str = 'price'
    not_set:       str = '(not set)'      # GA4's placeholder for a missing item name
    uncategorized: str = 'Uncategorized'
    unbranded:     str = 'Unbranded'

    # ====================================================================
    # Item funnel outputs
    # ====================================================================
    is_viewed:        str = 'is_viewed'
    is_added_to_cart: str = 'is_added_to_cart'
    is_checked_out:   str = 'is_checked_out'
    is_purchased:     str = 'is_purchased'
    revenue:          str = 'revenue'

    # ====================================================================
    # Sessions
    # ====================================================================
    session_id:              str = 'session_id'
    session_number:          str = 'session_number'
    session_engaged:         str = 'session_engaged'
    session_start_timestamp: str = 'session_start'
    session_date:            str = 'session_date'
    session_engagement_time: str = 'engagement_time'
    event_count:             str = 'event_count'
    converted:               str = 'converted'
    session_value:           str = 'value'                   # same text as basket_value: 'value'
    conversions_in_session:  str = 'conversions_in_session'

    # ====================================================================
    # UTM and channels
    # Output of Enrichment
    # ====================================================================
    source_utm:    str = 'source_utm'
    medium_utm:    str = 'medium_utm'
    campaign_utm:  str = 'campaign_utm'
    channel:       str = 'channel'
    channel_group: str = 'channel_group'

    # ====================================================================
    # Session counts
    # ====================================================================
    page_views: str = 'page_views'
    item_views: str = 'item_views'
    carts:      str = 'carts'
    checkouts:  str = 'checkouts'

    # ====================================================================
    # Journeys
    # ====================================================================
    hours_before_conversion: str = 'hours_before'
    has_conversion:          str = 'has_conversion'
    conversion_path:         str = 'conversion_path'
    hours_path:              str = 'hours_path'
    channel_set:             str = 'channel_set'
    journey_start_timestamp: str = 'journey_start'
    journey_end_timestamp:   str = 'journey_end'
    timestamp_path:          str = 'timestamp_path'
    conversion_count:        str = 'conversion_count'
    conversion_value:        str = 'conversion_value_usd'
    touchpoints:             str = 'touchpoints'
    journey_duration:        str = 'duration'
    touchpoint_count:        str = 'touchpoint_count'
    path_to_conversion:      str = 'path_to_conversion'

    # ====================================================================
    # Users
    # Outputs of the user facts
    # ====================================================================
    first_active_date:      str = 'first_active_date'
    last_active_date:       str = 'last_active_date'
    total_pageviews:        str = 'total_pageviews'
    total_engaged_sessions: str = 'total_engaged_sessions'
    total_engagement_time:  str = 'total_engagement_time_msec'
    total_sessions:         str = 'total_sessions'
    total_lifetime_events:  str = 'total_lifetime_events'
    lifetime_revenue:       str = 'lifetime_revenue'
    total_purchases:        str = 'total_purchases'
    total_items_purchased:  str = 'total_items_purchased'
    total_conversions:      str = 'total_conversions'
    repeat:                 str = 'repeat'

    # ====================================================================
    # Basket
    # Item pairs bought together
    # ====================================================================
    antecedent:                str = 'antecedent'
    consequent:                str = 'consequent'
    basket:                    str = 'basket'
    number_of_transactions:    str = 'number_of_transactions'
    support_of_basket:         str = 'support_of_basket'
    confidence_of_first_item:  str = 'confidence_of_first_item'
    confidence_of_second_item: str = 'confidence_of_second_item'
    lift:                      str = 'lift'
    is_self_node:              str = 'is_self_node'
    basket_value:              str = 'value'                      # same text as session_value: 'value'
    basket_id:                 str = 'basket_id'

    # ====================================================================
    # Network: layout
    # ====================================================================
    layout_x: str = 'layout_x'
    layout_y: str = 'layout_y'

    # ====================================================================
    # Network: nodes
    # ====================================================================
    degree:          str = 'degree'
    strength:        str = 'strength'
    betweenness:     str = 'betweenness'
    closeness:       str = 'closeness'
    clustering:      str = 'clustering'
    raw_degree:      str = 'raw_degree'
    raw_strength:    str = 'raw_strength'
    hub_rank:        str = 'hub_rank'
    is_hub:          str = 'is_hub'
    item_baskets:    str = 'item_baskets'
    item_revenue:    str = 'item_revenue'
    community:       str = 'community'
    community_label: str = 'community_label'

    # ====================================================================
    # Network: edges
    # ====================================================================
    network_edge_id:   str = 'network_edge_id'
    item_a:            str = 'item_a'
    item_b:            str = 'item_b'
    cooccurrence:      str = 'cooccurrence'
    confidence_a_to_b: str = 'confidence_a_to_b'
    confidence_b_to_a: str = 'confidence_b_to_a'
    edge_alpha:        str = 'edge_alpha'
    edge_betweenness:  str = 'edge_betweenness'
    community_a:       str = 'community_a'
    community_b:       str = 'community_b'
    is_bridge:         str = 'is_bridge'

    # ====================================================================
    # Network: communities
    # ====================================================================
    community_hub:        str = 'community_hub'
    community_title:      str = 'community_title'
    community_item_count: str = 'community_item_count'
    community_edges:      str = 'community_edges'
    bridge_edges:         str = 'bridge_edges'
    density:              str = 'density'
    total_cooccurrence:   str = 'total_cooccurrence'
    average_lift:         str = 'average_lift'
    community_items:      str = 'community_items'

    # ====================================================================
    # Network: stages
    # ====================================================================
    stage_order: str = 'stage_order'
    stage:       str = 'stage'
    edges:       str = 'edges'
    nodes:       str = 'nodes'
    modularity:  str = 'modularity'

    # ====================================================================
    # Attribution
    # ====================================================================
    attribution_id:          str = 'attribution_id'
    attribution_model_id:    str = 'attribution_model_id'
    attribution_model:       str = 'attribution_model'
    attribution_description: str = 'attribution_description'
    touch_number:            str = 'touch_number'
    credit:                  str = 'credit'
    revenue_credit:          str = 'revenue_credit'

    # ====================================================================
    # Keys
    # Each is the name of an id column in a dimension table and in the facts that point at it
    # ====================================================================
    event_id:              str = 'event_id'
    date_id:               str = 'date_id'
    geo_id:                str = 'geo_id'
    device_id:             str = 'device_id'
    traffic_source_id:     str = 'traffic_source_id'
    product_key:           str = 'product_id'
    item_key:              str = 'item_id'                # the item tables' key; item_id above is the item NAME
    item_funnel_id:        str = 'item_funnel_id'
    journey_id:            str = 'journey_id'
    converting_journey_id: str = 'converting_journey_id'

    # ====================================================================
    # Event type values
    # Edit for different event names
    # ====================================================================
    conversion:          str = 'purchase'        # fires when a purchase happens
    session_start_event: str = 'session_start'   # fires when a session starts
    first_visit:         str = 'first_visit'
    page_view:           str = 'page_view'
    view_item:           str = 'view_item'
    select_item:         str = 'select_item'
    add_to_cart:         str = 'add_to_cart'
    begin_checkout:      str = 'begin_checkout'

    # ====================================================================
    # Validation
    # ====================================================================
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