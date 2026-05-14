from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import (
    CONF_ALEXA_ACTIONS,
    CONF_ALEXA_ACTION_SCRIPT,
    CONF_ALEXA_SUPPRESS_CONFIRMATION,
    CONF_IMPEDANCE_WAIT_SECONDS,
    CONF_MAC,
    CONF_NOTIFY_ASSIGNED,
    CONF_NOTIFY_SERVICE,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_USER_NOTIFY_SERVICE,
    CONF_USER_ALEXA_DEVICE,
    CONF_USERS,
    DEFAULT_USERS_JSON,
    DOMAIN,
)


def _parse_users(value: str) -> list[dict[str, Any]]:
    users = json.loads(value)
    if not isinstance(users, list) or not users:
        raise ValueError("users must be a non-empty list")
    for user in users:
        if not isinstance(user, dict):
            raise ValueError("each user must be an object")
        for key in ("NAME", "GT", "LT", "SEX", "HEIGHT", "DOB"):
            if key not in user:
                raise ValueError(f"missing {key}")
        if user["SEX"] not in ("male", "female"):
            raise ValueError("SEX must be male or female")
        if CONF_USER_NOTIFY_SERVICE in user and not isinstance(user[CONF_USER_NOTIFY_SERVICE], str):
            raise ValueError(f"{CONF_USER_NOTIFY_SERVICE} must be a string")
        if CONF_USER_ALEXA_DEVICE in user and not isinstance(user[CONF_USER_ALEXA_DEVICE], str):
            raise ValueError(f"{CONF_USER_ALEXA_DEVICE} must be a string")
    return users


def _users_json(users: list[dict[str, Any]]) -> str:
    return json.dumps(users, indent=2)


class XiaomiScaleHaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            mac = user_input[CONF_MAC].strip().upper()
            try:
                users = _parse_users(user_input[CONF_USERS])
            except (json.JSONDecodeError, ValueError):
                errors[CONF_USERS] = "invalid_users"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_MAC: mac,
                        CONF_USERS: users,
                    },
                    options={
                        CONF_NOTIFY_SERVICE: user_input.get(CONF_NOTIFY_SERVICE, "").strip(),
                        CONF_PERSISTENT_NOTIFICATION: user_input.get(CONF_PERSISTENT_NOTIFICATION, True),
                        CONF_NOTIFY_ASSIGNED: user_input.get(CONF_NOTIFY_ASSIGNED, False),
                        CONF_IMPEDANCE_WAIT_SECONDS: user_input.get(CONF_IMPEDANCE_WAIT_SECONDS, 8),
                        CONF_ALEXA_ACTIONS: user_input.get(CONF_ALEXA_ACTIONS, False),
                        CONF_ALEXA_ACTION_SCRIPT: user_input.get(
                            CONF_ALEXA_ACTION_SCRIPT,
                            "script.activate_alexa_actionable_notification",
                        ).strip(),
                        CONF_ALEXA_SUPPRESS_CONFIRMATION: user_input.get(
                            CONF_ALEXA_SUPPRESS_CONFIRMATION,
                            True,
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Xiaomi Scale"): str,
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_NOTIFY_SERVICE, default=""): str,
                vol.Optional(CONF_PERSISTENT_NOTIFICATION, default=True): bool,
                vol.Optional(CONF_NOTIFY_ASSIGNED, default=False): bool,
                vol.Optional(CONF_IMPEDANCE_WAIT_SECONDS, default=8): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=0, max=60),
                ),
                vol.Optional(CONF_ALEXA_ACTIONS, default=False): bool,
                vol.Optional(
                    CONF_ALEXA_ACTION_SCRIPT,
                    default="script.activate_alexa_actionable_notification",
                ): str,
                vol.Optional(CONF_ALEXA_SUPPRESS_CONFIRMATION, default=True): bool,
                vol.Required(CONF_USERS, default=DEFAULT_USERS_JSON): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return XiaomiScaleHaOptionsFlow()


class XiaomiScaleHaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                users = _parse_users(user_input[CONF_USERS])
            except (json.JSONDecodeError, ValueError):
                errors[CONF_USERS] = "invalid_users"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_NOTIFY_SERVICE: user_input.get(CONF_NOTIFY_SERVICE, "").strip(),
                        CONF_PERSISTENT_NOTIFICATION: user_input.get(CONF_PERSISTENT_NOTIFICATION, True),
                        CONF_NOTIFY_ASSIGNED: user_input.get(CONF_NOTIFY_ASSIGNED, False),
                        CONF_IMPEDANCE_WAIT_SECONDS: user_input.get(CONF_IMPEDANCE_WAIT_SECONDS, 8),
                        CONF_ALEXA_ACTIONS: user_input.get(CONF_ALEXA_ACTIONS, False),
                        CONF_ALEXA_ACTION_SCRIPT: user_input.get(
                            CONF_ALEXA_ACTION_SCRIPT,
                            "script.activate_alexa_actionable_notification",
                        ).strip(),
                        CONF_ALEXA_SUPPRESS_CONFIRMATION: user_input.get(
                            CONF_ALEXA_SUPPRESS_CONFIRMATION,
                            True,
                        ),
                        CONF_USERS: users,
                    },
                )

        options = self.config_entry.options
        users = options.get(CONF_USERS, self.config_entry.data.get(CONF_USERS, []))
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_SERVICE,
                    default=options.get(CONF_NOTIFY_SERVICE, ""),
                ): str,
                vol.Optional(
                    CONF_PERSISTENT_NOTIFICATION,
                    default=options.get(CONF_PERSISTENT_NOTIFICATION, True),
                ): bool,
                vol.Optional(
                    CONF_NOTIFY_ASSIGNED,
                    default=options.get(CONF_NOTIFY_ASSIGNED, False),
                ): bool,
                vol.Optional(
                    CONF_IMPEDANCE_WAIT_SECONDS,
                    default=options.get(CONF_IMPEDANCE_WAIT_SECONDS, 8),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
                vol.Optional(
                    CONF_ALEXA_ACTIONS,
                    default=options.get(CONF_ALEXA_ACTIONS, False),
                ): bool,
                vol.Optional(
                    CONF_ALEXA_ACTION_SCRIPT,
                    default=options.get(
                        CONF_ALEXA_ACTION_SCRIPT,
                        "script.activate_alexa_actionable_notification",
                    ),
                ): str,
                vol.Optional(
                    CONF_ALEXA_SUPPRESS_CONFIRMATION,
                    default=options.get(CONF_ALEXA_SUPPRESS_CONFIRMATION, True),
                ): bool,
                vol.Required(CONF_USERS, default=_users_json(users)): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
