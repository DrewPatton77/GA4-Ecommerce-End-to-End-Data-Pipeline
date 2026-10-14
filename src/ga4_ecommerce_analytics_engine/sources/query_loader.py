'''
Load .sql files and render them a BigQuery queries ready to run.

Templates uses {{double_brace}} placeholders, so single braces (regex quantifier 
like {2,}) and dollar signs (regex anchors) in the SQL are left untouched.

Example template (sql/bigquery/events.sql):

    SELECT ...
    FROM `{{DATASET}}.{{TABLE}}`
    WHERE _TABLE_SUFFIX BETWEEN '{{start_date}}' AND '{{end_date}}'
'''

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from ga4_ecommerce_analytics_engine.constants import (
    DATASET,
    TABLE
)

# <repo root>/sql/bigquery, resolved from src/<package>/sources/query_loader.py
repo_root = Path(__file__).resolve().parents[3] 
DEFAULT_SQL_DIR = repo_root / "sql" / "bigquery"

# Regex to capture any text inside curly brackets (e.g., {DATASET}, {TABLE}, {start_date}, {end_date}):
    # • \{\{: Matches a literal pair of opening curly braces {{.
    # • \s*: Optional spaces inside the braces.
    # • ([^}]+): Captures everything inside until it hits a closing brace (you can also use ([\w.]+) if you want to strictly limit it to word characters and dots).
    # • \s*: Optional spaces before the closing braces.
    # • \}\}: Matches a literal pair of closing curly braces }}.
_PLACEHOLDER = re.compile(r"\{\{\s*([^}]+)\s*\}\}")



class QueryLoader:
    '''
    Finds .sql templates and fills in their placeholders.
    '''

    def __init__(
        self,
        sql_dir: Path | str = DEFAULT_SQL_DIR,
        dataset: str = DATASET,
        table: str = TABLE
    ) -> None:

        self.sql_dir = Path(sql_dir)
        self._default = {
            'DATASET': dataset,
            'TABLE': table
        }
        self._cache: dict[str, str] = {}

    # ---- Loading -----------------------------

    def available(self) -> list[str]:
        '''
        Names of the templates in the SQL folder (without the .sql extension)
        '''
        return sorted(path.stem for path in self.sql_dir.glob("*.sql"))

    def load(self, name: str) -> str:
        '''
        Read the raw, unrendered text of a template (i.e., 'events').
        '''
        if name not in self._cache:
            path = self.sql_dir / f"{name}.sql"
            if not path.is_file():
                raise FileNotFoundError(
                    f"No SQL template named '{name}' in {self.sql_dir}."
                    f"Available: {self.available()}"
                )
            self._cache[name] = path.read_text(encoding="utf-8")
        return self._cache[name]

    # --- Rendering --------------------------------------

    def render(
        self,
        name: str,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        **extra: str,
    ) -> str:
        '''
        Load a template and fill in its placeholders.

        Args:
            name: Template name without extension, e.g. 'events'.
            start_date: First day to include (YYYY-MM-DD, YYYYMMDD, or a date).
            end_date: Last day to include
            **extra: Any additional placeholder values the template needs.

        Raises:
            ValueError: if a date invalid, the range is reversed, or the 
                template contains a placeholder that has no value.
        '''
        start = self._to_table_suffix(start_date)
        end = self._to_table_suffix(end_date)
        if start > end:
            raise ValueError(f"start_date ({start_date}) is after end_date ({end_date}).")


        values = {**self._default, **extra, 'start_date': start, 'end_date': end}
        text = self.load(name)

        def substitute(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in values:
                raise ValueError(
                    f"Template '{name}' uses {{{{{key}}}}} but no value was provided. "
                    f"Known values: {sorted(values)}"
                )
            return str(values[key])

        return _PLACEHOLDER.sub(substitute, text)

    # ---- Helpers --------------------------------------

    @staticmethod
    def _to_table_suffix(value: str | date | datetime) -> str:
        '''
        Convert a date to the YYYYMMDD form BigQuery's _TABLE_SUFFIX expects.

        A wrongly formatted date silently matches no tables, so reject it here.
        '''
        if isinstance(value, datetime):
            return value.strftime('%Y%m%d')
        if isinstance(value, date):
            return value.strftime('%Y%m%d')
        for fmt in ('%Y-%m-%d', '%Y%m%d'):
            try:
                return datetime.strptime(value, fmt).strftime('%Y%m%d')
            except ValueError:
                continue
        raise ValueError(
            f"Invalid date '{value}'. Use YYYY-MM-DD or YYYYMMDD."
        )
            
