from __future__ import annotations

from typing import Sequence

import polars as pl

from ga4_ecommerce_analytics_engine.enrichment.channel_rules import (
DataChannelRule, 
Criterion,
Clause,
ChannelRule
    )

class DataChannelClassifier:
    '''
    Adds a channel column to a table with source_utm, medium_utm, and campaign_utm
    '''

    def __init__(self):
        channel_rules = DataChannelRule()
        self.source_utm  : str = 'source_utm'
        self.medium_utm  : str = 'medium_utm'
        self.campaign_utm: str = 'campaign_utm'
        self.utm: list[str] = [self.source_utm, self.medium_utm, self.campaign_utm]

        source_norm: Sequence[tuple[str, str]] = channel_rules.source_normalization
        self.source_norm = tuple(source_norm)

        rules: Sequence[DataChannelRule] = channel_rules.channel_rules()
        self.rules = tuple(rules)

# --- Normalize -----------------------------------------------

    def normalize_sources(self, sessions: pl.DataFrame) -> pl.DataFrame:

        sessions = sessions.with_columns(
                    [
        pl.col(column)
                        .cast(pl.Utf8)
                        .fill_null('')
                        .str.to_lowercase()
                        .str.strip_chars()
                        .alias(column)
        for column in self.utm
                    ]
                )

        for fragment, norm_source in self.source_norm:
            sessions = sessions.with_columns(
            pl.when(pl.col(self.source_utm).str.contains(fragment, literal=True))
                            .then(pl.lit(norm_source))
                            .otherwise(pl.col(self.source_utm))
                            .alias(self.source_utm)
                        )

        return sessions

    # --- Classifying all channels -------------------------------

    def classify(self, sessions: pl.DataFrame) -> pl.DataFrame:
        '''
        Normalize the UTM columns, then add the channel column.
        '''
        normalized = self.normalize_sources(sessions)
        return normalized.with_columns(self._channel_expression().alias('channel'))

    # --- Grouping all channels -----------------------------------
    def grouping(self, sessions_channel: pl.DataFrame) -> pl.DataFrame:
        return sessions_channel.with_columns(
            pl.when(pl.col('channel').str.contains('Email|Newsletter')).then(pl.lit('Email'))
            .when(pl.col('channel').str.contains('Internal|Redacted|Qwiklabs')).then(pl.lit('Non-Marketing'))
            .when(pl.col('channel').str.contains('Organic Social|Organic Video|Display Ads|Affiliate|Data Share Promo')).then(pl.lit('Other Marketing'))
            .when(pl.col('channel').eq('Organic Search')).then(pl.lit('Organic Search'))
            .when(pl.col('channel').eq('Direct')).then(pl.lit('Direct'))
            .when(pl.col('channel').eq('Referral')).then(pl.lit('Referral'))
            .when(pl.col('channel').eq('Paid Search')).then(pl.lit('Paid Search'))
            .when(pl.col('channel').eq('Unclassified')).then(pl.lit('Unclassified'))
            .alias('channel_group')
        )

    # --- Matching --------------------------------------------------

    def _channel_expression(self) -> pl.Expr:
        '''
        First matching rule wins. Otherwise, the 'Unclassified' label is used.
        '''
        chain = None
        for rule in self.rules:
            condition = self._rule_expression(rule)
            label = pl.lit(rule.label)
            chain = pl.when(condition).then(label) if chain is None else chain.when(condition).then(label)
        if chain is None:
            return pl.lit('Unclassifed')
        return chain.otherwise(pl.lit('Unclassified'))

    def _rule_expression(self, rule: ChannelRule) -> pl.Expr:
        return pl.any_horizontal(*[self._clause_expression(clause) for clause in rule.clauses])

    def _clause_expression(self, clause: Clause) -> pl.Expr:
        if isinstance(clause, Criterion):
            return self._criterion_expression(clause)
        return pl.all_horizontal(*[self._criterion_expression(c) for c in clause])

    @staticmethod
    def _criterion_expression(criterion: Criterion) -> pl.Expr:
        column = pl.col(criterion.source) # This should either be kept here or editable in the schema.
        if criterion.operator == "equals":
            return column == criterion.values[0]
        if criterion.operator == "in":
            return column.is_in(list(criterion.values))
        if criterion.operator == "contains":
            return pl.any_horizontal(
                *[column.str.contains(fragment, literal=True) for fragment in criterion.values]
                )
        return column.str.contains(criterion.values[0]) # regex
