from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory, UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH

from .const import DOMAIN, SIGNAL_MEASUREMENT


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        XiaomiScaleWeightSensor(runtime, user["NAME"]) for user in runtime.users
    ]
    entities.append(XiaomiScalePendingSensor(runtime))
    entities.append(XiaomiScaleDiagnosticSensor(runtime))
    entities.append(XiaomiScaleHistorySensor(runtime))
    async_add_entities(entities)


class XiaomiScaleBaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self._attr_device_info = {
            "identifiers": {(DOMAIN, runtime.entry.entry_id)},
            "connections": {(CONNECTION_BLUETOOTH, runtime.mac)},
            "name": runtime.entry.data[CONF_NAME],
            "manufacturer": "Xiaomi",
            "model": "Mi Scale BLE",
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_MEASUREMENT,
                self._handle_measurement,
            )
        )

    @callback
    def _handle_measurement(self, entry_id: str) -> None:
        if entry_id == self.runtime.entry.entry_id:
            self.async_write_ha_state()


class XiaomiScaleWeightSensor(XiaomiScaleBaseSensor):
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime, user_name: str) -> None:
        super().__init__(runtime)
        self.user_name = user_name
        self._attr_name = f"{user_name} weight"
        self._attr_unique_id = f"{runtime.entry.entry_id}_{user_name.lower()}_weight"

    @property
    def native_value(self) -> float | None:
        data = self.runtime.latest_by_user.get(self.user_name)
        if data is None:
            return None
        weight = float(data["weight"])
        if data["unit"] == "lbs":
            return round(weight * 0.4536, 2)
        if data["unit"] == "jin":
            return round(weight * 0.5, 2)
        return weight

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.latest_by_user.get(self.user_name, {})


class XiaomiScalePendingSensor(XiaomiScaleBaseSensor):
    def __init__(self, runtime) -> None:
        super().__init__(runtime)
        self._attr_name = "pending measurement"
        self._attr_unique_id = f"{runtime.entry.entry_id}_pending"

    @property
    def native_value(self) -> str | None:
        pending = self.runtime.pending
        if pending is None:
            return None
        return ", ".join(pending.get("candidates", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.pending or {}


class XiaomiScaleDiagnosticSensor(XiaomiScaleBaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime) -> None:
        super().__init__(runtime)
        self._attr_name = "last BLE measurement"
        self._attr_unique_id = f"{runtime.entry.entry_id}_last_ble_measurement"

    @property
    def native_value(self) -> str | None:
        return self.runtime.last_diagnostic.get("state")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.last_diagnostic


class XiaomiScaleHistorySensor(XiaomiScaleBaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime) -> None:
        super().__init__(runtime)
        self._attr_name = "history"
        self._attr_unique_id = f"{runtime.entry.entry_id}_history"

    @property
    def native_value(self) -> int:
        return sum(len(measurements) for measurements in self.runtime.history.data.values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.history.summary()
