"""Balance and allowance sensors for China Mobile 10086."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .measurement import amount, flow_gb, flow_mb, summary, voice_value


def _packages(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("flow", {}).get("packageInfo")
    return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def _package_key(item: dict[str, Any], index: int) -> str:
    identity = [item.get("cardId"), item.get("planId"), item.get("resourcesCode"), index]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:16]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        AccountSensor(coordinator, entry, "balance", "话费余额", "元"),
        AccountSensor(coordinator, entry, "total_remaining", "总剩余流量", "GB"),
        AccountSensor(coordinator, entry, "total_used", "总已用流量", "MB"),
        AccountSensor(coordinator, entry, "total_quota", "流量总量", "GB"),
        AccountSensor(coordinator, entry, "general_remaining", "国内通用剩余流量", "GB"),
        AccountSensor(coordinator, entry, "general_quota", "国内通用流量总量", "GB"),
        AccountSensor(coordinator, entry, "other_remaining", "国内其他剩余流量", "GB"),
        AccountSensor(coordinator, entry, "other_quota", "国内其他流量总量", "GB"),
        AccountSensor(coordinator, entry, "general_used", "国内通用已用流量", "MB"),
        AccountSensor(coordinator, entry, "other_used", "国内其他已用流量", "MB"),
        AccountSensor(coordinator, entry, "voice_remaining", "剩余通话", "分钟"),
        AccountSensor(coordinator, entry, "voice_used", "已用通话", "分钟"),
        AccountSensor(coordinator, entry, "voice_quota", "通话总量", "分钟"),
    ]
    async_add_entities(entities)

    known: set[str] = set()

    def add_packages() -> None:
        new = []
        for index, item in enumerate(_packages(coordinator.data)):
            key = _package_key(item, index)
            if key not in known:
                known.add(key)
                new.append(PackageSensor(coordinator, entry, key, item))
        if new:
            async_add_entities(new)

    add_packages()
    entry.async_on_unload(coordinator.async_add_listener(add_packages))


class BaseMobileSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="中国移动",
            name="中国移动10086",
        )
        self.entry_id = entry.entry_id


class AccountSensor(BaseMobileSensor):
    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, key: str, name: str, unit: str
    ) -> None:
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if self.key == "balance":
            return amount(data["balance"].get("curFee"))
        if self.key.startswith("voice_"):
            field = {
                "voice_remaining": "flowRemain",
                "voice_used": "flowUse",
                "voice_quota": "flowSum",
            }[self.key]
            return voice_value(data["voice"], field)
        card = {
            "total_remaining": "00",
            "total_used": "00",
            "total_quota": "00",
            "general_remaining": "01",
            "general_quota": "01",
            "other_remaining": "02",
            "other_quota": "02",
            "general_used": "01",
            "other_used": "02",
        }[self.key]
        row = summary(data["flow"], card)
        if row is None:
            return None
        field = (
            "flowUse"
            if self.key.endswith("used")
            else "flowSum" if self.key.endswith("quota") else "flowRemain"
        )
        convert = flow_mb if self.key.endswith("used") else flow_gb
        return convert(row.get(field), row.get("unit"))


class PackageSensor(BaseMobileSensor):
    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, key: str, item: dict[str, Any]
    ) -> None:
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_package_{key}"
        label = item.get("planName") or item.get("cardName") or "套餐"
        self._attr_name = f"{label}剩余流量"
        self._attr_native_unit_of_measurement = "MB"

    def _item(self) -> dict[str, Any] | None:
        return next(
            (
                item
                for index, item in enumerate(_packages(self.coordinator.data))
                if _package_key(item, index) == self.key
            ),
            None,
        )

    @property
    def native_value(self) -> float | None:
        item = self._item()
        return flow_mb(item.get("remainRes"), item.get("unit")) if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self._item()
        if not item:
            return {}
        return {
            "total_mb": flow_mb(item.get("totalRes"), item.get("unit")),
            "used_mb": flow_mb(item.get("usedRes"), item.get("unit")),
            "expires_at": item.get("expTime") or None,
        }
