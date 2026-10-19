
from __future__ import annotations

import polars as pl

from ga4_ecommerce_analytics_engine.dimensions.base import BaseDimension


class GeoDimension(BaseDimension):
    @property
    def key(self) -> str:
        return self.geo_id

    @property
    def columns(self) -> tuple[str, ...]:
        return (self.continent, self.country, self.region, self.city)

    def build_with_user_mapping(self, dimensions_df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Return (geo dimension, user -> geo key).

        The dimension holds every location seen. Each user maps to the first location they were seen in,
        so a user who travelled does not get two rows (and duplicate facts).
        """
        self.check_required_columns(dimensions_df, required_columns={self.user_id, self.timestamp})
        dimension = self.build(dimensions_df)
        first = self.first_per_entity(dimensions_df, self.user_id, self.timestamp)
        return dimension, self.assign_keys(first, dimension, self.user_id)
