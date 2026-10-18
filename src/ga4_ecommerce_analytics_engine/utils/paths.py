
from __future__ import annotations

from typing import Iterable

PATH_SEPARATOR = " > "

def format_path(values: Iterable, separator: str = PATH_SEPARATOR) -> str:
    return separator.join(str(value) for value in values)