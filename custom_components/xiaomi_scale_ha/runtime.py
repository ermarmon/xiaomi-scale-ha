from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ALEXA_ACTIONS,
    CONF_ALEXA_ACTION_SCRIPT,
    CONF_ALEXA_SUPPRESS_CONFIRMATION,
    CONF_IMPEDANCE_WAIT_SECONDS,
    CONF_MAC,
    CONF_NOTIFY_ASSIGNED,
    CONF_NOTIFY_SERVICE,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_USER_ALEXA_DEVICE,
    CONF_USER_NOTIFY_SERVICE,
    CONF_USERS,
    DOMAIN,
    EVENT_ASSIGNED,
    EVENT_DISCARDED,
    EVENT_PENDING,
    SERVICE_ASSIGN_PENDING,
    SERVICE_DISCARD_PENDING,
    SIGNAL_MEASUREMENT,
)
from .history import UserHistory
from .metrics import build_metrics, same_weight_session, slug
from .parser import ScaleMeasurement

_LOGGER = logging.getLogger(__name__)


class XiaomiScaleRuntime:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.name: str = entry.data["name"]
        self.mac: str = entry.data[CONF_MAC].upper()
        self.users: list[dict[str, Any]] = entry.options.get(CONF_USERS, entry.data[CONF_USERS])
        self.history = UserHistory(hass, f"{DOMAIN}_{entry.entry_id}_history")
        self.latest_by_user: dict[str, dict[str, Any]] = {}
        self.pending: dict[str, Any] | None = None
        self.last_diagnostic: dict[str, Any] = {"state": "starting"}
        self._action_to_user: dict[str, str | None] = {}
        self._alexa_event_to_user: dict[str, str] = {}
        self._last_signature: tuple[float, int | None] | None = None
        self._last_signature_time: float = 0
        self._pending_finalize: dict[str, asyncio.Task] = {}

    async def async_setup(self) -> None:
        await self.history.async_load()
        self._restore_latest_measurements()

    def _restore_latest_measurements(self) -> None:
        for user in self.users:
            user_name = user.get("NAME")
            if not isinstance(user_name, str):
                continue
            latest = self.history.latest_measurement(user_name)
            if latest is not None:
                self.latest_by_user[user_name] = latest

    async def async_clear_history(self, user_name: str | None = None) -> None:
        await self.history.async_clear(user_name)
        self.last_diagnostic = {"state": "history_cleared", "user_name": user_name}
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)

    async def async_delete_history_measurement(self, user_name: str, index: int) -> None:
        await self.history.async_delete_measurement(user_name, index)
        self.last_diagnostic = {
            "state": "history_measurement_deleted",
            "user_name": user_name,
            "index": index,
        }
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)

    async def async_handle_measurement(self, measurement: ScaleMeasurement) -> None:
        sig = (measurement.weight, measurement.impedance)
        now = monotonic()
        if self._last_signature == sig and now - self._last_signature_time < 30:
            return
        self._last_signature = sig
        self._last_signature_time = now

        candidates = self.history.candidates(measurement.weight, self.users)
        payload = {
            "weight": measurement.weight,
            "unit": measurement.unit,
            "timestamp": measurement.timestamp,
            "impedance": measurement.impedance,
            "has_impedance": measurement.impedance is not None,
            "source_address": measurement.source_address,
            "rssi": measurement.rssi,
        }
        self.last_diagnostic = {
            "state": "measurement_received",
            "timestamp": measurement.timestamp,
            "weight": measurement.weight,
            "unit": measurement.unit,
            "impedance": measurement.impedance,
            "candidates": candidates,
            "source_address": measurement.source_address,
            "rssi": measurement.rssi,
        }

        if len(candidates) == 1:
            user_name = candidates[0]
            self.last_diagnostic["state"] = "assigned"
            self.last_diagnostic["user_name"] = user_name
            await self.async_assign_payload(payload, user_name, finalize=False)
            return

        if len(candidates) > 1:
            self.last_diagnostic["state"] = "pending"
            await self.async_set_pending({**payload, "candidates": candidates})
            return

        self.last_diagnostic["state"] = "no_user_matched"
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)
        _LOGGER.info("No configured user matched %.2f %s", measurement.weight, measurement.unit)

    async def async_set_pending(self, payload: dict[str, Any]) -> None:
        self.pending = payload
        self._action_to_user = self._build_action_map(payload["candidates"])
        self.hass.bus.async_fire(EVENT_PENDING, self.pending_event_data)
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)
        await self.async_send_pending_notification()
        await self.async_send_alexa_actionable_notifications()

    async def async_assign_pending(self, user_name: str) -> bool:
        if self.pending is None:
            return False
        await self.async_assign_payload(dict(self.pending), user_name, finalize=True)
        return True

    async def async_assign_payload(self, payload: dict[str, Any], user_name: str, finalize: bool) -> None:
        user = next((item for item in self.users if item["NAME"] == user_name), None)
        if user is None:
            raise HomeAssistantError(f"Unknown user: {user_name}")

        payload.update(build_metrics(payload, user))
        existing = self.latest_by_user.get(user_name)
        if existing and same_weight_session(existing, payload):
            if existing.get("_finalized"):
                payload["_finalized"] = True
            payload = {**existing, **payload}
        self.latest_by_user[user_name] = payload
        self.pending = None
        self._action_to_user = {}
        self._alexa_event_to_user = {}
        await self._dismiss_pending_notification()
        if finalize:
            await self._finalize_assigned_measurement(user, payload)
        else:
            self._schedule_assigned_finalize(user, payload)
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)

    def _schedule_assigned_finalize(self, user: dict[str, Any], payload: dict[str, Any]) -> None:
        user_name = user["NAME"]
        task = self._pending_finalize.pop(user_name, None)
        if task is not None:
            task.cancel()

        wait_seconds = self.entry.options.get(CONF_IMPEDANCE_WAIT_SECONDS, 8)
        if payload.get("impedance") is not None or wait_seconds <= 0:
            self.hass.async_create_task(self._finalize_assigned_measurement(user, payload))
            return

        self._pending_finalize[user_name] = self.hass.async_create_task(
            self._delayed_finalize_assigned_measurement(user, wait_seconds)
        )

    async def _delayed_finalize_assigned_measurement(self, user: dict[str, Any], wait_seconds: int) -> None:
        user_name = user["NAME"]
        try:
            await asyncio.sleep(wait_seconds)
            payload = self.latest_by_user.get(user_name)
            if payload is not None:
                await self._finalize_assigned_measurement(user, payload)
        except asyncio.CancelledError:
            raise
        finally:
            if self._pending_finalize.get(user_name) is asyncio.current_task():
                self._pending_finalize.pop(user_name, None)

    async def _finalize_assigned_measurement(self, user: dict[str, Any], payload: dict[str, Any]) -> None:
        user_name = user["NAME"]
        if payload.get("_finalized"):
            async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)
            return
        payload["_finalized"] = True
        await self.history.async_add_measurement(
            user_name, float(payload["weight"]), payload["timestamp"], payload
        )
        await self._send_assigned_notification(user, payload)
        self.hass.bus.async_fire(
            EVENT_ASSIGNED,
            {"entry_id": self.entry.entry_id, "user_name": user_name, **payload},
        )
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)

    async def async_discard_pending(self, reason: str = "discarded") -> bool:
        if self.pending is None:
            return False
        payload = self.pending
        self.pending = None
        self._action_to_user = {}
        self._alexa_event_to_user = {}
        for task in self._pending_finalize.values():
            task.cancel()
        self._pending_finalize.clear()
        await self._dismiss_pending_notification()
        self.hass.bus.async_fire(
            EVENT_DISCARDED,
            {"entry_id": self.entry.entry_id, "reason": reason, **payload},
        )
        async_dispatcher_send(self.hass, SIGNAL_MEASUREMENT, self.entry.entry_id)
        return True

    async def async_send_pending_notification(self) -> None:
        if self.pending is None:
            return
        candidates = self.pending.get("candidates", [])
        weight = self.pending["weight"]
        unit = self.pending["unit"]
        message = f"Pesaje sin asignar: {weight} {unit}. Candidatos: {', '.join(candidates)}."

        if self.entry.options.get(CONF_PERSISTENT_NOTIFICATION, True):
            actions = "\n".join(
                f"- Asignar a {c}: ejecuta `{DOMAIN}.{SERVICE_ASSIGN_PENDING}` con `user_name: {c}`"
                for c in candidates
            )
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "notification_id": self.notification_id,
                    "title": "Xiaomi Scale HA",
                    "message": f"{message}\n\n{actions}\n- Descartar: `{DOMAIN}.{SERVICE_DISCARD_PENDING}`",
                },
                blocking=False,
            )

        for notify_service in self._notify_services_for_users(candidates):
            await self._send_pending_mobile_notification(notify_service, message)

    async def async_send_alexa_actionable_notifications(self) -> None:
        if not self.pending or not self.entry.options.get(CONF_ALEXA_ACTIONS, False):
            return
        script_service = self.entry.options.get(
            CONF_ALEXA_ACTION_SCRIPT, "script.activate_alexa_actionable_notification"
        ).strip()
        if not script_service or "." not in script_service:
            _LOGGER.warning("Invalid Alexa actionable script service: %s", script_service)
            return

        domain, service = script_service.split(".", 1)
        candidates = self.pending.get("candidates", [])
        weight = self.pending["weight"]
        unit = self.pending["unit"]
        suppress = self.entry.options.get(CONF_ALEXA_SUPPRESS_CONFIRMATION, True)
        self._alexa_event_to_user = {}

        for user_name in candidates:
            user = next((item for item in self.users if item["NAME"] == user_name), None)
            if not user:
                continue
            alexa_device = user.get(CONF_USER_ALEXA_DEVICE, "")
            if not isinstance(alexa_device, str) or not alexa_device.strip():
                continue
            event_id = f"{DOMAIN}_{self.entry.entry_id}_alexa_{slug(user_name)}"
            self._alexa_event_to_user[event_id] = user_name
            await self.hass.services.async_call(
                domain,
                service,
                {
                    "text": f"Pesaje sin asignar de {weight} {unit}. {user_name}, ¿eres tú?",
                    "event_id": event_id,
                    "alexa_device": alexa_device.strip(),
                    "suppress_confirmation": suppress,
                },
                blocking=False,
            )

    async def async_handle_mobile_action(self, action: str) -> bool:
        if action not in self._action_to_user:
            return False
        user_name = self._action_to_user[action]
        if user_name is None:
            await self.async_discard_pending("mobile_action")
        else:
            await self.async_assign_pending(user_name)
        return True

    async def async_handle_alexa_action(self, event_id: str, response_type: str | None) -> bool:
        user_name = self._alexa_event_to_user.get(event_id)
        if user_name is None:
            return False
        if response_type == "ResponseYes":
            await self.async_assign_pending(user_name)
        elif response_type == "ResponseNo":
            _LOGGER.info("Alexa rejected pending measurement for %s", user_name)
        else:
            _LOGGER.debug("Ignoring Alexa response %s for event %s", response_type, event_id)
        return True

    @property
    def pending_event_data(self) -> dict[str, Any]:
        return {"entry_id": self.entry.entry_id, **(self.pending or {})}

    @property
    def notification_id(self) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_pending"

    def _build_action_map(self, candidates: list[str]) -> dict[str, str | None]:
        action_map: dict[str, str | None] = {
            self._action_for(i, c): c for i, c in enumerate(candidates)
        }
        action_map[self._discard_action] = None
        return action_map

    def _action_for(self, index: int, candidate: str) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_assign_{index}_{slug(candidate)}"

    @property
    def _discard_action(self) -> str:
        return f"{DOMAIN}_{self.entry.entry_id}_discard"

    def _notify_service_for_user(self, user: dict[str, Any]) -> str:
        svc = user.get(CONF_USER_NOTIFY_SERVICE, "")
        return svc.strip() if isinstance(svc, str) else ""

    def _notify_services_for_users(self, user_names: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for user_name in user_names:
            user = next((u for u in self.users if u["NAME"] == user_name), None)
            svc = self._notify_service_for_user(user) if user else ""
            if svc and svc not in seen:
                seen.add(svc)
                result.append(svc)
        return result

    async def _send_assigned_notification(self, user: dict[str, Any], payload: dict[str, Any]) -> None:
        if not self.entry.options.get(CONF_NOTIFY_ASSIGNED, False):
            return
        notify_service = self._notify_service_for_user(user)
        if not notify_service:
            return
        user_name = user["NAME"]
        weight = payload["weight"]
        unit = payload["unit"]
        message = f"{user_name}: {weight} {unit}"
        details = []
        if (bmi := payload.get("bmi")) is not None:
            details.append(f"BMI {bmi}")
        if (body_fat := payload.get("body_fat")) is not None:
            details.append(f"grasa {body_fat}%")
        if details:
            message = f"{message} ({', '.join(details)})"
        await self._send_mobile_notification(
            notify_service,
            "Peso registrado",
            message,
            data={"tag": f"{DOMAIN}_{self.entry.entry_id}_{slug(user_name)}_assigned", "group": DOMAIN},
        )

    async def _send_mobile_notification(
        self, notify_service: str, title: str, message: str, data: dict[str, Any] | None = None
    ) -> None:
        if "." not in notify_service:
            _LOGGER.warning("Invalid notify service: %s", notify_service)
            return
        domain, service = notify_service.split(".", 1)
        if domain != "notify":
            _LOGGER.warning("Notify service must start with notify.: %s", notify_service)
            return
        await self.hass.services.async_call(
            domain, service,
            {"title": title, "message": message, "data": data or {}},
            blocking=False,
        )

    async def _send_pending_mobile_notification(self, notify_service: str, message: str) -> None:
        candidates = self.pending.get("candidates", []) if self.pending else []
        actions = [
            {"action": self._action_for(i, c), "title": f"Soy {c}"}
            for i, c in enumerate(candidates)
        ]
        actions.append({"action": self._discard_action, "title": "Descartar"})
        await self._send_mobile_notification(
            notify_service,
            "Pesaje sin asignar",
            message,
            data={"tag": self.notification_id, "group": DOMAIN, "actions": actions},
        )

    async def _dismiss_pending_notification(self) -> None:
        await self.hass.services.async_call(
            "persistent_notification", "dismiss",
            {"notification_id": self.notification_id},
            blocking=False,
        )
