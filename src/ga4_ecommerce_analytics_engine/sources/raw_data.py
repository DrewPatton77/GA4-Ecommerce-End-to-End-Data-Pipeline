'''
Container for the three raw extracts the pipeline starts from.
'''

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

@dataclass
class RawData:
    '''
    Raw extracts, passed around together instead of living as class attributes.
    '''

    events: pl.DataFrame
    items: pl.DataFrame
    dimensions: pl.DataFrame

    