'''
Tests for query_loader.py Uses the fixtures in tests / conftest.py.

Runs tests using temporary .sql files.
'''

from __future__ import annotations

import datetime as dt

import pytest

def test_available_lists_the_templates(loader):
    assert loader.available() == ['dimensions', 'events', 'items']

def test_render_fills_in_every_placeholder(loader):
    sql = loader.render('events', '2020-11-01', '2021-01-31')

    assert "`proj.dataset.events_*`" in sql
    assert "BETWEEN '20201101' AND '20210131'"
    assert "{{" not in sql

def test_render_leaves_regex_braces_and_anchors_alone(loader):
    sql = loader.render("events", '2020-11-01', '2020-11-02')

    assert "a{2,}$" in sql

@pytest.mark.parametrize(
    "start, end",
    [
        ('2020-11-01', '2020-11-02'),
        ('20201101', 20201102),
        (dt.date(2020, 11, 1), dt.date(2020,11,2)),
        (dt.datetime(2020, 11, 1, 5, 30), dt.datetime(2020, 11, 2, 23, 59)),
    ],
)
def test_every_accepted_date_format_renders_the_same_query(loader, start, end):
    expected = loader.render('events', '2020-11-01', '2020-11-02')

    assert loader.render('events', start, end) == expected

@pytest.mark.parametrize(
    'bad_date', ['2020/11/01', '11-01-2020', 'not a date', '', '2020-13-01']
)
def test_invalid_dates_are_rejected(loader, bad_date):
    with pytest.raises(ValueError, match='Invalid date'):
        loader.render('events', bad_date, '2020-11-02')

def test_start_equal_to_end_is_allowed_inclusive(loader):
    sql = loader.render('events', '2020-11-01', '2020-11-01')
    assert "BETWEEN '20201101' AND '20201101'" in sql

def test_reversed_date_range_is_rejected(loader):
    with pytest.raises(ValueError, match="is after"):
        loader.render('events', '2020-11-02', '2020-11-01')

def test_reversed_date_range_is_rejected(loader):
    sql = loader.render('events', '2020-11-01', '2020-11-01')

    assert "BETWEEN '20201101' AND '20201101'" in sql

def test_missing_template_error_lists_what_exists(loader):
    with pytest.raises(FileNotFoundError, match="No SQL template named 'nope'") as err:
        loader.render('nope', '2020-11-01', '2020-11-02')

    assert 'events' in str(err.value)

def test_integer_date_is_accepted(loader):
    assert loader.render("events", 20201101, 20201102) == loader.render(
        "events", "2020-11-01", "2020-11-02"
    )

@pytest.mark.parametrize("sloppy", ["2020-1-1", "2020-01-1", "2020-1-01"])
def test_non_padded_dates_are_currently_accepted(loader, sloppy):
    # Current behaviour — either document or tighten with a round-trip check
    assert "BETWEEN '20200101'" in loader.render("events", sloppy, "2020-01-02")

def test_unfilled_placeholder_raises_instead_of_sending_broken_sql(loader, sql_dir):
    (sql_dir / 'broken.sql').write_text('SELECT {{unknown_thing}}', encoding='utf-8')

    with pytest.raises(ValueError, match='unknown_thing'):
        loader.render('broken', '2020-11-01', '2020-11-02')

def test_default_sql_dir_resolves_to_the_repo_root():
    from ga4_ecommerce_analytics_engine.sources.query_loader import DEFAULT_SQL_DIR
    assert (DEFAULT_SQL_DIR / "events.sql").is_file()


def test_extra_values_can_fill_custom_placeholders(loader, sql_dir):
    (sql_dir / 'custom.sql').write_text("SELECT '{{label}}'", encoding='utf-8')

    sql=loader.render('custom', '2020-11-01', '2020-11-02', label='hello')

    assert sql == "SELECT 'hello'"

def test_template_text_is_cached_after_the_first_load(loader, sql_dir):
    first = loader.load('events')
    (sql_dir / 'events.sql').write_text("SELECT 'edited'", encoding='utf-8')

    # Document current behaviour: edits need a new QueryLoader (or a restart).
    assert loader.load('events') == first