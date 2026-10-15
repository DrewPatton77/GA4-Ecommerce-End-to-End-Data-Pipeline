'''
BigQuery implementation of BaseSource.

Combines QueryLoader (which SQL to run) with BigQueryClient (how to run it),
and caches results locally as parquet so repeat runs cost nothing.
'''

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import polars as pl

from ga4_ecommerce_analytics_engine.sources.base import BaseSource, DateLike
from ga4_ecommerce_analytics_engine.sources.bigquery_client import BigQueryClient, CostEstimate, Columns
from ga4_ecommerce_analytics_engine.sources.query_loader import QueryLoader

logger = logging.getLogger(__name__)

# <repo root>/data/cache, resolbed from src/<package>/sources/bigquery_source.py
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"

# Template names in sql/bigquery/ for each raw table.
EVENTS_QUERY = 'events'
ITEMS_QUERY = 'items'
DIMENSIONS_QUERY = 'dimensions'

class BigQuerySource(BaseSource):
    '''
    Fetches raw GA4 data from BigQuery, with an optional local parquet cache.
    '''

    def __init__(
        self,
        client: BigQueryClient | None = None,
        loader: QueryLoader | None = None,
        cache_dir : Path | str = DEFAULT_CACHE_DIR,
        use_cache: bool = True,
        refresh: bool = False,
    ) -> None:
        '''
        Args:
            client: Runs queries. A default BigQueryClient is created if not instantiated
            loader: Renders SQL templates. A default QueryLoader is created if not instantiated
            cache_dir: Where cached parquet files are stored.
            use_cache: Read from and write to the cache.
            refresh: Ignore existing cache files and re-query (the result is re-cached).
        ''' 
        self.client = client or BigQueryClient()
        self.loader = loader or QueryLoader()
        self.cache_dir = Path(cache_dir)
        self.use_cache = use_cache
        self.refresh = refresh

    # ---- BaseSource Interface -----------------------------

    def fetch_events(self, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        return self._fetch(EVENTS_QUERY, start_date, end_date)

    def fetch_items(self, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        return self._fetch(ITEMS_QUERY, start_date, end_date)

    def fetch_dimensions(self, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        return self._fetch(DIMENSIONS_QUERY, start_date, end_date)

    # --- Column validation ---------------------------------------------
    
    def validate_columns(self, start_date: DateLike, end_date: DateLike) -> None:
        '''
        Dry-run all three queries and return each of their columns, keyed by query name.

        Nothing is billed.
        '''
        columns = {}
        for name in (EVENTS_QUERY, ITEMS_QUERY, DIMENSIONS_QUERY):
            query = self.loader.render(name, start_date, end_date)
            columns[name] = self.client.columns(query)

        for column in columns[EVENTS_QUERY].columns:
            if not column in columns[ITEMS_QUERY].columns:
                raise KeyError(
                    f"Missing column in {ITEMS_QUERY} query: {column}"
                    f"All {EVENTS_QUERY} query columns should be in the {ITEMS_QUERY} query."
                )

    # ---- Cost -----------------------------------------------

    def estimate_cost(self, start_date: DateLike, end_date: DateLike) -> dict[str, CostEstimate]:
        '''
        Dry-run all three queries and return each estimate, keyed by query name.

        Nothing is billed. Call this before a first run over a new date range.
        '''
        estimates = {}
        for name in (EVENTS_QUERY, ITEMS_QUERY, DIMENSIONS_QUERY):
            query = self.loader.render(name, start_date, end_date)
            estimates[name] = self.client.estimate_cost(query)
            total_cad = sum(e.cost_usd for e in estimates.values())
            total_gb = sum(e.gb_scanned for e in estimates.values())

            logger.info("Total estimate:  ~$%.4f CAD, %.2f GB", total_cad, total_gb)

        return estimates

    # ---- Internals ----------------------------------------------

    def _fetch(self, name: str, start_date: DateLike, end_date: DateLike) -> pl.DataFrame:
        '''
        Render the query, then return cached data or run it against BigQuery.
        '''
        query = self.loader.render(name, start_date, end_date)
        cache_path = self._cache_path(name, query)

        if self.use_cache and not self.refresh and cache_path.is_file():
            logger.info(f"Reading '%s' from cache: %s", name, cache_path)
            return pl.read_parquet(cache_path)

        logger.info("Running '%s' query against BigQuery", name)
        df = self.client.run_query(query)

        if self.use_cache:
            self._write_cache(df, cache_path)
        
        return df

    def _cache_path(self, name: str, query: str) -> Path:
        '''
        Cache file named by query + a hash of the rendered SQL.

        The hash covers the dates and the SQL text, so changing either one 
        automatrically misses the cache instead of returning stale data.
        '''
        digest = hashlib.sha256(query.encode('utf-8')).hexdigest()[:12]
        return self.cache_dir / f"{name}_{digest}.parquest"

    def _write_cache(self, df: pl.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)
        logger.info("Cached %d rows to %s", df.height, path)

    
    
