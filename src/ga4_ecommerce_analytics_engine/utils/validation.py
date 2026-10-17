from __future__ import annotations

import logging

import polars as pl

logger = logging.getLogger(__name__)

def check_required_columns(self, df: pl.DataFrame, required_values) -> None:
        '''
        This will fail early and includes a readable message when the extract is missing any columns
        to ensure that the data matches the required columns schema.
        '''
        
        required_cols = {
            value
            for key, value in vars(self).items()
            if key not in required_values and isinstance(value, str)
        }

        missing_cols = required_cols - set(df.columns)
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
        