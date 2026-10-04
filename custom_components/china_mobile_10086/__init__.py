"""Read account values produced by the HAOS browser app."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, RESULT_PATH


PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


def _read_result() -> dict[str, Any]:
    try:
        payload = json.loads(Path(RESULT_PATH).read_text(encoding="utf-8"))
        if payload.get("version") != 2 or not isinstance(payload.get("sensors"), dict):
            raise ValueError("unsupported browser result")
        stamp = datetime.fromisoformat(payload["updated_at"])
        if stamp.tzinfo is None or datetime.now(timezone.utc) - stamp > timedelta(minutes=70):
            return {"status": "stale", "sensors": {}}
        return payload
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "waiting_for_app", "sensors": {}}


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Discard short-lived captured requests from the previous version."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(entry, data={}, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=DOMAIN,
        update_method=lambda: hass.async_add_executor_job(_read_result),
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
