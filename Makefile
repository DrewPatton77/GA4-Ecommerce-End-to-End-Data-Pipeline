# Common tasks. Run `make` to list them.
# Override dates on the command line:  make run START=2020-12-01 END=2020-12-31

START ?= 2020-11-01
END   ?= 2021-01-31
UV    := uv run

.DEFAULT_GOAL := help
.PHONY: help install test test-fast cost run refresh run-pg run-all db-up db-down db-reset db-psql clean

help:  ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync

test:  ## Run all unit tests
	$(UV) pytest tests/unit

test-fast:  ## Stop at the first failure
	$(UV) pytest tests/unit -x -q

cost:  ## Dry-run the BigQuery queries and show the cost (nothing is billed)
	$(UV) ga4-pipeline $(START) $(END) --estimate-cost

run:  ## Build the tables and write parquet files to data/output
	$(UV) ga4-pipeline $(START) $(END)

refresh:  ## Same as run, but ignore the local BigQuery cache
	$(UV) ga4-pipeline $(START) $(END) --refresh

run-pg:  ## Build the tables and load them into Postgres (needs db-up and .env)
	$(UV) --env-file .env ga4-pipeline $(START) $(END) --to postgres

run-all:  ## Write parquet files AND load Postgres
	$(UV) --env-file .env ga4-pipeline $(START) $(END) --to both

db-up:  ## Start Postgres in Docker
	@test -f .env || (echo "Missing .env: run  cp .env.example .env  and set a password" && exit 1)
	docker compose up -d --wait

db-down:  ## Stop Postgres (data is kept)
	docker compose down

db-reset:  ## Stop Postgres and DELETE its data
	docker compose down -v

db-psql:  ## Open a psql shell in the container
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

clean:  ## Remove output files and Python caches (keeps the BigQuery cache)
	rm -rf data/output .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
