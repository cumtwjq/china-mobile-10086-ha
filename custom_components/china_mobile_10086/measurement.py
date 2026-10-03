"""Interpret the units used by the China Mobile allowance responses."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def amount(value: Any) -> float | None:
    """Return a finite numeric amount; N represents an unlimited quota."""
    if value in (None, "", "N", "--"):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return float(number) if number.is_finite() else None


def flow_mb(value: Any, unit: Any) -> float | None:
    """The observed unit codes are 1=MB, 2=GB, and 6=KB."""
    number = amount(value)
    if number is None:
        return None
    factor = {"1": 1, "2": 1024, "6": 1 / 1024}.get(str(unit))
    return round(number * factor, 2) if factor is not None else None


def flow_gb(value: Any, unit: Any) -> float | None:
    mb = flow_mb(value, unit)
    return round(mb / 1024, 2) if mb is not None else None


def summary(flow: dict[str, Any], card_id: str) -> dict[str, Any] | None:
    rows = flow.get("flowSumInfo")
    if not isinstance(rows, list):
        return None
    return next((row for row in rows if isinstance(row, dict) and row.get("cardId") == card_id), None)


def voice_minutes(voice: dict[str, Any]) -> float | None:
    return voice_value(voice, "flowRemain")


def voice_value(voice: dict[str, Any], field: str) -> float | None:
    rows = voice.get("flowSumList")
    if not isinstance(rows, list):
        return None
    row = next((row for row in rows if isinstance(row, dict) and row.get("cardId") == "04"), None)
    if not row or str(row.get("unit")) != "4":
        return None
    return amount(row.get(field))
