"""Minimal tests for dimensions/base.py."""

from __future__ import annotations

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.dimensions.base import BaseDimension


class ColorDimension(BaseDimension):
    key = "color_id"
    columns = ("color", "shade")


@pytest.fixture
def source():
    return pl.DataFrame(
        {
            "who": ["a", "b", "c", "d"],
            "color": ["red", "red", "blue", None],
            "shade": ["dark", "dark", "light", None],
        }
    )


def test_build_gives_each_distinct_combination_one_integer_key(source):
    dim = ColorDimension().build(source)

    assert dim.columns == ["color_id", "color", "shade"]
    assert dim["color_id"].to_list() == [0, 1, 2]  # red/dark, blue/light, null/null
    assert dim.height == 3

def test_placeholder_values_are_cleaned_and_merge_into_one_row():
    messy = pl.DataFrame(
        {
            "who": ["a", "b", "c", "d"],
            "color": ["(not set)", "", None, "RED"],
            "shade": ["(none)", "<other>", "(direct)", "Dark"],
        }
    )
    dimension = ColorDimension()

    dim = dimension.build(messy)
    mapping = dimension.assign_keys(messy, dim, "who")

    # rows 1 and 2 clean to the same (unspecified, unspecified); row 3 is (unspecified, direct); row 4 is (red, dark)
    assert dim["color"].to_list() == ["unspecified", "unspecified", "red"]
    assert dim["shade"].to_list() == ["unspecified", "direct", "dark"]
    assert mapping["color_id"].to_list() == [0, 0, 1, 2]


def test_assign_keys_shares_a_key_between_matching_rows_including_nulls(source):
    dimension = ColorDimension()
    dim = dimension.build(source)

    mapping = dimension.assign_keys(source, dim, "who")

    assert mapping["who"].to_list() == ["a", "b", "c", "d"]
    assert mapping["color_id"].to_list() == [0, 0, 1, 2]
    assert mapping["color_id"].null_count() == 0  # the all-null row still found its key


def test_attach_key_adds_the_key_without_changing_the_row_count(source):
    dimension = ColorDimension()
    mapping = dimension.assign_keys(source, dimension.build(source), "who")
    facts = pl.DataFrame({"who": ["a", "a", "c"], "amount": [1, 2, 3]})

    result = dimension.attach_key(facts, mapping, on="who")

    assert result.height == 3
    assert result["color_id"].to_list() == [0, 0, 1]


def test_attach_key_refuses_a_mapping_that_would_duplicate_facts():
    mapping = pl.DataFrame({"who": ["a", "a"], "color_id": [0, 1]})

    with pytest.raises(ValueError, match="more than one row"):
        BaseDimension.attach_key(pl.DataFrame({"who": ["a"]}), mapping, on="who")


def test_first_per_entity_keeps_the_earliest_row():
    df = pl.DataFrame({"user": ["u", "u", "v"], "ts": [2, 1, 5], "city": ["B", "A", "C"]})

    result = ColorDimension().first_per_entity(df, "user", "ts")

    assert dict(zip(result["user"], result["city"])) == {"u": "A", "v": "C"}
