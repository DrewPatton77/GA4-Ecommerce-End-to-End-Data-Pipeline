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


def test_touchpoint_count_is_the_number_of_journeys_with_that_length(journeys):
    assert journeys["u1"]["touchpoint_count"] == 1  # only one 3-touchpoint journey
    assert journeys["u2"]["touchpoint_count"] == 2  # u2 and u3 are both 1-touchpoint
    assert journeys["u3"]["touchpoint_count"] == 2


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


def test_duration_bins_cover_every_journey_including_the_longest(journeys):
    assert journeys["u3"]["duration_bins"] == 0
    assert journeys["u1"]["duration_bins"] == 19  # the maximum lands in the last bin
    assert journeys["u3"]["duration_labels"].startswith("0m")  # first bin starts at zero
    assert journeys["u1"]["duration_labels"].endswith("2d")  # last bin ends at the 50-hour maximum


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


def test_value_bins_cover_the_smallest_and_largest_values(converting):
    assert converting["u2"]["value_bins"] == 0  # $20, the minimum
    assert converting["u1"]["value_bins"] == 19  # $50, the maximum
    assert converting["u2"]["value_labels"].startswith("$20 - ")
    assert converting["u1"]["value_labels"].endswith(" - $50")


def test_zero_value_is_left_out_of_the_bins():
    sessions = pl.DataFrame(
        [
            ("a", T0, D1, "Direct", 1, 0.0),
            ("b", T0, D1, "Direct", 1, 30.0),
        ],
        schema=SCHEMA,
        orient="row",
    )

    converting = by_user(JourneyBuilder().build(sessions).converting)

    assert converting["a"]["conversion_value_usd"] is None
    assert converting["a"]["value_bins"] is None
    assert converting["b"]["value_bins"] is not None


def test_bin_counts_are_configurable():
    result = JourneyBuilder(n_duration_bins=5, n_value_bins=5).build(make_sessions())

    assert max(result.journeys["duration_bins"]) == 4
    assert max(result.converting["value_bins"]) == 4


def test_missing_required_column_raises_a_readable_error():
    with pytest.raises(KeyError, match="channel"):
        JourneyBuilder().build(make_sessions().drop("channel"))