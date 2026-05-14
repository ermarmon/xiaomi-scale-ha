from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import CONF_MAC, CONF_USERS, DEFAULT_USERS_JSON, DOMAIN


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
    return users


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
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Xiaomi Scale"): str,
                vol.Required(CONF_MAC): str,
                vol.Required(CONF_USERS, default=DEFAULT_USERS_JSON): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
