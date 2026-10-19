
from __future__ import annotations

from datetime import date

import pytest

from ga4_ecommerce_analytics_engine.cli import DEFAULT_OUTPUT_DIR, parse_args


def test_dates_are_parsed_and_defaults_applied():
    args = parse_args(["2020-11-01", "2021-01-31"])

    assert (args.start_date, args.end_date) == (date(2020, 11, 1), date(2021, 1, 31))
    assert args.output_dir == DEFAULT_OUTPUT_DIR
    assert not (args.no_cache or args.refresh or args.estimate_cost)


@pytest.mark.parametrize(
    'argv',
    [
        pytest.param(['2021-02-01', '2021-01-01'], id='end-before-start'),
        pytest.param(['2021-13-01', '2021-01-01'], id='bad-date'),
    ],
)
def test_bad_dates_are_rejected(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)
