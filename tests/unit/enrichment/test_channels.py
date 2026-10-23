from __future__ import annotations

import polars as pl
import pytest

from ga4_ecommerce_analytics_engine.enrichment.channel_rules import ChannelRule, one_of
from ga4_ecommerce_analytics_engine.enrichment.channels import DataChannelClassifier


def classify(rows: list[tuple], classifier: DataChannelClassifier | None = None) -> list[str]:
    sessions = pl.DataFrame(
        rows,
        schema={"source_utm": pl.Utf8, "medium_utm": pl.Utf8, "campaign_utm": pl.Utf8},
        orient="row",
    )
    return (classifier or DataChannelClassifier()).classify(sessions)["channel"].to_list()


CHANNEL_CASES = [
    pytest.param("(direct)", "(none)", "Direct", id="direct"),
    pytest.param("googlemerchandisestore", "referral", "Direct", id="direct-merch-store"),
    pytest.param("google", "cpc", "Paid Search", id="paid-search"),
    pytest.param("mail.google.com", "referral", "Email", id="email"),
    pytest.param("my-newsletter", "email", "Newsletter", id="newsletter"),
    pytest.param("google", "organic", "Organic Search", id="organic-search"),
    pytest.param("facebook", "social", "Organic Social", id="organic-social"),
    pytest.param("docs.google.com", "referral", "Internal", id="internal"),
    pytest.param("some-site.com", "unknown", "Referral", id="referral-by-domain"),
    pytest.param("other", "referral", "Referral", id="referral-by-medium"),
    pytest.param("something-else", "something-else", "Unclassified", id="unclassified"),
    pytest.param("google", "(none)", "Direct", id="direct-medium-only"),
    pytest.param("some-site.com", "organic", "Referral", id="referral-by-domain-non-referral-medium"),
]


@pytest.mark.parametrize(("source", "medium", "expected"), CHANNEL_CASES)
def test_each_channel(source, medium, expected):
    assert classify([(source, medium, None)]) == [expected]


def test_a_criterion_only_looks_at_its_own_column():
    # 'cpc' as a *source* must not trigger the medium == 'cpc' rule.
    assert classify([("cpc", "something-else", None)]) == ["Unclassified"]


def test_a_tuple_clause_requires_every_criterion():
    classifier = DataChannelClassifier()
    classifier.rules = (ChannelRule("Mine", ((one_of("source_utm", "a"), one_of("medium_utm", "b")),)),)

    assert classify([("a", "b", None), ("a", "x", None), ("z", "b", None)], classifier) == [
        "Mine",
        "Unclassified",
        "Unclassified",
    ]


def test_first_matching_rule_wins():
    # Matches Direct (normalised source) and Paid Search (medium); Direct is listed first.
    assert classify([("googlemerchandisestore.com", "cpc", None)]) == ["Direct"]


def test_values_are_lowercased_trimmed_and_sources_normalised():
    assert classify([("  GOOGLE ", " CPC ", None)]) == ["Paid Search"]
    assert classify([("m.facebook.com", "social", None)]) == ["Organic Social"]


def test_nulls_do_not_crash_and_are_unclassified():
    assert classify([(None, None, None)]) == ["Unclassified"]

def test_empty_rules_returns_unclassified():
    classifier = DataChannelClassifier()
    classifier.rules = ()
    assert classify([("google", "cpc", None)], classifier) == ["Unclassified"]

def test_empty_dataframe_returns_empty_with_channel_column():
    empty = pl.DataFrame(schema={"source_utm": pl.Utf8, "medium_utm": pl.Utf8, "campaign_utm": pl.Utf8})
    result = DataChannelClassifier().classify(empty)
    assert result.height == 0
    assert "channel" in result.columns

def test_normalization_does_not_cascade():
    # If a source matches one pattern, it shouldn't trigger a *later* pattern's replacement
    # (only matters if two patterns could overlap)
    assert classify([("googlemerchandisestore.com", "referral", None)]) == ["Direct"]