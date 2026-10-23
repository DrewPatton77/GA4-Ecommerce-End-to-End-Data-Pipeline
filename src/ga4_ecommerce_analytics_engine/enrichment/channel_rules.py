'''
Set-up channel rules for marketing source / medium / campaign


----> To change channel rules, edit this file. <----


------
Rules are checked in priority order, such that the first match is priority.

A rule matches when ALL of its clauses match.
A clause is either a single Criterion, or a tuple of Criterion objects that must ALL hold.

Multiple rules with the same label are OR'd together — the first matching rule
(in priority order) assigns the label.

Criteria compare against the lower-cased, trimmed source / medium / campaign:
    contains, one_of

The structure is as follows:
    - Channel Rules:
        - label
            - Clause: tuple[Criterion]
                = Criterion  
                - Criterion
        - label
            - Clause
                - Criterion
        ...
        

Let us look at a simple example to get the structure down:
    ChannelRule('Direct', (
            eq(source, '(direct)'),       # clause 1: single Criterion
            eq(medium, '(none)'),         # clause 2: single Criterion
            # Both must hold → source==direct AND medium==none
        )),
        ChannelRule('Direct', (
            eq(source, 'googlemerchandisestore'),  # second Direct rule, OR'd with the first
        )),
        ...
        - (edit, remove or add)
'''

from __future__ import annotations

from dataclasses import dataclass, field
from ga4_ecommerce_analytics_engine.schema import DataSchema

# --- Internals ----> DO NOT EDIT BELOW THIS LINE. SEE BOTTOM OF PAGE <---------------------------------

schema = DataSchema()

OPERATORS = ('contains', 'in') # 
UNCLASSIFIED_LABEL = 'Unclassified' # When no rules match, the rule returns an 'Unclassified' rule.
SOURCES = (schema.source_utm, schema.medium_utm, schema.campaign_utm)

@dataclass(frozen=True)
class Criterion:
    source: str 
    operator: str 
    values: tuple[str, ...]
    
    unclassified_label: str = field(default=UNCLASSIFIED_LABEL, init=False)
        
    def __post_init__(self) -> None: 
        
        if self.source not in SOURCES:
            raise ValueError(f"Unknown field '{self.source}'. Use one of {SOURCES}")
        if self.operator not in OPERATORS:
            raise ValueError(f"Unkown operator '{self.operator}'. Use one of {OPERATORS}")
        if not self.values:
            raise ValueError("A criterion needs at least one value.")
        if self.operator in ('equals', 'regex') and len(self.values) != 1:
            raise ValueError(f"'{self.operator}' takes exactly one value")

Clause = Criterion | tuple[Criterion, ...]

@dataclass(frozen=True)
class ChannelRule:
    label: str
    clauses: tuple[Clause, ...]

    def __post_init__(self) -> None:        
        if not self.label:
            raise ValueError("A channel rule needs a label.")
        if not self.clauses:
            raise ValueError(f"Rule '{self.label}' needs at least one clause")


# --- Short constructors so the channel rules read like a table -----


def one_of(field: str, *values: str) -> Criterion:
    return Criterion(field, "in", tuple(values))

def contains(field: str, *fragments: str) -> Criterion:
    return Criterion(field, 'contains', tuple(fragments))


# ---- Main -----> EDIT HERE! DO NOT EDIT ABOVE THIS LINE <----------------------------

class DataChannelRule:
    def __init__(self):
        self.source_utm = schema.source_utm
        self.medium_utm = schema.medium_utm
        self.campaign_utm = schema.campaign_utm

        # Source normalization
        self.source_normalization: tuple[tuple[str, str], ...] = (
            ('googlesyndication', 'googlesyndication'),
            ('bing', 'bing'),
            ('yahoo', 'yahoo'),
            ('facebook', 'facebook'),
            ('reddit', 'reddit'),
            ('googlemerchandisestore.com', 'googlemerchandisestore'),
            ('doubleclick.net', 'doubleclick'),
            ('qwiklabs', 'qwiklabs')
        )

    def channel_rules(self) -> tuple[ChannelRule, ...]:
        '''
        Can config: Add or remove some channel rules.
        '''
        return (
            ChannelRule(
                'Direct',
                (
                    one_of(self.source_utm, '(direct)'), 
                    one_of(self.medium_utm, '(none)'),
                ),
            ),
            ChannelRule('Direct', (one_of(self.source_utm, 'googlemerchandisestore'),),), # Having another 'Direct' ChannelRule makes this an or statement.
            ChannelRule('Paid Search', (one_of(self.medium_utm, 'cpc'),),),
            ChannelRule('Email', (one_of(self.source_utm, 'mail.google.com'),),),
            ChannelRule('Newsletter', (contains(self.source_utm, 'newsletter'),),),
            ChannelRule(
                'Organic Search',
                (
                    one_of(self.medium_utm, 'organic'),
                    one_of(self.source_utm, 'google', 'baidu', 'ecosia.org', 'yahoo', 'bing'),
                ),
            ),
            ChannelRule(
                'Organic Social',
                (
                    one_of(
                        self.source_utm,
                        "reddit",
                        "facebook",
                        "l.instagram.com",
                        "l.messenger",
                        'linkedin.com',
                        'pinterest.com',
                        't.co'
                    ),
                ),
            ),
            ChannelRule('Organic Video', (contains(self.source_utm, 'youtube'),),),
            ChannelRule('Data Share Promo', (one_of(self.campaign_utm, 'data share promo'),),),
            ChannelRule('Affiliate', (one_of(self.medium_utm, 'affiliate'),),),
            ChannelRule('Display Ads', (one_of(self.source_utm, 'googlesyndication', 'doubleclick'),),),
            ChannelRule('Display Ads', (contains(self.source_utm, '2mdn.net'),),),
            ChannelRule(
                'Internal',
                (
                    one_of(
                        self.source_utm,
                        'corp.google.com',
                        'docs.google.com',
                        'sites.google.com',
                        'keep.google.com',
                        'groups.google.com',
                        'analytics.google.com',
                        'support.google.com',
                        'moma.corp.google.com',

                    ),
                ),
            ),
            ChannelRule('Qwiklabs', (contains(self.source_utm, 'qwiklabs'),),),
            ChannelRule('Redacted', (contains(self.source_utm, 'data deleted'),),),
            ChannelRule('Redacted', (contains(self.medium_utm, 'data deleted'),),),
            ChannelRule('Redacted', (contains(self.campaign_utm, 'data deleted'),),),
            ChannelRule(
                'Referral',
                (
                    contains(self.source_utm, '.com', '.net', '.org'),
                    one_of(self.medium_utm, 'referral'),
                ),
        ),
    )
