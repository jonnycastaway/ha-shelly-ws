"""Shelly Dimmer WebSocket integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, PLATFORMS
from .websocket_client import ShellyWebSocketClient

_LOGGER = logging.getLogger(__name__)

SIGNAL_UPDATE = f"{DOMAIN}_update_{{entry_id}}"
SIGNAL_CONNECTED = f"{DOMAIN}_connected_{{entry_id}}"
SIGNAL_DISCONNECTED = f"{DOMAIN}_disconnected_{{entry_id}}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Shelly Dimmer WS from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data.get(CONF_USERNAME) or None
    password = entry.data.get(CONF_PASSWORD) or None

    def on_update(data: dict) -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE.format(entry_id=entry.entry_id), data)

    def on_connected() -> None:
        async_dispatcher_send(hass, SIGNAL_CONNECTED.format(entry_id=entry.entry_id))

    def on_disconnected() -> None:
        async_dispatcher_send(hass, SIGNAL_DISCONNECTED.format(entry_id=entry.entry_id))

    client = ShellyWebSocketClient(
        host=host,
        port=port,
        username=username,
        password=password,
        on_update=on_update,
        on_connected=on_connected,
        on_disconnected=on_disconnected,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await client.start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client: ShellyWebSocketClient = hass.data[DOMAIN].pop(entry.entry_id)
        await client.stop()
    return unload_ok
