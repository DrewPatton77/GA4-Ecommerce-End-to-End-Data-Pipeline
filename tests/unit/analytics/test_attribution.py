'''
Minimal tests for analytics/attribution.py (AttributionAnalyzer)
'''

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.analytics.attribution import MODELS, AttributionAnalyzer

T0 = datetime(2020, 12, 1)


def make_sessions(paths: dict[str, list[tuple[str, float]]]) -> pl.DataFrame:
    '''
    paths: user -> [(channel, hours after T0), ...] in time order
    '''
    rows = []
    for user, path in paths.items():
        for k, (channel, hours) in enumerate(path):
            start = T0 + timedelta(hours=hours)
            rows.append((user, f"{user}-{k}", start, start.date(), channel))
    schema = {
        "user_pseudo_id": pl.Utf8, "session_id": pl.Utf8, "session_start": pl.Datetime,
        "session_date": pl.Date, "channel": pl.Utf8,
    }
    return pl.DataFrame(rows, schema=schema, orient="row")


def make_converting(values: dict[str, float]) -> pl.DataFrame:
    return pl.DataFrame(
        {"user_pseudo_id": list(values), "converting_journey_id": list(range(len(values))),
         "conversion_value_usd": list(values.values())},
        schema={"user_pseudo_id": pl.Utf8, "converting_journey_id": pl.Int64, "conversion_value_usd": pl.Float64},
    )


def by_channel(sessions: pl.DataFrame, result, model: str, column: str = "credit") -> dict[str, float]:
    model_id = result.models.filter(pl.col("attribution_model") == model)["attribution_model_id"][0]
    facts = result.facts.filter(pl.col("attribution_model_id") == model_id)
    summed = facts.join(sessions.select("session_id", "channel"), on="session_id").group_by("channel").agg(pl.col(column).sum())
    return dict(zip(summed["channel"], summed[column]))


def test_heuristic_models_split_one_journey_as_documented():
    sessions = make_sessions({"u1": [("Direct", 0), ("Paid Search", 24), ("Email", 48)]})
    result = AttributionAnalyzer().build(sessions, make_converting({"u1": 100.0}))

    assert by_channel(sessions, result, "First-Click") == {"Direct": 1.0}
    assert by_channel(sessions, result, "Last-Click") == {"Email": 1.0}
    assert by_channel(sessions, result, "Last-Click Non-Direct") == {"Email": 1.0}
    assert by_channel(sessions, result, "Linear") == pytest.approx({"Direct": 1 / 3, "Paid Search": 1 / 3, "Email": 1 / 3})
    assert by_channel(sessions, result, "Position-Based") == pytest.approx({"Direct": 0.4, "Paid Search": 0.2, "Email": 0.4})
    assert by_channel(sessions, result, "Position-Based", "revenue_credit") == pytest.approx(
        {"Direct": 40.0, "Paid Search": 20.0, "Email": 40.0}
    )


def test_last_click_non_direct_falls_back_to_the_last_session_when_every_session_is_direct():
    sessions = make_sessions({"u1": [("Direct", 0), ("Direct", 24)], "u2": [("Email", 0), ("Direct", 24)]})
    result = AttributionAnalyzer().build(sessions, make_converting({"u1": 10.0, "u2": 10.0}))

    # u1 has only Direct sessions, so Direct keeps u1's credit; u2 skips its Direct session and credits Email
    assert by_channel(sessions, result, "Last-Click Non-Direct") == {"Direct": 1.0, "Email": 1.0}


def test_time_decay_halves_the_weight_every_half_life():
    sessions = make_sessions({"u1": [("A", 0), ("B", 168)]})  # A is one half-life (168 h) before the last session
    result = AttributionAnalyzer().build(sessions, make_converting({"u1": 90.0}))

    assert by_channel(sessions, result, "Time-Decay") == pytest.approx({"A": 1 / 3, "B": 2 / 3})


def test_shapley_splits_between_distinct_channels_then_between_that_channels_sessions():
    sessions = make_sessions({"u1": [("A", 0), ("A", 1), ("B", 2)]})
    result = AttributionAnalyzer().build(sessions, make_converting({"u1": 10.0}))

    assert by_channel(sessions, result, "Shapley Value") == pytest.approx({"A": 0.5, "B": 0.5})
    shapley_id = result.models.filter(pl.col("attribution_model") == "Shapley Value")["attribution_model_id"][0]
    rows = result.facts.filter(pl.col("attribution_model_id") == shapley_id).sort("touch_number")
    assert rows["credit"].to_list() == pytest.approx([0.25, 0.25, 0.5])  # A's half is shared by its two sessions


def test_markov_removal_effect_gives_everything_to_the_channel_conversions_depend_on():
    # Everyone who converted came through Email; everyone who did not only saw Direct.
    sessions = make_sessions({"u1": [("Email", 0)], "u2": [("Email", 0)], "u3": [("Direct", 0)], "u4": [("Direct", 0)]})
    analyzer = AttributionAnalyzer()
    users = analyzer.converting_users(make_converting({"u1": 10.0, "u2": 10.0}))

    effects = analyzer.removal_effects(analyzer.touches(sessions), users)

    assert effects == pytest.approx({"Direct": 0.0, "Email": 1.0})


def test_every_model_shares_out_each_journeys_credit_and_revenue_exactly():
    sessions = make_sessions(
        {
            "u1": [("Direct", 0), ("Email", 30), ("Paid Search", 60)],
            "u2": [("Email", 0)],
            "u3": [("Paid Search", 0), ("Direct", 200)],
            "u4": [("Direct", 0)],  # never converts, but still shapes the Markov chain
            "u5": [("Email", 0), ("Direct", 10), ("Email", 20)],  # same
        }
    )
    values = {"u1": 90.0, "u2": 50.0, "u3": 20.0}
    result = AttributionAnalyzer().build(sessions, make_converting(values))

    assert result.models["attribution_model"].to_list() == [name for name, _ in MODELS]
    per_journey = result.facts.group_by("attribution_model_id", "converting_journey_id").agg(
        pl.col("credit").sum(), pl.col("revenue_credit").sum()
    )
    assert per_journey.height == len(MODELS) * len(values)  # every model credits every converting journey
    assert per_journey["credit"].to_list() == pytest.approx([1.0] * per_journey.height)
    expected = {i: v for i, v in enumerate(values.values())}  # journey id -> revenue
    for row in per_journey.iter_rows(named=True):
        assert row["revenue_credit"] == pytest.approx(expected[row["converting_journey_id"]])
