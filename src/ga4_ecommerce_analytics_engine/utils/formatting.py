
from __future__ import annotations

def format_duration(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f}m"
    if hours < 48:
        return f"{hours:.0f}h"
    return f"{hours / 24:.0f}d"

def format_dollars(value: float) -> str:
    return f"${int(round(value))}"