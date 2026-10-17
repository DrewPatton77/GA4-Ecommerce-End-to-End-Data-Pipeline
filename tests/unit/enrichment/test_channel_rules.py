

from __future__ import annotations

import pytest

from ga4_ecommerce_analytics_engine.enrichment.channel_rules import (
    ChannelRule,
    Criterion,
    DataChannelRule,
    eq
)

@pytest.mark.parametrize(
    'args',
    [
        ('country', 'equals', ('x',)), # Unknown column
        ('source_utm', 'starts_with', ('x',)), # Unknown operator
        ('source_utm', 'in', ()), # No value
    ],
)
def test_invalid_criteria_are_rejected(args):
    with pytest.raises(ValueError):
         Criterion(*args)

def test_invalid_rules_are_rejected():
    with pytest.raises(ValueError):
            ChannelRule('', (eq('source_utm', 'a'),))
    with pytest.raises(ValueError):
        ChannelRule('Direct', ())

def test_default_rules_are_valid_and_start_with_direct():
     rules = DataChannelRule().channel_rules()

     assert rules[0].label == 'Direct'
     assert all(isinstance(r, ChannelRule) for r in rules)
