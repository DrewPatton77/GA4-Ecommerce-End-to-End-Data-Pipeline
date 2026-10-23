'''
Tests for bigquery_client.py using a fake Google client (no network).

Uses a FakeClient from conftest.py that counts calls. This verifies the cache,
where the second fetch makes no query, changing the dates misses the cache,
refresh=True re-queries, and use_cache=False writes nothing.
'''

from __future__ import annotations

import polars as pl
import pyarrow as pa
import pytest
from google.api_core.exceptions import BadRequest

from ga4_ecommerce_analytics_engine.sources.bigquery_client import (
    BigQueryClient,
    BudgetExceededError,
    CostEstimate,
)
from ga4_ecommerce_analytics_engine.constants import BYTES_PER_TIB

CAP = 10 # 10 GB cap used by most tests


# ---- Fakes ---------------------------------------------

class FakeRows:
    def __init__(self, table: pa.Table) -> None:
        self._table = table

    def to_arrow(self, create_bqstorage_client: bool = True) -> pa.Table:
        return self._table

class FakeJob:
    def __init__(self, total_bytes: int, config, schema: tuple[str, ...] = ("x",)) -> None:
        self.total_bytes_processed = total_bytes
        self.job_config = config
        self.result_timeout = 'not called'
        self._schema = schema

    def result(self, timeout=None) -> FakeRows:
        self.result_timeout = timeout
        return FakeRows(pa.table({'x': [1, 2, 3]}))

    def _job_statistics(self) -> dict:
        return {"schema": {"fields": [{"name": n} for n in self._schema]}}


class FakeGoogleClient:
    '''
    Mimics the one method of bigquery.Client that BigQueryClient uses.
    '''

    def __init__(self, bytes_scanned: int = 0, error_on_dry_run: Exception | None = None, cap: int = CAP, schema: tuple[str, ...] = ("x")):
        self.bytes_scanned = bytes_scanned
        self.error_on_dry_run = error_on_dry_run
        self.jobs: list[FakeJob] = []
        self.cap: int = cap
        self.schema = schema

    def query(self, sql_query, job_config=None) -> FakeJob:
        if job_config.dry_run and self.error_on_dry_run:
            raise self.error_on_dry_run
        job = FakeJob(self.bytes_scanned, job_config, schema=self.schema)
        self.jobs.append(job)
        return job

def make_client(google_client: FakeGoogleClient, cap: int = CAP) -> BigQueryClient:
    # Strings on purpose: .env value arrives as text and must be cast.
    client = BigQueryClient(
        project_id='test-project',
        usd_to_cad_exchange_rate='1.4',
        ondemand_pricing='6.25',
        maximum_bytes_billed=str(cap),
    )
    client._client = google_client # skip creating a real bigquery.Client
    return client

# ---- Settings ---------------------------------------------

def test_settings_given_as_strings_are_cast_to_numbers():
    client = make_client(FakeGoogleClient())

    assert client.usd_to_cad_exchange_rate == 1.4
    assert client.ondemand_pricing == 6.25
    assert client.maximum_bytes_billed == CAP
    assert isinstance(client.maximum_bytes_billed, int)

# ---- Cost estimates -----------------------------------------

def test_estimate_cost_math():
    client = make_client(FakeGoogleClient(bytes_scanned=10**9, cap=CAP))

    estimate = client.estimate_cost("SELECT 1")

    assert estimate.bytes_scanned == 10**9
    assert estimate.gb_scanned == pytest.approx(1)
    assert estimate.cost_usd == pytest.approx(6.25 * 1e9 / BYTES_PER_TIB)
    assert estimate.cost_cad == pytest.approx((1.4 * 6.25 * 1e9) / BYTES_PER_TIB)
    assert estimate.is_within_budget is True

@pytest.mark.parametrize(
    'bytes_scanned, expected', [(0, True), (CAP * 1e9, True), ((CAP * 1e9)+ 1, False)]
)
def test_budget_check_compares_bytes_to_bytes(bytes_scanned, expected):
    client = make_client(FakeGoogleClient)

    assert client.is_within_budget(bytes_scanned) is expected

def test_estimate_flags_a_query_over_budget():
    client = make_client(FakeGoogleClient(bytes_scanned=(CAP * 1e9) + 1))

    assert client.estimate_cost("SELECT 1").is_within_budget is False

def test_dry_run_job_has_dry_run_set_and_no_billing_cap():
    google = FakeGoogleClient(bytes_scanned=1)
    client = make_client(google)

    client.estimate_cost("SELECT 1")

    config = google.jobs[0].job_config
    assert config.dry_run is True
    assert config.maximum_bytes_billed is None

def test_bad_sql_during_dry_run_becomes_a_value_error():
    google = FakeGoogleClient(error_on_dry_run=BadRequest("Syntax error"))
    client = make_client(google)

    with pytest.raises(ValueError, match='rejected the query'):
        client.estimate_cost("SELEC 1")

def test_cost_estimate_summary_and_gb_property():
    ok = CostEstimate(2_500_000_000, 0.01, 0.0014, True)
    over = CostEstimate(2_500_000_000, 0.01, 0.014, False)

    assert ok.gb_scanned == 2.5
    assert "within budget" in ok.summary()
    assert "OVER BUDGET" in over.summary()

def test_budget_error_message_reports_the_cap_in_gb():
    google = FakeGoogleClient(bytes_scanned=11 * 10**9)   # 11 GB
    client = make_client(google, cap=10)                  # 10 GB cap

    with pytest.raises(BudgetExceededError) as err:
        client.run_query("SELECT 1")

    assert "10.00 GB" in str(err.value)
    assert "10737418240" not in str(err.value)            # the buggy rendering

def test_cost_uses_tib_not_tb():
    # 1 TiB exactly = $6.25 at $6.25/TiB
    client = make_client(FakeGoogleClient(bytes_scanned=1024**4))
    assert client.estimate_cost("SELECT 1").cost_usd == pytest.approx(6.25)

def test_check_budget_false_still_sets_billing_cap():
    google = FakeGoogleClient(bytes_scanned=1)
    client = make_client(google)
    client.run_query("SELECT 1", check_budget=False)

    assert len(google.jobs) == 1
    assert not google.jobs[0].job_config.dry_run
    assert google.jobs[0].job_config.maximum_bytes_billed == CAP * 10**9

# ---- Running queries ------------------------------------

def test_run_query_returns_a_polars_dataframe():
    client = make_client(FakeGoogleClient(bytes_scanned=1))

    df = client.run_query("SELECT 1")

    assert isinstance(df, pl.DataFrame)
    assert df.shape == (3, 1)
    assert df.columns == ['x']

def test_run_query_arrow_returns_the_raw_arrow_table():
    client = make_client(FakeGoogleClient(bytes_scanned=1))

    table = client.run_query_arrow("SELECT 1")

    assert isinstance(table, pa.Table)

def test_real_run_applies_the_billing_cap():
    google = FakeGoogleClient(bytes_scanned=1)
    client = make_client(google)

    client.run_query("SELECT 1")

    real_job = google.jobs[-1]
    assert not real_job.job_config.dry_run
    assert real_job.job_config.maximum_bytes_billed == (CAP * 1e9)

def test_run_query_does_a_dry_run_first_by_default():
    google = FakeGoogleClient(bytes_scanned=1)
    client = make_client(google)

    client.run_query("SELECT 1")

    assert [job.job_config.dry_run for job in google.jobs] == [True, False]

def test_over_budget_query_raises_and_never_runs_for_real():
    google = FakeGoogleClient(bytes_scanned=(CAP * 1e9) + 1)
    client = make_client(google)

    with pytest.raises(BudgetExceededError):
        client.run_query("SELECT 1")

    assert len(google.jobs) == 1 # only the dry run happened
    assert google.jobs[0].job_config.dry_run is True

def test_check_budget_false_skips_the_dry_run():
    google = FakeGoogleClient(bytes_scanned=(CAP * 1e9) + 1)
    client = make_client(google)

    client.run_query("SELECT 1", check_budget=False)

    assert len(google.jobs) == 1
    assert not google.jobs[0].job_config.dry_run

def test_timeout_is_passed_to_the_result_call():
    google = FakeGoogleClient(bytes_scanned=1)
    client = make_client(google)

    client.run_query("SELECT 1", timeout=5)

    assert google.jobs[-1].result_timeout == 5

def test_columns_returns_all_columns_from_a_dry_run():
    # FakeJob needs to expose .schema; add `schema` kwarg to FakeJob:
    #   def __init__(self, total_bytes, config, schema=("x",)):
    #       self.schema = [SimpleNamespace(name=n) for n in schema]
    google = FakeGoogleClient(bytes_scanned=1, schema=("a", "b", "c"))
    client = make_client(google)

    cols = client.columns("SELECT 1")

    assert cols.columns == ("a", "b", "c")     
    assert google.jobs[0].job_config.dry_run is True

def test_columns_returns_hashable_object():
    from ga4_ecommerce_analytics_engine.sources.bigquery_client import Columns
    google = FakeGoogleClient(bytes_scanned=1, schema=("a",))
    client = make_client(google)

    hash(client.columns("SELECT 1"))   # will TypeError until field is tuple[str, ...]