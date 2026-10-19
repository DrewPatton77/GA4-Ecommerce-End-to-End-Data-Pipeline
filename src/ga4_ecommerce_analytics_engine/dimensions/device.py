
from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.dimensions.base import BaseDimension


class DeviceDimension(BaseDimension):
    @property
    def key(self) -> str:
        return self.device_id

    @property
    def columns(self) -> tuple[str, ...]:
        return (
            self.device_category,
            self.device_brand_name,
            self.device_model_name,
            self.device_os,
            self.device_os_version,
        )

    def build_with_user_mapping(self, dimensions_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Return (device dimension, user -> device key), using each user's first device."""
        self.check_required_columns(dimensions_df, required_columns={self.user_id, self.timestamp})
        first = self.first_per_entity(dimensions_df, self.user_id, self.timestamp)
        dimension = self.build(first)
        return dimension, self.assign_keys(first, dimension, self.user_id)
