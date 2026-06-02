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

# (key, label, unit, device_class, icon)
METRIC_DEFS: list[tuple[str, str, str | None, str | None, str | None]] = [
    ("bmi",              "BMI",              "kg/m²",              None,                      "mdi:human"),
    ("body_fat",         "body fat",         "%",                  None,                      "mdi:water-percent"),
    ("water",            "water",            "%",                  None,                      "mdi:water"),
    ("muscle_mass",      "muscle mass",      UnitOfMass.KILOGRAMS, SensorDeviceClass.WEIGHT,  None),
    ("bone_mass",        "bone mass",        UnitOfMass.KILOGRAMS, SensorDeviceClass.WEIGHT,  None),
    ("lean_body_mass",   "lean body mass",   UnitOfMass.KILOGRAMS, SensorDeviceClass.WEIGHT,  None),
    ("visceral_fat",     "visceral fat",     None,                 None,                      "mdi:stomach"),
    ("basal_metabolism", "basal metabolism", "kcal",               None,                      "mdi:fire"),
    ("protein",          "protein",          "%",                  None,                      "mdi:food-drumstick"),
    ("metabolic_age",    "metabolic age",    "years",              None,                      "mdi:calendar-clock"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for user in runtime.users:
        user_name = user["NAME"]
        entities.append(XiaomiScaleWeightSensor(runtime, user_name))
        for key, label, unit, device_class, icon in METRIC_DEFS:
            entities.append(XiaomiScaleMetricSensor(runtime, user_name, key, label, unit, device_class, icon))
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


class XiaomiScaleMetricSensor(XiaomiScaleBaseSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        runtime,
        user_name: str,
        key: str,
        label: str,
        unit: str | None,
        device_class: str | None,
        icon: str | None,
    ) -> None:
        super().__init__(runtime)
        self.user_name = user_name
        self._key = key
        self._attr_name = f"{user_name} {label}"
        self._attr_unique_id = f"{runtime.entry.entry_id}_{user_name.lower()}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if icon:
            self._attr_icon = icon

    @property
    def native_value(self) -> float | int | None:
        return self.runtime.last_metrics_by_user.get(self.user_name, {}).get(self._key)


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
        attrs = dict(self.runtime.last_diagnostic)
        if self.runtime.last_notification:
            attrs["last_notification"] = self.runtime.last_notification
        return attrs


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
