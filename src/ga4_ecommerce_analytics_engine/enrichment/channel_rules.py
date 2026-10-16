'''
Set-up channel rules for marketing source / medium / campaign


----> To change channel rules, edit this file. <----


------
Rules are checked in priority order, such that the first match is priority.

A rule matches when ANY of its clauses match. 

A clause is either a single Criterion, or a tuple of Criterion objects that must ALL hold.

Criteria compare against the lower-cased, trimmed source / medium / campaign:
    equals, in, contains, regex.

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
    - Channel Rule:
        - label = 'Direct'
            - Clause = (
                - Criterion = (source == '(direct)' & medium == '(none)'),
                - Criterion = (source == 'googlemerchandisestore')
               )
        - label = 'Email'
            - Clause = (
                - Criterion = (source == 'google.mail.com')
              )
        ...
        - (edit, remove or add)
'''

from __future__ import annotations

from dataclasses import dataclass, field

# --- Internals ----> DO NOT EDIT BELOW THIS LINE. SEE BOTTOM OF PAGE <-------

SOURCES = ['source_utm', 'medium_utm', 'campaign_utm'] # Should I make these labels configurable in the schema?
OPERATORS = ("equals", 'in', 'contains', 'regex') # 
UNCLASSIFIED_LABEL = 'Unclassified' # When no rules match, the rule returns an 'Unclassified' rule.

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

def eq(field: str, value: str) -> Criterion:
    return Criterion(field, 'equals', (value,))

def is_in(field: str, *values: str) -> Criterion:
    return Criterion(field, "in", tuple(values))

def contains(field: str, *fragments: str) -> Criterion:
    return Criterion(field, 'contains', tuple(fragments))

def regex(field: str, pattern: str) -> Criterion:
    return Criterion(field, 'regex', (pattern,))


# ---- Main -----> EDIT HERE! DO NOT EDIT ABOVE THIS LINE <-------

class DataChannelRule:
    def __init__(self):

        # Required columns
        self.source_utm = 'source_utm'
        self.medium_utm = 'medium_utm'
        self.campaign_utm = 'campaign_utm'

        # Source normalization
        self.source_normalization: tuple[tuple[str, str], ...] = (
            ('googlesyndication', 'googlesyndication'),
            ('bing', 'bing'),
            ('yahoo', 'yahoo'),
            ('facebook', 'facebook'),
            ('reddit', 'reddit'),
            ('googlemerchandisestore.com', 'googlemerchandisestore'),
            ('doubleclick.net', 'double.click'),
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
                    eq(self.source_utm, '(direct)'), 
                    eq(self.medium_utm, '(none)'),
                ),
            ),
            ChannelRule('Direct', (eq(self.source_utm, 'googlemerchandisestore'),),),
            ChannelRule('Paid Search', (eq(self.medium_utm, 'cpc'),),),
            ChannelRule('Email', (eq(self.source_utm, 'mail.google.com'),),),
            ChannelRule('Newsletter', (contains(self.source_utm, 'newsletter'),),),
            ChannelRule(
                'Organic Search',
                (
                    eq(self.medium_utm, 'organic'),
                    is_in(self.source_utm, 'google', 'baidu', 'ecosia.org', 'yahoo', 'bing'),
                ),
            ),
            ChannelRule(
                'Organic Social',
                (
                    is_in(
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
            ChannelRule(
                'Internal',
                (
                    is_in(
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
            ChannelRule(
                'Referral',
                (
                    regex(self.source_utm, r"\.com|\.net|\.org"),
                    eq(self.medium_utm, 'referral'),
                ),
            ),
        )
        
