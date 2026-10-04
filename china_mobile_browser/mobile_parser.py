"""Extract read-only account values from China Mobile browser responses."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from Crypto.Cipher import AES


KEY = b"1234123412ABCDEF"
IV = b"ABCDEF1234123412"


def decode_response(body: str) -> dict[str, Any] | None:
    """Decode the JSON or AES-CBC JSON returned by wx.10086.cn."""
    try:
        if len(body) >= 32 and len(body) % 32 == 0 and all(
            char in "0123456789abcdefABCDEF" for char in body
        ):
            raw = AES.new(KEY, AES.MODE_CBC, IV).decrypt(bytes.fromhex(body))
            pad = raw[-1]
            if pad < 1 or pad > 16 or raw[-pad:] != bytes([pad]) * pad:
                return None
            body = raw[:-pad].decode("utf-8")
        decoded = json.loads(body)
    except (ValueError, UnicodeError, KeyError):
        return None
    return decoded if isinstance(decoded, dict) else None


def number(value: Any) -> float | None:
    if value in (None, "", "N", "--"):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return float(result) if result.is_finite() else None


def balance_from_page_text(page_text: str) -> float | None:
    """Read the amount next to the visible 话费余额 label, if present."""
    for pattern in (
        r"话费余额(?:\s*[（(]元[）)])?\s*(\d+\.\d{2})(?:\s*元)?",
        r"(\d+\.\d{2})(?:\s*元)?\s*话费余额",
    ):
        match = re.search(pattern, page_text)
        if match:
            return number(match.group(1))
    return None


def balance_for_display(api_balance: float | None, page_text: str) -> float | None:
    """Prefer the account holder's visible balance to a different API amount."""
    visible_balance = balance_from_page_text(page_text)
    return visible_balance if visible_balance is not None else api_balance


def flow_mb(item: dict[str, Any], field: str) -> float | None:
    value = number(item.get(field))
    if value is None:
        return None
    unit = str(item.get("unit", ""))
    if unit == "04":
        value *= 1024
    elif unit != "03":
        return None
    return round(value, 2)


def value_at(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extract_sensors(responses: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Return only values actually present in successful account responses."""
    result: dict[str, float] = {}
    fee = responses.get("fareBalance") or responses.get("accountFeeBalanceQuery") or {}
    balance = number(value_at(fee, "data", "realFeeQryRsp", "curFeeTotal"))
    if balance is None:
        balance = number(value_at(fee, "data", "curFeeTotal"))
    if balance is not None:
        result["balance"] = balance

    margin = responses.get("getNewMarginInfo") or {}
    data = value_at(margin, "data", "resultData")
    if not isinstance(data, dict):
        return result

    flow = data.get("planRemianFlowInfo") or {}
    for api_key, sensor_prefix in (
        ("planRemian", "general"),
        ("directionalFlowInfo", "directional"),
        ("otherRemian", "other"),
        ("totalInfo", "total"),
    ):
        item = flow.get(api_key) or {}
        if not isinstance(item, dict):
            continue
        for api_field, suffix in (
            ("remainNum", "remaining"),
            ("usedNum", "used"),
            ("sumNum", "quota"),
        ):
            value = flow_mb(item, api_field)
            if value is not None:
                result[f"{sensor_prefix}_{suffix}"] = (
                    value if suffix == "used" else round(value / 1024, 3)
                )

    voice = data.get("planRemianVoiceInfo") or {}
    voice_total = voice.get("totalInfo") or {}
    for api_field, suffix in (
        ("remainNum", "remaining"),
        ("usedNum", "used"),
        ("sumNum", "quota"),
    ):
        value = number(voice_total.get(api_field))
        if value is not None:
            result[f"voice_{suffix}"] = value
    return result
