"""Config flow for Shelly Dimmer WebSocket integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_USERNAME, default=""): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def _test_connection(host: str, port: int, username: str, password: str) -> str | None:
    """Try to connect to the Shelly and return device ID or raise."""
    import json
    uri = f"ws://{host}:{port}/rpc"
    try:
        session = aiohttp.ClientSession()
        async with session.ws_connect(uri, timeout=aiohttp.ClientTimeout(total=5)) as ws:
            payload = json.dumps({"id": 1, "src": "ha-config-test", "method": "Shelly.GetDeviceInfo"})
            await ws.send_str(payload)
            msg = await asyncio.wait_for(ws.receive(), timeout=5)
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                result = data.get("result", {})
                if data.get("error", {}).get("code") == 401:
                    return None  # auth required but not yet provided
                return result.get("id", host)
        await session.close()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        raise
    finally:
        await session.close()
    return host


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "").strip()
            name = user_input[CONF_NAME].strip()

            # Prevent duplicate entries for the same host
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                device_id = await _test_connection(host, port, username, password)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during connection test")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
