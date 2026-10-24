"""Tests for aggregation/journeys.py (JourneyBuilder) on small hand-made frames."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.aggregation.journeys import JourneyBuilder

T0 = dt.datetime(2020, 12, 1, 9, 0, 0)
D1 = dt.date(2020, 12, 1)
D3 = dt.date(2020, 12, 3)

SCHEMA = {
    "user_pseudo_id": pl.Utf8,
    "session_start": pl.Datetime,
    "session_date": pl.Date,
    "channel": pl.Utf8,
    "converted": pl.Int8,
    "value": pl.Float64,
}


def make_sessions() -> pl.DataFrame:
    rows = [
        # u1: three sessions over 50 hours, converting in the middle one
        ("u1", T0, D1, "Direct", 0, None),
        ("u1", T0 + dt.timedelta(hours=2), D1, "Paid Search", 1, 50.0),
        ("u1", T0 + dt.timedelta(hours=50), D3, "Direct", 0, None),
        # u2: one converting session
        ("u2", T0, D1, "Organic Search", 1, 20.0),
        # u3: one non-converting session
        ("u3", T0, D1, "Direct", 0, None),
    ]
    return pl.DataFrame(rows, schema=SCHEMA, orient="row")


def by_user(df: pl.DataFrame) -> dict[str, dict]:
    return {row["user_pseudo_id"]: row for row in df.iter_rows(named=True)}


@pytest.fixture
def result():
    return JourneyBuilder().build(make_sessions())


@pytest.fixture
def journeys(result):
    return by_user(result.journeys)


@pytest.fixture
def converting(result):
    return by_user(result.converting)


# ---- All journeys ------------------------------------------------------------


def test_one_row_per_user(result):
    assert result.journeys.height == 3


def test_path_is_in_time_order_even_if_input_is_shuffled():
    shuffled = make_sessions().reverse()

    journeys = by_user(JourneyBuilder().build(shuffled).journeys)

    assert journeys["u1"]["conversion_path"] == ["Direct", "Paid Search", "Direct"]


def test_touchpoints_and_unique_channels(journeys):
    assert journeys["u1"]["touchpoints"] == 3
    assert journeys["u1"]["channel_set"] == ["Direct", "Paid Search"]
    assert journeys["u2"]["touchpoints"] == 1


def test_conversion_counts_and_value(journeys):
    assert journeys["u1"]["conversion_count"] == 1
    assert journeys["u1"]["conversion_value_usd"] == 50.0
    assert journeys["u1"]["has_conversion"] is True
    assert journeys["u3"]["conversion_count"] == 0
    assert journeys["u3"]["conversion_value_usd"] == 0.0
    assert journeys["u3"]["has_conversion"] is False


def test_journey_dates(journeys):
    assert journeys["u1"]["journey_start"] == D1
    assert journeys["u1"]["journey_end"] == D3


def test_hours_before_counts_back_from_the_last_session(journeys):
    assert journeys["u1"]["hours_before"] == pytest.approx([50.0, 48.0, 0.0])
    assert journeys["u2"]["hours_before"] == pytest.approx([0.0])


def test_duration_is_the_time_from_first_to_last_session(journeys):
    assert journeys["u1"]["duration"] == pytest.approx(50.0)
    assert journeys["u3"]["duration"] == pytest.approx(0.0)

# ---- Converting journeys -----------------------------------------------------


def test_only_converting_users_are_kept(result):
    assert set(result.converting["user_pseudo_id"]) == {"u1", "u2"}


def test_printable_paths(converting):
    assert converting["u1"]["path_to_conversion"] == "Direct > Paid Search > Direct"
    assert converting["u2"]["path_to_conversion"] == "Organic Search"

    # The hours list stays a list; the printable version lives in a text column (whatever it is named).
    assert converting["u1"]["hours_before"] == pytest.approx([50.0, 48.0, 0.0])
    assert "50 > 48 > 0" in converting["u1"].values()
    assert "0" in converting["u2"].values()


def test_missing_required_column_raises_a_readable_error():
    with pytest.raises(KeyError, match="channel"):
        JourneyBuilder().build(make_sessions().drop("channel"))