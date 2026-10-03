"""China Mobile 10086 read-only Home Assistant integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientError, ClientResponseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MobileAPIError, MobileAuthError, MobileServiceUnavailableError, fetch_account
from .const import CONF_CAPTURE, DOMAIN, POLL_MINUTES


PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)

    async def update() -> dict:
        try:
            return await fetch_account(session, entry.data[CONF_CAPTURE])
        except MobileAuthError as err:
            raise ConfigEntryAuthFailed("中国移动登录已失效，请更新抓取请求") from err
        except MobileServiceUnavailableError as err:
            raise UpdateFailed("中国移动接口返回升级公告，请检查登录会话或稍后重试") from err
        except ClientResponseError as err:
            raise UpdateFailed(f"中国移动接口返回 HTTP {err.status}") from err
        except (ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed("无法连接中国移动接口") from err
        except MobileAPIError as err:
            raise UpdateFailed("中国移动返回的数据无效") from err

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=DOMAIN,
        update_method=update,
        update_interval=timedelta(minutes=POLL_MINUTES),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
