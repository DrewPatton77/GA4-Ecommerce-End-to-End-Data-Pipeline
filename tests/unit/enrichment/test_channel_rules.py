

from __future__ import annotations

import pytest

from ga4_ecommerce_analytics_engine.enrichment.channel_rules import (
    ChannelRule,
    Criterion,
    DataChannelRule,
    one_of
)

@pytest.mark.parametrize(
    'args',
    [
        ('country', 'one', ('x',)), # Unknown column
        ('source_utm', 'starts_with', ('x',)), # Unknown operator
        ('source_utm', 'one_of', ()), # No value
    ],
)
def test_invalid_criteria_are_rejected(args):
    with pytest.raises(ValueError):
        Criterion(*args)
        ChannelRule('X', ('not a criterion',))

def test_invalid_rules_are_rejected():
    with pytest.raises(ValueError):
            ChannelRule('', (one_of('source_utm', 'a'),))
    with pytest.raises(ValueError):
        ChannelRule('Direct', ())

def test_default_rules_are_valid_and_start_with_direct():
    rules = DataChannelRule().channel_rules()

    assert rules[0].label == 'Direct'
    assert all(isinstance(r, ChannelRule) for r in rules)
    # Direct is a two-clause rule — pins the AND semantics
    assert len(rules[0].clauses) == 2
    assert all(isinstance(c, Criterion) for c in rules[0].clauses)
    # Every rule's label is a non-empty string
    assert all(r.label for r in rules)
    # No duplicate-label rules are unintentional (currently: Direct appears twice)
    labels = [r.label for r in rules]
    assert labels.count('Direct') == 2   # documents the current OR pattern

