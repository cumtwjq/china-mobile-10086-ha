"""China Mobile account sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN


SENSORS: tuple[tuple[str, str, str], ...] = (
    ("balance", "话费余额", "元"),
    ("total_remaining", "总剩余流量", "GB"),
    ("total_used", "总已用流量", "MB"),
    ("total_quota", "流量总量", "GB"),
    ("general_remaining", "国内通用剩余流量", "GB"),
    ("general_used", "国内通用已用流量", "MB"),
    ("general_quota", "国内通用流量总量", "GB"),
    ("directional_remaining", "定向剩余流量", "GB"),
    ("directional_used", "定向已用流量", "MB"),
    ("directional_quota", "定向流量总量", "GB"),
    ("other_remaining", "国内其他剩余流量", "GB"),
    ("other_used", "国内其他已用流量", "MB"),
    ("other_quota", "国内其他流量总量", "GB"),
    ("voice_remaining", "剩余通话", "分钟"),
    ("voice_used", "已用通话", "分钟"),
    ("voice_quota", "通话总量", "分钟"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [StatusSensor(coordinator, entry)]
        + [AccountSensor(coordinator, entry, key, name, unit) for key, name, unit in SENSORS]
    )


class BaseSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="中国移动",
            name=(
                f"中国移动10086 · 尾号{entry.data['phone'][-4:]}"
                if entry.data.get("phone") else "中国移动10086"
            ),
        )


class StatusSensor(BaseSensor):
    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_browser_status"
        self._attr_name = "浏览器登录状态"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("status", "waiting_for_app")

    @property
    def extra_state_attributes(self) -> dict:
        return {"last_checked": self.coordinator.data.get("updated_at")}


class AccountSensor(BaseSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: DataUpdateCoordinator, entry: ConfigEntry, key: str, name: str, unit: str
    ) -> None:
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return (
            self.coordinator.last_update_success
            and data.get("status") == "ok"
            and self.key in data.get("sensors", {})
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("sensors", {}).get(self.key)
