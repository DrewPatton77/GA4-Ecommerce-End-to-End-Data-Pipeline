'''
Load the finished tables into Postgres.

    PostgresWriter(PostgresConfig.from_env()).write(tables)

The whole load is ONE transaction: Power BI sees the old tables until the new ones are complete.
Tables are dropped and rebuilt each run (a full refresh). Constraints are added after the data is
loaded, which is much faster than loading into constrained tables, and a bad key fails the load
loudly instead of leaving broken relationships
'''

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import polars as pl
from psycopg import Connection, connect, sql

from ga4_ecommerce_analytics_engine.writers.warehouse import TableSpec, load_order, table_specs

logger = logging.getLogger(__name__)

CHUNK_ROWS = 200_000


@dataclass(frozen=True)
class PostgresConfig:
    host: str = 'localhost'
    port: int = 5432
    database: str = 'ga4'
    user: str = 'postgres'
    password: str = ''

    @classmethod
    def from_env(cls) -> "PostgresConfig":
        '''
        Reads POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
        '''
        return cls(
            host=os.environ.get('POSTGRES_HOST', cls.host),
            port=int(os.environ.get('POSTGRES_PORT', cls.port)),
            database=os.environ.get('POSTGRES_DB', cls.database),
            user=os.environ.get('POSTGRES_USER', cls.user),
            password=os.environ.get('POSTGRES_PASSWORD', cls.password),
        )

    def connect(self) -> Connection:
        return connect(
            host=self.host, port=self.port, dbname=self.database, user=self.user, password=self.password
        )


# ---- Types and DDL (pure functions, easy to test) ---------------------------------


def postgres_type(dtype: pl.DataType) -> str:
    if dtype in (pl.Int8, pl.Int16, pl.UInt8):
        return 'SMALLINT'
    if dtype in (pl.Int32, pl.UInt16):
        return 'INTEGER'
    if dtype in (pl.Int64, pl.UInt32, pl.UInt64):
        return 'BIGINT'
    if dtype in (pl.Float32, pl.Float64):
        return 'DOUBLE PRECISION'
    if dtype == pl.Boolean:
        return 'BOOLEAN'
    if dtype in (pl.Utf8, pl.Categorical):
        return 'TEXT'
    if dtype == pl.Date:
        return 'DATE'
    if dtype.base_type() == pl.Datetime:  # works for the class and for Datetime("us", tz)
        return "TIMESTAMPTZ" if getattr(dtype, "time_zone", None) else "TIMESTAMP"
    raise TypeError(f'No Postgres type for polars dtype {dtype}. Drop or convert that column first.')


def create_table_sql(name: str, table: pl.DataFrame, schema_name: str) -> sql.Composed:
    columns = sql.SQL(", ").join(
        sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(postgres_type(dtype)))
        for column, dtype in table.schema.items()
    )
    return sql.SQL('CREATE TABLE {} ({})').format(sql.Identifier(schema_name, name), columns)


# ---- The writer -----------------------------------------------------------------


class PostgresWriter:
    def __init__(self, config: PostgresConfig | None = None, schema_name: str = "ga4", specs=None) -> None:
        self.config = config or PostgresConfig.from_env()
        self.schema_name = schema_name
        self.specs: dict[str, TableSpec] = specs or table_specs()

    def write(self, tables: dict[str, pl.DataFrame]) -> None:
        unknown = set(tables) - set(self.specs)
        if unknown:
            raise ValueError(f'No table spec for: {sorted(unknown)}. Add them to writers/warehouse.py.')
        self._check_primary_keys(tables)

        order = [name for name in load_order(self.specs) if name in tables]
        with self.config.connect() as conn:  # commits on success, rolls everything back on error
            with conn.cursor() as cur:
                cur.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(self.schema_name)))
                for name in reversed(order):
                    cur.execute(sql.SQL('DROP TABLE IF EXISTS {} CASCADE').format(self._ident(name)))
                for name in order:
                    cur.execute(create_table_sql(name, tables[name], self.schema_name))
                    self._copy(cur, name, tables[name])
                for name in order:
                    self._add_constraints(cur, self.specs[name], tables[name])
                for name in order:
                    cur.execute(sql.SQL('ANALYZE {}').format(self._ident(name)))
        logger.info("Loaded %d tables into schema '%s'", len(order), self.schema_name)

    # ---- Steps ----------------------------------------------------------------

    def _copy(self, cur, name: str, table: pl.DataFrame) -> None:
        columns = sql.SQL(', ').join(sql.Identifier(c) for c in table.columns)
        statement = sql.SQL('COPY {} ({}) FROM STDIN WITH (FORMAT csv)').format(self._ident(name), columns)
        with cur.copy(statement) as copy:
            for offset in range(0, table.height, CHUNK_ROWS):  # in chunks, so big tables never become one giant string
                chunk = table.slice(offset, CHUNK_ROWS)
                copy.write(chunk.write_csv(include_header=False).encode("utf-8"))
        logger.info('Loaded %-26s %9d rows', name, table.height)

    def _add_constraints(self, cur, spec: TableSpec, table: pl.DataFrame) -> None:
        if spec.primary_key:
            cur.execute(
                sql.SQL('ALTER TABLE {} ADD PRIMARY KEY ({})').format(
                    self._ident(spec.name), sql.SQL(", ").join(sql.Identifier(c) for c in spec.primary_key)
                )
            )
        for fk in spec.foreign_keys:
            if fk.column not in table.columns:  # e.g. a schema without that dimension
                logger.debug('%s has no column %s: skipping its foreign key', spec.name, fk.column)
                continue
            cur.execute(
                sql.SQL('ALTER TABLE {} ADD FOREIGN KEY ({}) REFERENCES {} ({})').format(
                    self._ident(spec.name), sql.Identifier(fk.column),
                    self._ident(fk.ref_table), sql.Identifier(fk.ref_column),
                )
            )
            cur.execute(
                sql.SQL('CREATE INDEX {} ON {} ({})').format(
                    sql.Identifier(f"ix_{spec.name}_{fk.column}"), self._ident(spec.name), sql.Identifier(fk.column)
                )
            )

    def _check_primary_keys(self, tables: dict[str, pl.DataFrame]) -> None:
        '''
        Fail before touching the database if a primary key column is missing or not unique
        '''
        for name, table in tables.items():
            key = list(self.specs[name].primary_key)
            if not key:
                continue
            missing = [c for c in key if c not in table.columns]
            if missing:
                raise ValueError(f'{name} is missing primary key column(s) {missing}')
            if table.select(key).is_duplicated().any():
                raise ValueError(f'{name} has duplicate values in its primary key {key}')

    def _ident(self, name: str) -> sql.Identifier:
        return sql.Identifier(self.schema_name, name)
