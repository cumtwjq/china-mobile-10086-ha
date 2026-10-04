"""Read account values produced by the HAOS browser app."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .auth_bridge import async_queue_forget
from .const import CONF_ACCOUNT_ID, DOMAIN, RESULT_DIR


PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


def _read_result(account_id: str) -> dict[str, Any]:
    try:
        if re.fullmatch(r"legacy|[0-9a-f]{16}", account_id) is None:
            raise ValueError("invalid account id")
        payload = json.loads(
            (Path(RESULT_DIR) / f"{account_id}.json").read_text(encoding="utf-8")
        )
        if payload.get("version") != 2 or not isinstance(payload.get("sensors"), dict):
            raise ValueError("unsupported browser result")
        stamp = datetime.fromisoformat(payload["updated_at"])
        if stamp.tzinfo is None or datetime.now(timezone.utc) - stamp > timedelta(minutes=70):
            return {"status": "stale", "sensors": {}}
        return payload
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "waiting_for_app", "sensors": {}}


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Keep the existing browser profile and entity IDs for the first account."""
    if entry.version < 3:
        data = dict(entry.data) if entry.version == 2 else {}
        data[CONF_ACCOUNT_ID] = "legacy"
        phone = data.get("phone")
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=3,
            unique_id=phone if phone else entry.unique_id,
            title=f"中国移动10086 · 尾号{phone[-4:]}" if phone else entry.title,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    account_id = entry.data.get(CONF_ACCOUNT_ID, "legacy")
    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=DOMAIN,
        update_method=lambda: hass.async_add_executor_job(_read_result, account_id),
        update_interval=timedelta(minutes=5),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    reauth_started = False

    def prompt_reauth() -> None:
        nonlocal reauth_started
        if coordinator.data.get("status") == "login_required" and not reauth_started:
            for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
                context = flow.get("context") or {}
                if context.get("entry_id") == entry.entry_id and str(
                    flow.get("step_id", "")
                ).startswith("reauth"):
                    reauth_started = True
                    return
            try:
                entry.async_start_reauth(hass)
                reauth_started = True
            except Exception:
                _LOGGER.exception("Could not start China Mobile reauthentication")
        elif coordinator.data.get("status") == "ok":
            reauth_started = False

    entry.async_on_unload(coordinator.async_add_listener(prompt_reauth))
    prompt_reauth()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Discard this account's browser login when its integration is removed."""
    await async_queue_forget(hass, entry.data.get(CONF_ACCOUNT_ID, "legacy"))
