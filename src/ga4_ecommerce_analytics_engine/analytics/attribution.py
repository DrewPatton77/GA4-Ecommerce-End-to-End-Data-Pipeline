'''
Marketing attribution: which channel should get credit for a conversion?

    result = AttributionAnalyzer().build(sessions, converting_journeys)
    result.facts     one row per session (touch) in a converting journey, per model: credit and revenue credit
    result.models    one row per model: key, name, description

Eight models are built. Every model gives each converting journey a total credit of exactly 1 (and so its
revenue is shared out exactly), so any model's totals add up to the same revenue:

    First-Click / Last-Click      all credit to the first / last session
    Last-Click Non-Direct         all credit to the last session that was not Direct (the last session if all were)
    Linear                        equal credit to every session
    Position-Based                40% first, 40% last, 20% shared by the middle (50/50 for two, 100% for one)
    Time-Decay                    weights halve every `half_life_hours` before the journey's last session
    Shapley Value                 equal credit to every DISTINCT channel in the journey
    Markov Chain                  credit follows each channel's removal effect (see removal_effects)

A channel with several sessions in one journey shares its credit between them, so credit summed by channel
matches the channel-level tables of the heuristic models exactly.

The Markov model is channel-level by nature (one removal effect per channel). To get credit per session, each
journey's credit is split between the distinct channels in it in proportion to their removal effects, so
Markov totals are NOT the same as 'removal effect x total revenue'. Use `removal_effects` for that.

The steps are separate methods so each can be tested on its own:

    touches            sessions -> one row per session, in order, with its position and hours before the last one
    converting_users   converting journeys -> user, journey id, revenue (the users that get credit)
    removal_effects    all touches -> each channel's share of the conversions that depend on it (Markov)
    models_table       the model dimension
'''

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import polars as pl

from ga4_ecommerce_analytics_engine.facts.common import add_id, to_date_id
from ga4_ecommerce_analytics_engine.schema import DataSchema

MICROS_PER_HOUR = 3_600_000_000

# Markov states besides the channels themselves.
START, CONVERSION, NULL = 'Start', 'Conversion', 'Null'

# (name, description), in key order: the first model gets key 0.
MODELS: tuple[tuple[str, str], ...] = (
    ('First-Click', 'All credit to the first session of the journey.'),
    ('Last-Click', 'All credit to the last session of the journey.'),
    ('Last-Click Non-Direct', 'All credit to the last session that was not Direct (the last session if all were Direct).'),
    ('Linear', 'Equal credit to every session.'),
    ('Position-Based', '40% to the first and 40% to the last session, 20% shared by the middle ones.'),
    ('Time-Decay', 'More credit to sessions closer to the end of the journey (7-day half-life).'),
    ('Shapley Value', 'Equal credit to every distinct channel in the journey.'),
    ('Markov Chain', "Credit split by each channel's removal effect: how many conversions are lost without it."),
)

# Working columns, dropped before the result is returned.
_INDEX, _COUNT, _HOURS, _CONVERTS, _MODEL = '_touch_index', '_touches', '_hours_before', '_converts', '_model'


class AttributionResult(NamedTuple):
    facts: pl.DataFrame
    models: pl.DataFrame


@dataclass(frozen=True)
class AttributionAnalyzer(DataSchema):
    half_life_hours: float = 168.0  # Time-Decay: a session this many hours before the last one counts half as much
    direct_channel: str = 'Direct'
    unknown_channel: str = 'Unclassified'  # label for a session with no channel, so it can be a Markov state

    # ---- Public ---------------------------------------------------------------

    def build(self, sessions: pl.DataFrame, converting: pl.DataFrame) -> AttributionResult:
        '''
        `sessions`: every session. `converting`: converting journeys, one row per user (the journey facts)
        '''
        touches = self.touches(sessions)
        users = self.converting_users(converting)

        weights = self.removal_effects(touches, users)
        credited = touches.join(users, on=self.user_id, how='inner')
        credited = credited.with_columns(self._credit_expressions(weights))

        models = self.models_table()
        ids = dict(zip(models[self.attribution_model], models[self.attribution_model_id]))
        names = list(ids)

        facts = (
            credited.select(
                self.user_id, self.session_id, self.converting_journey_id, self.date_id,
                pl.col(_INDEX).add(1).alias(self.touch_number),
                pl.col(_COUNT).alias(self.touchpoints),
                pl.col(self.conversion_value),
                *names,
            )
            .unpivot(
                index=[
                    self.user_id, self.session_id, self.converting_journey_id, self.date_id,
                    self.touch_number, self.touchpoints, self.conversion_value,
                ],
                on=names,
                variable_name=_MODEL,
                value_name=self.credit,
            )
            .filter(pl.col(self.credit) > 0)  # a model that gives a session nothing writes no row for it
            .with_columns(
                pl.col(_MODEL).replace_strict(ids, return_dtype=pl.Int64).alias(self.attribution_model_id),
                (pl.col(self.credit) * pl.col(self.conversion_value)).alias(self.revenue_credit),
            )
            .sort([self.attribution_model_id, self.converting_journey_id, self.touch_number])
        )
        facts = add_id(facts, self.attribution_id).select(
            self.attribution_id, self.attribution_model_id, self.converting_journey_id,
            self.user_id, self.session_id, self.date_id, self.touch_number, self.touchpoints,
            self.credit, self.revenue_credit,
        )
        return AttributionResult(facts, models)

    def models_table(self) -> pl.DataFrame:
        return pl.DataFrame(
            {
                self.attribution_model_id: list(range(len(MODELS))),
                self.attribution_model: [name for name, _ in MODELS],
                self.attribution_description: [description for _, description in MODELS],
            },
            schema={
                self.attribution_model_id: pl.Int64,
                self.attribution_model: pl.Utf8,
                self.attribution_description: pl.Utf8,
            },
        )

    # ---- 1. Touches -----------------------------------------------------------

    def touches(self, sessions: pl.DataFrame) -> pl.DataFrame:
        '''
        Every session as a touch: its place in the user's path and the hours before the user's last session
        '''
        self.check_required_columns(
            sessions,
            required_columns={
                self.user_id, self.session_id, self.session_start_timestamp, self.session_date, self.channel,
            },
        )
        start = pl.col(self.session_start_timestamp)
        return (
            sessions.select(
                self.user_id, self.session_id, self.session_start_timestamp, self.session_date, self.channel
            )
            .with_columns(pl.col(self.channel).fill_null(self.unknown_channel))
            .sort([self.user_id, self.session_start_timestamp, self.session_id], maintain_order=True)
            .with_columns(
                pl.int_range(pl.len(), dtype=pl.Int64).over(self.user_id).alias(_INDEX),
                pl.len().over(self.user_id).cast(pl.Int64).alias(_COUNT),
                (
                    (start.max().over(self.user_id) - start).dt.total_microseconds() / MICROS_PER_HOUR
                ).alias(_HOURS),
                to_date_id(self.session_date).alias(self.date_id),
            )
        )

    def converting_users(self, converting: pl.DataFrame) -> pl.DataFrame:
        '''
        The users that get credit: their journey id and total revenue (a missing value counts as 0)
        '''
        self.check_required_columns(
            converting, required_columns={self.user_id, self.converting_journey_id, self.conversion_value}
        )
        if converting[self.user_id].is_duplicated().any():
            raise ValueError('The converting journeys have more than one row per user; credit would be counted twice.')
        return converting.select(
            self.user_id,
            self.converting_journey_id,
            pl.col(self.conversion_value).cast(pl.Float64).fill_null(0.0),
        )

    # ---- 2. Credit per model --------------------------------------------------

    def _credit_expressions(self, weights: dict[str, float]) -> list[pl.Expr]:
        '''
        One expression per model: each touch's share of its journey's credit (the shares add up to 1)
        '''
        user, channel = pl.col(self.user_id), pl.col(self.channel)
        i, n = pl.col(_INDEX), pl.col(_COUNT)
        is_first, is_last = i == 0, i == n - 1

        # Index of the last session that was not Direct; null when every session was Direct, so fall back to the last.
        last_non_direct = pl.coalesce(
            pl.when(channel != self.direct_channel).then(i).otherwise(None).max().over(self.user_id), n - 1
        )

        position = (
            pl.when(n == 1).then(1.0)
            .when(n == 2).then(0.5)
            .when(is_first | is_last).then(0.4)
            .otherwise(0.2 / (n - 2))  # the middle sessions share 20% equally
        )

        decay = (pl.col(_HOURS) * (-np.log(2) / self.half_life_hours)).exp()

        # Credit per DISTINCT channel, split between that channel's sessions.
        sessions_in_channel = pl.len().over(self.user_id, self.channel).cast(pl.Float64)
        distinct_channels = channel.n_unique().over(self.user_id).cast(pl.Float64)
        shapley = 1.0 / (distinct_channels * sessions_in_channel)

        weight = channel.replace_strict(weights, default=0.0, return_dtype=pl.Float64) / sessions_in_channel
        weight_total = weight.sum().over(self.user_id)
        markov = pl.when(weight_total > 0).then(weight / weight_total).otherwise(shapley)  # no weights: equal split

        shares = {
            'First-Click': is_first.cast(pl.Float64),
            'Last-Click': is_last.cast(pl.Float64),
            'Last-Click Non-Direct': (i == last_non_direct).cast(pl.Float64),
            'Linear': 1.0 / n,
            'Position-Based': position,
            'Time-Decay': decay / decay.sum().over(self.user_id),
            'Shapley Value': shapley,
            'Markov Chain': markov,
        }
        return [expression.alias(name) for name, expression in shares.items()]

    # ---- 3. Markov removal effects --------------------------------------------

    def removal_effects(self, touches: pl.DataFrame, converting: pl.DataFrame) -> dict[str, float]:
        '''
        Each channel's share (adds up to 1) of the conversions that would be lost if the channel were removed.

        Uses every user's path (converting or not): Start -> channel -> ... -> Conversion or Null. The conversion
        probability from Start is solved exactly, then again with each channel's incoming transitions removed.
        `converting` is the frame from `converting_users`
        '''
        flagged = touches.join(
            converting.select(self.user_id).with_columns(pl.lit(True).alias(_CONVERTS)), on=self.user_id, how='left'
        ).with_columns(pl.col(_CONVERTS).fill_null(False))

        channel = pl.col(self.channel)
        outcome = pl.when(pl.col(_CONVERTS)).then(pl.lit(CONVERSION)).otherwise(pl.lit(NULL))
        steps = pl.concat(
            [
                flagged.filter(pl.col(_INDEX) == 0).select(pl.lit(START).alias('source'), channel.alias('target')),
                flagged.select(
                    channel.alias('source'),
                    # the next session's channel, or the journey's outcome after the last one
                    pl.coalesce(channel.shift(-1).over(self.user_id), outcome).alias('target'),
                ),
            ]
        )

        channels = sorted(touches[self.channel].unique().to_list())
        transient = [START, *channels]  # Start is first, so row 0 is where every journey begins
        states = [*transient, CONVERSION, NULL]
        position = {state: k for k, state in enumerate(states)}

        counts = np.zeros((len(transient), len(states)))
        for source, target, count in steps.group_by(['source', 'target']).len().iter_rows():
            counts[position[source], position[target]] += count
        totals = counts.sum(axis=1, keepdims=True)
        probabilities = np.divide(counts, totals, out=np.zeros_like(counts), where=totals > 0)

        k = len(transient)
        Q, R = probabilities[:, :k], probabilities[:, k:]  # transient -> transient, transient -> (Conversion, Null)

        def conversion_probability(q: np.ndarray) -> float:
            # Absorption probabilities B = (I - Q)^-1 R; column 0 is Conversion and row 0 is Start.
            return float(np.linalg.solve(np.eye(k) - q, R)[0, 0])

        base = conversion_probability(Q)
        if base <= 0 or not channels:
            return {name: 1 / len(channels) for name in channels}

        effects = []
        for column in range(1, k):
            without = Q.copy()
            without[:, column] = 0.0  # nothing can move into this channel any more
            effects.append(max(0.0, 1.0 - conversion_probability(without) / base))

        total = sum(effects)
        if total <= 0:
            return {name: 1 / len(channels) for name in channels}
        return {name: effect / total for name, effect in zip(channels, effects)}
