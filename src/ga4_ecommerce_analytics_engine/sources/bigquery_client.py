'''
BigQuery client: dry-run cost estimates and query run.

Query results return as an Arrow table and converted to a polars DataFrame.
'''

from __future__ import annotations

# built-in modules
import logging
from dataclasses import dataclass
from typing import Sequence

# libraries
import polars as pl
import pyarrow as pa
from google.api_core.exceptions import BadRequest
from google.cloud import bigquery

# import config
from ga4_ecommerce_analytics_engine.config import (
    PROJECT_ID, 
    USD_TO_CAD_EXCHANGE_RATE, 
    ONDEMAND_PRICING, 
    MAXIMUM_BYTES_BILLED
)

# import constants
from ga4_ecommerce_analytics_engine.constants import (
    BYTES_PER_GB,
    BYTES_PER_TB
)

logger = logging.getLogger(__name__)


class BudgetExceededError(RuntimeError):
    '''
    Raised when a query's estimated scan is larger than the configured cap.
    '''

@dataclass(frozen=True) # to make hashable.
class CostEstimate:
    '''
    Result of a BigQuery dry run.
    '''

    bytes_scanned: int
    cost_usd: float
    cost_cad: float
    is_within_budget: bool

    @property
    def gb_scanned(self) -> float:
        return self.bytes_scanned / BYTES_PER_GB # Convert bytes to tebibytes.

    def summary(self) -> str:
        status = "within budget" if self.is_within_budget else "OVER BUDGET"
        return (
            f"Scanned: {self.gb_scanned:.2f} GB | "
            f"Cost: ~${self.cost_cad:.4f} CAD (~${self.cost_usd:.4f} USD | {status})"
        )

class BigQueryClient:
    '''
    Wrapper around google-cloud-bigquery.
    '''

    def __init__(
        self, 
        project_id: str = PROJECT_ID,
        usd_to_cad_exchange_rate: float = USD_TO_CAD_EXCHANGE_RATE,
        ondemand_pricing: float = ONDEMAND_PRICING,
        maximum_bytes_billed: int = MAXIMUM_BYTES_BILLED
    ) -> None:
        
        self.project_id = project_id
        self.usd_to_cad_exchange_rate = usd_to_cad_exchange_rate
        self.ondemand_pricing = ondemand_pricing
        self.maximum_bytes_billed = maximum_bytes_billed
        self._client: bigquery.Client | None = None

    # --- Internals -------------------------

    @property
    def client(self) -> bigquery.Client:
        '''
        Create the BigQuery client once, on first use.
        '''
        if self._client is None:
            self._client = bigquery.Client(project=self.project_id)
        return self._client

    def _build_job_config(
        self,
        dry_run: bool,
        query_parameters: Sequence[bigquery.ScalarQueryParameter] | None = None,
    ) -> bigquery.QueryJobConfig:
        '''
        Build job configs.
        '''
        config = bigquery.QueryJobConfig(dry_run=dry_run)
        if query_parameters:
            config.query_parameters = list(query_parameters)
        if not dry_run:
            # Safety cap: returns error if job 
            config.maximum_bytes_billed = int(self.maximum_bytes_billed * BYTES_PER_GB) # Convert from GB to bytes
        return config

    # ---- Cost ----------------------------

    def estimate_cost(
        self,
        query: str,
        query_parameters: Sequence[bigquery.ScalarQueryParameter] | None = None,
    ) -> CostEstimate:
        '''
        Dry-run a query and estimate what it would cost.

        Args:
            query: The SQL query to dry run.
            query_parameters: Optional named parameters (e.g. @start_date).

        Returns:
            A CostEstimate with bytes scanned, USD/CAD cost, and a budget flag.
        '''
        job_config = self._build_job_config(dry_run=True, query_parameters=query_parameters)
        try:
            job = self.client.query(query, job_config=job_config)
        except BadRequest as err:
            raise ValueError(f"BigQuery rejected the query during dry run: {err}") from err

        bytes_scanned = int(job.total_bytes_processed or 0)
        cost_usd = (bytes_scanned / BYTES_PER_TB) * self.ondemand_pricing
        cost_cad = cost_usd * self.usd_to_cad_exchange_rate

        estimate = CostEstimate(
            bytes_scanned=bytes_scanned,
            cost_usd=cost_usd,
            cost_cad=cost_cad,
            is_within_budget=self.is_within_budget(bytes_scanned)
        )
        logger.info(estimate.summary())
        return estimate

    def is_within_budget(self, bytes_scanned: int) -> bool:
        '''
        Compare bytes to budget bytes.
        '''
        return bytes_scanned / BYTES_PER_GB <= self.maximum_bytes_billed

    # ---- Running queries ----------------------------

    def run_query_arrow(
        self,
        query: str,
        query_parameters: Sequence[bigquery.ScalarQueryParameter] | None = None,
        check_budget: bool = True,
        timeout: float | None = None,
    ) -> pa.Table:
        '''
        Run a query and return the raw Arrow table.

        Args:
            query: The SQL query to run.
            query_parameters: Optional named parameters (e.g. @start_date).
            check_budget: Dry-run first and raise BudgetExceededError if over the cap.
            timeout: Seconds to wait for the result before giving up.
        '''
        if check_budget:
            estimate = self.estimate_cost(query, query_parameters)
            if not estimate.is_within_budget:
                raise BudgetExceededError(
                    f"Estimated scan of {estimate.gb_scanned:.2f} GB exceeds the cap of "
                    f"{self.maximum_bytes_billed * BYTES_PER_GB:.2f} GB."
                )

        job_config = self._build_job_config(dry_run=False, query_parameters=query_parameters)
        job = self.client.query(query, job_config=job_config)
        # Waits for the job to finish, then downloads via the Storage API when available.
        return job.result(timeout=timeout).to_arrow(create_bqstorage_client=True)

    def run_query(
        self,
        query: str,
        query_parameters: Sequence[bigquery.ScalarQueryParameter] | None = None,
        check_budget: bool = True,
        timeout: float | None = None,
    ) -> pl.DataFrame:
        '''
        Run a query and return a polars DataFrame (BigQuery -> Arrow -> polars).
        '''
        table = self.run_query_arrow(
            query,
            query_parameters=query_parameters,
            check_budget=check_budget,
            timeout=timeout,
        )
        return pl.from_arrow(table)

    def run_query_pandas(self, query: str, **kwargs) -> "pd.DataFrame":
        '''
        Temporary bridge for legacy code that still expects pandas.

        Delete once the cleaning and aggregation code is migrated to polars.
        '''
        return self.run_query(query, **kwargs).to_pandas()
        


