'''
    tables = Pipeline().run(raw)          # raw is a RawData(events, items, dimensions)
    tables["fact_session"]                # polars DataFrame

Stages, in order (each one is a module you can also use on its own):

    clean       cleaning.transactions      deduplicate purchases, composite session ids
    enrich      enrichment                 session UTM values, then marketing channel
    aggregate   aggregation                sessions, then journeys
    dimensions  dimensions                 date, geo, device, traffic source, item, transaction
    facts       facts                      event, item funnel, session, user, journey (with dimension keys attached)
    basket      analytics.basket           items bought together
'''

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import polars as pl

from ga4_ecommerce_analytics_engine.aggregation.journeys import JourneyBuilder
from ga4_ecommerce_analytics_engine.aggregation.sessions import SessionBuilder
from ga4_ecommerce_analytics_engine.analytics.basket import BasketAnalyzer
from ga4_ecommerce_analytics_engine.cleaning.transactions import DataCleaner
from ga4_ecommerce_analytics_engine.dimensions.date import DateDimension
from ga4_ecommerce_analytics_engine.dimensions.device import DeviceDimension
from ga4_ecommerce_analytics_engine.dimensions.geo import GeoDimension
from ga4_ecommerce_analytics_engine.dimensions.items import ItemDimension, TransactionDimension
from ga4_ecommerce_analytics_engine.dimensions.traffic_source import TrafficSourceDimension
from ga4_ecommerce_analytics_engine.enrichment.channels import DataChannelClassifier
from ga4_ecommerce_analytics_engine.enrichment.utm import DataUtm
from ga4_ecommerce_analytics_engine.facts.events import EventFacts, EventItemBridge
from ga4_ecommerce_analytics_engine.facts.item_funnel import ItemFunnelFacts
from ga4_ecommerce_analytics_engine.facts.journeys import JourneyFacts
from ga4_ecommerce_analytics_engine.facts.keys import attach_keys
from ga4_ecommerce_analytics_engine.facts.sessions import SessionFacts
from ga4_ecommerce_analytics_engine.facts.users import UserFacts
from ga4_ecommerce_analytics_engine.schema import DataSchema
from ga4_ecommerce_analytics_engine.sources.raw_data import RawData

logger = logging.getLogger(__name__)

Tables = dict[str, pl.DataFrame]

# Output table names, in one place so the writers and Power BI see the same names.
DIM_DATE = "dim_date"
DIM_GEO = "dim_geo"
DIM_DEVICE = "dim_device"
DIM_TRAFFIC_SOURCE = "dim_traffic_source"
DIM_ITEM = "dim_item"
DIM_TRANSACTION = "dim_transaction"
BRIDGE_TRANSACTION_ITEM = "bridge_transaction_item"
BRIDGE_EVENT_ITEM = "bridge_event_item"
FACT_EVENT = "fact_event"
FACT_ITEM_FUNNEL = "fact_item_funnel"
FACT_SESSION = "fact_session"
FACT_USER = "fact_user"
FACT_JOURNEY = "fact_journey"
FACT_CONVERTING_JOURNEY = "fact_converting_journey"
FACT_BASKET = "fact_basket"


@dataclass
class Pipeline:
    '''
    Holds the stage objects (settings only). Swap any of them to change behaviour, e.g.
    Pipeline(basket=BasketAnalyzer(min_support=0.01))
    '''

    schema: DataSchema = field(default_factory=DataSchema)
    cleaner: DataCleaner = field(default_factory=DataCleaner)
    utm_builder: DataUtm = field(default_factory=DataUtm)
    classifier: DataChannelClassifier = field(default_factory=DataChannelClassifier)
    session_builder: SessionBuilder = field(default_factory=SessionBuilder)
    journey_builder: JourneyBuilder = field(default_factory=JourneyBuilder)
    basket: BasketAnalyzer = field(default_factory=BasketAnalyzer)

    def run(self, raw: RawData) -> Tables:
        tables: Tables = {}

        clean = self._stage('clean', lambda: self.cleaner.clean_transactions(raw.events, raw.items))
        events, session_utm = self._stage('utm', lambda: tuple(self.utm_builder.enrich_events_with_utm(clean.events)))
        session_channels = self._stage('channels', lambda: self.classifier.grouping(self.classifier.classify(session_utm)))
        sessions = self._stage('sessions', lambda: self.session_builder.build(events, session_channels))
        journeys = self._stage('journeys', lambda: self.journey_builder.build(sessions))

        dims = self._stage('dimensions', lambda: self._dimensions(raw, events, clean.items, sessions, tables))
        self._stage('facts', lambda: self._facts(events, clean.items, sessions, journeys, dims, tables))
        tables[FACT_BASKET] = self._stage('basket', lambda: self.basket.build(clean.items))

        return tables

    # ---- Dimensions -----------------------------------------------------------

    def _dimensions(self, raw, events, items, sessions, tables: Tables) -> "_Mappings":

        geo, geo_users = GeoDimension().build_with_user_mapping(raw.dimensions)
        device, device_users = DeviceDimension().build_with_user_mapping(raw.dimensions)
        traffic = TrafficSourceDimension().build_with_mappings(sessions)
        transactions = TransactionDimension().build(events, items)

        tables[DIM_DATE] = DateDimension().build(events)
        tables[DIM_GEO] = geo
        tables[DIM_DEVICE] = device
        tables[DIM_TRAFFIC_SOURCE] = traffic.dimension
        tables[DIM_ITEM] = ItemDimension().build(items)
        tables[DIM_TRANSACTION] = transactions.transactions
        tables[BRIDGE_TRANSACTION_ITEM] = transactions.transaction_items
        return _Mappings(geo_users, device_users, traffic.session_mapping, traffic.user_mapping)

    # ---- Facts ----------------------------------------------------------------

    def _facts(self, events, items, sessions, journeys, m: "_Mappings", tables: Tables) -> None:
        schema = DataSchema
        user, session = schema.user_id, schema.session_id
        by_user = [(m.geo, user), (m.device, user)]  # every fact has a user, so every fact gets these
        by_user_and_source = [*by_user, (m.traffic_user, user)]
        by_session = [*by_user, (m.traffic_session, session)]

        event_facts = EventFacts()
        events = event_facts.add_event_ids(events)
        tables[BRIDGE_EVENT_ITEM] = EventItemBridge().build(events, items)
        tables[FACT_EVENT] = attach_keys(event_facts.build(events), by_session)

        tables[FACT_ITEM_FUNNEL] = attach_keys(ItemFunnelFacts().build(items), by_session)
        tables[FACT_SESSION] = attach_keys(SessionFacts().build(sessions), by_session)
        tables[FACT_USER] = attach_keys(UserFacts().build(sessions), by_user_and_source)

        journey_facts = JourneyFacts().build(journeys.journeys, journeys.converting)
        tables[FACT_JOURNEY] = attach_keys(journey_facts.journeys, by_user_and_source)
        tables[FACT_CONVERTING_JOURNEY] = attach_keys(journey_facts.converting, by_user_and_source)

    # ---- Logging --------------------------------------------------------------

    @staticmethod
    def _stage(name: str, work: Callable):
        started = time.perf_counter()
        result = work()
        logger.info("%-10s done in %.1fs", name, time.perf_counter() - started)
        return result


@dataclass(frozen=True)
class _Mappings:
    geo: pl.DataFrame
    device: pl.DataFrame
    traffic_session: pl.DataFrame
    traffic_user: pl.DataFrame
