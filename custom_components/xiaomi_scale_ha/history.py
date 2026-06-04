from __future__ import annotations

from statistics import mean
from typing import Any

from homeassistant.helpers.storage import Store


class UserHistory:
    def __init__(self, hass, key: str) -> None:
        self._store = Store(hass, 1, key)
        self.data: dict[str, list[dict[str, Any]]] = {}

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            users = loaded.get("users", {})
            if isinstance(users, dict):
                self.data = users

    async def async_add_measurement(
        self,
        user_name: str,
        weight: float,
        timestamp: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        measurements = self.data.setdefault(user_name, [])
        record = {"weight": float(weight), "timestamp": timestamp}
        if payload:
            record.update(
                {
                    key: value
                    for key, value in payload.items()
                    if not key.startswith("_")
                }
            )
        measurements.append(record)
        self.data[user_name] = measurements[-10:]
        await self._store.async_save({"users": self.data})

    async def async_clear(self, user_name: str | None = None) -> None:
        if user_name:
            self.data.pop(user_name, None)
        else:
            self.data = {}
        await self._store.async_save({"users": self.data})

    async def async_delete_measurement(self, user_name: str, index: int) -> None:
        measurements = self.data.get(user_name, [])
        if not measurements:
            return
        if index < 0:
            index = len(measurements) + index
        if 0 <= index < len(measurements):
            measurements.pop(index)
            if measurements:
                self.data[user_name] = measurements
            else:
                self.data.pop(user_name, None)
            await self._store.async_save({"users": self.data})

    def summary(self) -> dict[str, Any]:
        return {
            user_name: {
                "count": len(measurements),
                "measurements": measurements,
            }
            for user_name, measurements in self.data.items()
        }

    def latest_measurement(self, user_name: str) -> dict[str, Any] | None:
        measurements = self.data.get(user_name, [])
        if not measurements:
            return None
        latest = dict(measurements[-1])
        latest.setdefault("unit", "kg")
        latest.setdefault("impedance", None)
        latest.setdefault("has_impedance", latest.get("impedance") is not None)
        latest["_restored"] = True
        latest["_finalized"] = True
        return latest

    def candidates(self, weight: float, users: list[dict[str, Any]], tolerance_kg: float = 2.0) -> list[str]:
        candidates: list[str] = []
        for user in users:
            name = user.get("NAME")
            if not isinstance(name, str):
                continue
            history = self.data.get(name, [])
            if len(history) >= 3:
                last_weights = [float(item["weight"]) for item in history[-10:] if "weight" in item]
                if last_weights and abs(mean(last_weights) - weight) <= tolerance_kg:
                    candidates.append(name)
                    continue
            gt = user.get("GT")
            lt = user.get("LT")
            if isinstance(gt, (int, float)) and isinstance(lt, (int, float)) and gt < weight < lt:
                candidates.append(name)
        return candidates
