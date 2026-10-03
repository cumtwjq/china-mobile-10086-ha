"""Phone and SMS-code login through the HAOS browser app."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .auth_bridge import async_auth_command
from .const import DOMAIN


CONF_PHONE = "phone"
CONF_CODE = "code"


def _phone_schema(default: str | None = None) -> vol.Schema:
    key = vol.Required(CONF_PHONE, default=default) if default else vol.Required(CONF_PHONE)
    return vol.Schema({key: selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEL)
    )})


def _code_schema() -> vol.Schema:
    return vol.Schema({vol.Required(CONF_CODE): selector.TextSelector()})


class LoginSteps:
    _phone: str

    async def _phone_step(
        self, step_id: str, user_input: dict[str, Any] | None = None, default: str | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            phone = str(user_input[CONF_PHONE]).strip()
            if len(phone) != 11 or not phone.startswith("1") or not phone.isdigit():
                errors["base"] = "invalid_phone"
            else:
                status = await async_auth_command(self.hass, "send_code", phone)
                if status == "sent":
                    self._phone = phone
                    return await self.async_step_code()
                errors["base"] = status if status in {
                    "app_not_running", "app_timeout", "manual_required", "send_failed", "login_failed"
                } else "login_failed"
        return self.async_show_form(
            step_id=step_id, data_schema=_phone_schema(default), errors=errors
        )

    async def async_step_code(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            code = str(user_input[CONF_CODE]).strip()
            if not code.isdigit() or not 4 <= len(code) <= 8:
                errors["base"] = "invalid_code"
            else:
                status = await async_auth_command(self.hass, "verify", code)
                if status == "success":
                    return await self._finish_login()
                errors["base"] = status if status in {
                    "app_not_running", "app_timeout", "invalid_code", "login_failed"
                } else "login_failed"
        return self.async_show_form(step_id="code", data_schema=_code_schema(), errors=errors)


class ChinaMobileConfigFlow(LoginSteps, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    _reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ChinaMobileOptionsFlow:
        return ChinaMobileOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._phone_step("user", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Restore the existing entry through the same phone/SMS flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        default = self._reauth_entry.data.get(CONF_PHONE) if self._reauth_entry else None
        return await self._phone_step("reauth_confirm", user_input, default)

    async def _finish_login(self) -> FlowResult:
        if self._reauth_entry is not None:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data_updates={CONF_PHONE: self._phone},
            )
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="中国移动10086", data={CONF_PHONE: self._phone})


class ChinaMobileOptionsFlow(LoginSteps, OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self._phone_step("init", user_input, self.config_entry.data.get(CONF_PHONE))

    async def _finish_login(self) -> FlowResult:
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_PHONE: self._phone},
        )
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_create_entry(data={})
