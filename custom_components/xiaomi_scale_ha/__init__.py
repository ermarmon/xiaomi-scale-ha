from __future__ import annotations

import logging
from time import monotonic
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_MAC, CONF_USERS, DOMAIN, SIGNAL_MEASUREMENT
from .history import UserHistory
from .parser import MISCALE_V1_UUID, MISCALE_V2_UUID, ScaleMeasurement, parse_service_info

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


class XiaomiScaleRuntime:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.name: str = entry.data[CONF_NAME]
        self.mac: str = entry.data[CONF_MAC].upper()
        self.users: list[dict[str, Any]] = entry.data[CONF_USERS]
        self.history = UserHistory(hass, f"{DOMAIN}_{entry.entry_id}_history")
        self.latest_by_user: dict[str, dict[str, Any]] = {}
        self.pending: dict[str, Any] | None = None
        self._last_signature: tuple[tuple[float, int | None], float] | None = None

    async def async_setup(self) -> None:
        await self.history.async_load()

    async def async_handle_measurement(self, measurement: ScaleMeasurement) -> None:
        signature = (measurement.weight, measurement.impedance)
        now = monotonic()
        if self._last_signature and signature == self._last_signature[0] and now - self._last_signature[1] < 30:
            return
        self._last_signature = (signature, now)

        candidates = self.history.candidates(measurement.weight, self.users)
        payload = {
            "weight": measurement.weight,
            "unit": measurement.unit,
            "timestamp": measurement.timestamp,
            "impedance": measurement.impedance,
            "source_address": measurement.source_address,
            "rssi": measurement.rssi,
        }
        if len(candidates) == 1:
            user_name = candidates[0]
            user = next(item for item in self.users if item["NAME"] == user_name)
            payload.update(_build_metrics(payload, user))
            self.latest_by_user[user_name] = payload
            self.pending = None
            await self.history.async_add_measurement(user_name, measurement.weight, measurement.timestamp)
            async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)
            return

        if len(candidates) > 1:
            self.pending = {**payload, "candidates": candidates}
            async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)
            return

        _LOGGER.info("No configured user matched %.2f %s", measurement.weight, measurement.unit)


def _build_metrics(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    weight = float(payload["weight"])
    if payload["unit"] == "lbs":
        calc_weight = round(weight * 0.4536, 2)
    elif payload["unit"] == "jin":
        calc_weight = round(weight * 0.5, 2)
    else:
        calc_weight = weight

    height_m = float(user["HEIGHT"]) / 100
    result = {"bmi": round(calc_weight / (height_m * height_m), 2)}

    impedance = payload.get("impedance")
    if impedance:
        try:
            from .body_metrics import bodyMetrics

            age = _age_years(user["DOB"])
            metrics = bodyMetrics(calc_weight, int(user["HEIGHT"]), age, user["SEX"], int(impedance))
            result.update(
                {
                    "basal_metabolism": round(metrics.getBMR(), 2),
                    "visceral_fat": round(metrics.getVisceralFat(), 2),
                    "lean_body_mass": round(metrics.getLBMCoefficient(), 2),
                    "body_fat": round(metrics.getFatPercentage(), 2),
                    "water": round(metrics.getWaterPercentage(), 2),
                    "bone_mass": round(metrics.getBoneMass(), 2),
                    "muscle_mass": round(metrics.getMuscleMass(), 2),
                    "protein": round(metrics.getProteinPercentage(), 2),
                    "metabolic_age": round(metrics.getMetabolicAge()),
                }
            )
        except Exception as err:
            _LOGGER.debug("Unable to calculate impedance metrics: %s", err)
    return result


def _age_years(dob: str) -> float:
    from datetime import datetime

    born = datetime.strptime(dob, "%Y-%m-%d")
    today = datetime.today()
    return abs((today - born).days) / 365


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime = XiaomiScaleRuntime(hass, entry)
    await runtime.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    @callback
    def _async_discovered_device(service_info: bluetooth.BluetoothServiceInfoBleak, change: bluetooth.BluetoothChange) -> None:
        if service_info.address.upper() != runtime.mac:
            return
        try:
            measurement = parse_service_info(service_info)
        except Exception as err:
            _LOGGER.warning("Could not parse Xiaomi scale advertisement: %s", err)
            return
        if measurement is None:
            return
        if not measurement.stabilized:
            _LOGGER.debug("Scale reading seen but not stabilized yet: %.2f %s", measurement.weight, measurement.unit)
            return
        runtime.hass.async_create_task(runtime.async_handle_measurement(measurement))

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_discovered_device,
            {"address": runtime.mac, "connectable": False},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_discovered_device,
            {"service_uuid": MISCALE_V2_UUID, "connectable": False},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_discovered_device,
            {"service_uuid": MISCALE_V1_UUID, "connectable": False},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
