'''
The warehouse model: which tables exist, their primary keys and foreign keys.

Column names come from DataSchema, so renaming a key there renames it here too.
The loader uses this to create tables, load them in the right order and add the constraints.
'''

from __future__ import annotations

from dataclasses import dataclass

from ga4_ecommerce_analytics_engine import pipeline as t
from ga4_ecommerce_analytics_engine.schema import DataSchema


@dataclass(frozen=True)
class ForeignKey:
    column: str
    ref_table: str
    ref_column: str


@dataclass(frozen=True)
class TableSpec:
    name: str
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()

    @property
    def parents(self) -> set[str]:
        return {fk.ref_table for fk in self.foreign_keys}


def table_specs(schema: DataSchema | None = None) -> dict[str, TableSpec]:
    s = schema or DataSchema()

    geo = ForeignKey(s.geo_id, t.DIM_GEO, s.geo_id)
    device = ForeignKey(s.device_id, t.DIM_DEVICE, s.device_id)
    source = ForeignKey(s.traffic_source_id, t.DIM_TRAFFIC_SOURCE, s.traffic_source_id)
    date = ForeignKey(s.date_id, t.DIM_DATE, s.date_id)
    item = ForeignKey(s.item_key, t.DIM_ITEM, s.item_key)
    product = ForeignKey(s.product_key, t.DIM_PRODUCT, s.product_key)

    specs = [
        # Dimensions
        TableSpec(t.DIM_DATE, (s.date_id,)),
        TableSpec(t.DIM_GEO, (s.geo_id,)),
        TableSpec(t.DIM_DEVICE, (s.device_id,)),
        TableSpec(t.DIM_TRAFFIC_SOURCE, (s.traffic_source_id,)),
        TableSpec(t.DIM_PRODUCT, (s.product_key,)),
        TableSpec(t.DIM_ITEM, (s.item_key,), (product,)),
        TableSpec(t.DIM_TRANSACTION, (s.transaction_id,)),
        # Facts
        TableSpec(t.FACT_EVENT, (s.event_id,), (date, geo, device, source)),
        TableSpec(t.FACT_ITEM_FUNNEL, (s.item_funnel_id,), (date, geo, device, source, product)),
        TableSpec(t.FACT_SESSION, (s.session_id,), (date, geo, device, source)),
        TableSpec(t.FACT_USER, (s.user_id,), (geo, device, source)),
        TableSpec(t.FACT_JOURNEY, (s.journey_id,), (geo, device, source)),
        TableSpec(t.FACT_CONVERTING_JOURNEY, (s.converting_journey_id,), (geo, device, source)),
        TableSpec(t.FACT_BASKET, (s.basket_id,)),
        # Bridges. The event bridge has no primary key: an item can appear twice in one event.
        # The transaction bridge has no item foreign key: GA4 can record a purchased item as '(not set)'.
        TableSpec(
            t.BRIDGE_EVENT_ITEM,
            (),
            (ForeignKey(s.event_id, t.FACT_EVENT, s.event_id), item),
        ),
        TableSpec(
            t.BRIDGE_TRANSACTION_ITEM,
            (s.transaction_id, s.item_key),
            (ForeignKey(s.transaction_id, t.DIM_TRANSACTION, s.transaction_id), item),
        ),
    ]
    return {spec.name: spec for spec in specs}


def load_order(specs: dict[str, TableSpec]) -> list[str]:
    '''
    Table names with every table after the tables it points at (parents first)
    '''
    ordered: list[str] = []
    remaining = dict(specs)
    while remaining:
        ready = [name for name, spec in remaining.items() if (spec.parents - {name}) <= set(ordered)]
        if not ready:
            raise ValueError(f'Foreign keys form a cycle among: {sorted(remaining)}')
        for name in ready:
            ordered.append(name)
            del remaining[name]
    return ordered
