'''
Clean raw GA4 transaction event data.

Input:
    - session_id: the raw GA session id (an integer), NOT the combined
    '<user>-<session>' string. This module builds the combined id once, here.
    - event_timestamp_micros: a timestamp, or integer microseconds since epoch.
    - items also carry: item_name, item_revenue, quantity, and (optionally) the
      event-level columns listed in EVENT_CONTEXT_COLUMNS.

Output:
    - events: every non-purchase event, plus one aggregated purchase event per
      transaction (event_value, basket_size, unique_items), sorted by user and
      time, with a conversion_timestamp column.
    - items: every non-purchase item row, plus the deduplicated purchase item
      rows with a transaction_id. All rows use the combined session_id.
'''

from __future__ import annotations

import logging
from typing import NamedTuple
from dataclasses import dataclass, fields

import polars as pl

logger = logging.getLogger(__name__)

# Store the cleaned data in a class for easy access.
class CleanedData(NamedTuple):
    events: pl.DataFrame
    items: pl.DataFrame

@dataclass(frozen=True)
class RequiredColumnsConfig:
    '''
    Change required column names for data flexibility.
    '''
    timestamp: str = 'event_timestamp_micros'
    user_id: str = 'user_pseudo_id'
    session_id: str = 'session_id'
    item_id: str = 'item_name'
    transaction_id: str = 'transaction_id'
    event_type: str = 'event_name'
    conversion: str = 'purchase'
    item_value: str = 'item_revenue'
    item_quantity: str = 'item_quantity'

class DataCleaner:
    def __init__(self, **config_overrides) -> None:
        '''
        Initializes the cleaner with the required columns config,
        which accepts optional column names to override the config.
        '''
        # Composition over inheritance.
        config = RequiredColumnsConfig(**config_overrides)

        self.timestamp = config.timestamp
        self.user_id = config.user_id
        self.session_id = config.session_id
        self.item_id = config.item_id
        self.transaction_id = config.transaction_id
        self.event_type = config.event_type
        self.conversion = config.conversion
        self.item_value = config.item_value
        self.item_quantity = config.item_quantity
    
    @property
    def deduplication_keys(self) -> list[str]:
        return [
            self.user_id, 
            self.session_id,
            self.transaction_id,
            self.item_id
            ]
    
    @property
    def event_keys(self) -> list[str]:
        return [
            self.user_id,
            self.session_id,
            self.timestamp
        ]

    # ---- Validation and normalizing -------------------------------------------------------

    def _check_required_columns(self, df: pl.DataFrame) -> None:
        '''
        This will fail early and includes a readable message when the extract is missing any columns
        to ensures that the raw data matches the required columns config.
        '''
        exclude_key = {'conversion'}
        
        required_cols = {
            value
            for key, value in vars(self).items()
            if key not in exclude_key and isinstance(value, str)
        }

        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise KeyError(
                f"Pre-cleaning Schema Validation Failed. " 
                f"The following required columns are missing from the items dataset: {missing_cols}"
            )
        logger.info("Schema validation passed. All required columns are in the items dataset.")

    def normalize_timestamps(self, df: pl.DataFrame) -> pl.DataFrame:
        '''
        Make timestamp a Datetime, whether it arrives as one or as an int.
        '''
        if df.schema[self.timestamp].is_integer():
            logger.info('Timestamp is an integer, converting to Datetime')
            return df.with_columns(
                pl.from_epoch(pl.col(self.timestamp), time_unit="us").alias(self.timestamp)
            )
        logger.info('Timestamp is already a Dateimte')
        return df

    def add_composite_session_id(self, df: pl.DataFrame) -> pl.DataFrame:
        '''
        Replace the raw session id with the composition key: user_id-session_id.

        A GA session id is only unique per user, so the combined id is truly unique.

        This also refuses to run twice, which would give something like: 'user-user-123'.
        '''
        already_combined = df.select(
            pl.col(self.session_id)
            .cast(pl.Utf8)
            .str.starts_with(pl.col(self.user_id))
            .any()
        ).item()

        if already_combined: # pass over the function no need for any error message.
            logger.info("session_id is already a composite key.")
            return df

        logger.info("creating a composition key for session_id")
        return df.with_columns(
            pl.concat_str(
                [pl.col(self.user_id), pl.col(self.session_id).cast(pl.Utf8)], separator='-'
            ).alias(self.session_id)
        )

    # --- Purchase items -------------------------------------------

    def extract_purchase_items(self, items: pl.DataFrame) -> pl.DataFrame:
        '''
        Keeps purchase item rows that *have* a revenue value (i.e., when the revenue is NOT a NULL value but may or may not contain a transaction_id that is NULL).
        '''
        purchases = items.filter(pl.col(self.event_type).eq(self.conversion))
        purchases = purchases.with_columns(
            pl.when(pl.col(self.transaction_id).is_null() & pl.col(self.item_value).is_not_null())
              .then(pl.lit('(not set)'))
              .otherwise(pl.col(self.transaction_id))
              .alias(self.transaction_id)
        )
        n_before = purchases.height
        purchases = purchases.filter(pl.col(self.item_value).is_not_null())
        logger.info( # Logger only takes % format and NOT f-strings!
            "Purchase item rows: %d before filter | %d after | %d dropped (null revenue)",
            n_before,
            purchases.height,
            n_before - purchases.height,
        )
        return purchases

    def add_transaction_id(self, purchase_items: pl.DataFrame) -> pl.DataFrame:
        '''
        Build transaction_id as a composition key with session_id-timestamp. 

        This creates a truly user-transaction unique id that can be traced back.
        '''
        logger.info('adding a new transaction_id')
        return purchase_items.with_columns(
            pl.concat_str(
                [
                    pl.col(self.session_id),
                    pl.col(self.timestamp).dt.epoch("us").cast(pl.Utf8)
                ],
                separator = '-',
            ).alias(self.transaction_id)
        )

    def deduplicate_items(self, purchase_items: pl.DataFrame) -> pl.DataFrame:
        '''
        Keep the first row for each user, session, transaction and item.
        '''
        n_before = purchase_items.height
        deduplicated = purchase_items.unique(
            subset=self.deduplication_keys, keep='first', maintain_order=True
        )
        logger.info( # its important to keep track of cleaning stats.
            "Purchase item rows after deduplicating: %d (%d dropped)",
            deduplicated.height,
            n_before - deduplicated.height,
        )
        return deduplicated

    # --- Purchase events ------------------------------------------------


    def aggregate_items_to_events(self, purchase_items: pl.DataFrame, raw_events: pl.DataFrame) -> pl.DataFrame:
        '''
        Collapse item rows into one purchase event per transaction.

        event_value  = sum of item revenue
        basket_size  = sum of quantities
        unique_items = number of item rows with a quantity 
        '''
        context_columns = raw_events.drop(self.event_keys).columns

        logging.info("Event columns: %s", raw_events.columns)
        logging.info("Item columns: %s", purchase_items.columns)
        logging.info("Context columns: %s", context_columns)
        
        context = [
            pl.col(column).first()
            for column in context_columns
            if column in purchase_items.columns
        ]
        logging.info('context: %s', context)
        return purchase_items.group_by(self.event_keys, maintain_order=True).agg(
            pl.col(self.transaction_id).first(),
            *context,
            pl.col(self.item_value).sum().alias('event_value'),
            pl.col(self.item_quantity).sum().alias('basket_size'),
            pl.col(self.item_quantity).count().alias('unique_items'),
        )

    def merge_purchases_into_events(
        self,
        raw_events: pl.DataFrame, purchase_events: pl.DataFrame
    ) -> pl.DataFrame:
        '''
        Swap the raw purchase events for the aggregated ones and add a conversion_timestamp column.
        '''
        non_purchase = raw_events.filter(pl.col(self.event_type) != self.conversion)
        combined = pl.concat([non_purchase, purchase_events], how='diagonal_relaxed').sort(
            [self.user_id, self.timestamp], maintain_order=True
        )
        return combined.with_columns(
            pl.when(pl.col(self.event_type) == self.conversion)
            .then(pl.col(self.timestamp))
            .otherwise(None)
            .alias('conversion_timestamp')
        )

    def rebuild_items(self, raw_items: pl.DataFrame, purchase_items: pl.DataFrame) -> pl.DataFrame:
        '''
        Non-purchase item rows appended to the cleaned purchase item rows.
        '''
        non_purchase = raw_items.filter(pl.col(self.event_type).ne(self.conversion))
        return pl.concat([non_purchase, purchase_items], how='diagonal_relaxed')

    # ---- Main ----------------------------------------------------

    def clean_transactions(self, raw_events: pl.DataFrame, raw_items: pl.DataFrame, composition_key: bool = False) -> CleanedData:
        '''
        Run every cleaning step and return the cleaned events and items.
        '''
        # --- Column Validation ----------------------------------
        self._check_required_columns(raw_items) # Checks whether the items dataframe contains ALL the required columns needed for deduplication.

        # --- Column normalization -------------------------------
        if composition_key:
            raw_events = self.add_composite_session_id(self.normalize_timestamps(raw_events)) # Creates a unique SESSION_ID by composition (i.e., USER_ID-SESSION_ID) for the EVENTS dataframe.
            raw_items = self.add_composite_session_id(self.normalize_timestamps(raw_items)) # Ditto, but for the ITEMS dataframe.
        else:
            raw_events = self.normalize_timestamps(raw_events)
            raw_items = self.normalize_timestamps(raw_items)

        # --- Clean transaction_id & deduplicate transactions -------------------------------
        purchase_items = self.deduplicate_items(self.add_transaction_id(self.extract_purchase_items(raw_items))) 
        purchase_events = self.aggregate_items_to_events(purchase_items, raw_events) 

        return CleanedData(
            events = self.merge_purchases_into_events(raw_events, purchase_events),
            items = self.rebuild_items(raw_items, purchase_items)
    )

