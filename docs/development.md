# Development

    uv sync            # install
    make test          # unit tests
    make test-fast     # stop at the first failure
    make cost          # dry-run BigQuery, nothing billed
    make run           # parquet to data/output
    make run-pg        # load Postgres
    make run-all       # both

## Tests

A handful of focused tests per module under `tests/unit/`. The network tests use two small triangles of items. Polars logic is tested on tiny hand-built frames.
Pure Python (CLI, load order, type mapping) is tested directly. The Postgres `COPY` and constraint code is checked by a
real `make run-pg`.

## Changing things

- **Rename a column:** edit `schema.py` only. Do not override names per instance.

- **Change a channel:** edit `enrichment/channel_rules.py`. The first match wins. Clauses are OR-ed, criteria inside a
  clause are AND-ed (for making a new channel rule).

- **Add a table:** build it in a `facts/` or `dimensions/` module, add it to `Pipeline.run`, then add a spec in
  `writers/warehouse.py` (primary key, foreign keys) and a row in `docs/tables.md`.

- **Add an attribution model:** add `(name, description)` to `MODELS` and a share expression in
  `_credit_expressions`. The test that every journey's credit sums to 1 covers it.

- **Change the network filters:** `CooccurrenceNetwork` takes `min_cooccurrence` (floor, 4 and above are kept), `alpha`
  (0.05), `min_degree` (8; it is compared with an edge's co-occurrence, and a very large value turns the exemption off)
  and `n_hubs`. After a change, check
  `fact_network_stage` and the modularity on its last row (this project aims for 0.65 to 0.8).

## Reading the data

The source data is incomplete at the end of the period (README, Data quality). When a number looks wrong in the last
days, check the share of purchase events with no revenue before looking for a bug: the pipeline drops them and never
fills them in.

