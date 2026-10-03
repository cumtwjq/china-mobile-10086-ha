"""Import a locally captured China Mobile session without displaying credentials."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MobileAPIError, MobileAuthError, MobileServiceUnavailableError, fetch_account, parse_capture
from .const import CONF_CAPTURE, CONF_REQUEST_JSON, DOMAIN


def _schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_REQUEST_JSON): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        }
    )


class ChinaMobileConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ChinaMobileOptionsFlow:
        return ChinaMobileOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                capture = parse_capture(user_input[CONF_REQUEST_JSON])
            except MobileAPIError:
                errors["base"] = "invalid_capture"
            else:
                try:
                    await fetch_account(async_get_clientsession(self.hass), capture)
                except MobileAuthError:
                    errors["base"] = "invalid_auth"
                except MobileServiceUnavailableError:
                    errors["base"] = "service_unavailable"
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(DOMAIN)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="中国移动10086", data={CONF_CAPTURE: capture})
        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)


class ChinaMobileOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                capture = parse_capture(user_input[CONF_REQUEST_JSON])
            except MobileAPIError:
                errors["base"] = "invalid_capture"
            else:
                try:
                    await fetch_account(async_get_clientsession(self.hass), capture)
                except MobileAuthError:
                    errors["base"] = "invalid_auth"
                except MobileServiceUnavailableError:
                    errors["base"] = "service_unavailable"
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_CAPTURE: capture},
                    )
                    await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    return self.async_create_entry(data={})
        return self.async_show_form(step_id="init", data_schema=_schema(), errors=errors)
