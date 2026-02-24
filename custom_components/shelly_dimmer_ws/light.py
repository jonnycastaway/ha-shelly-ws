"""Light platform for Shelly Dimmer WebSocket integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_CONNECTED, SIGNAL_DISCONNECTED, SIGNAL_UPDATE
from .const import DOMAIN
from .websocket_client import ShellyWebSocketClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Shelly dimmer light."""
    client: ShellyWebSocketClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ShellyDimmerLight(entry, client)])


class ShellyDimmerLight(LightEntity):
    """Represents the Shelly Dimmer as a HA light entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_has_entity_name = True
    _attr_name = None  # use device name as entity name

    def __init__(self, entry: ConfigEntry, client: ShellyWebSocketClient) -> None:
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Shelly",
            model="Dimmer 0/1-10V PM Gen3",
        )
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Register dispatcher callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_CONNECTED.format(entry_id=self._entry.entry_id),
                self._handle_connected,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_DISCONNECTED.format(entry_id=self._entry.entry_id),
                self._handle_disconnected,
            )
        )
        # Sofort initialen Status holen, falls WS bereits verbunden ist
        if self._client.connected:
            self.hass.async_create_task(self._fetch_initial())

    async def _fetch_initial(self) -> None:
        try:
            result = await self._client.call("Shelly.GetStatus")
            self._handle_update({"method": "NotifyStatus", "params": result})
        except Exception as err:
            _LOGGER.debug("Initial fetch failed: %s", err)

    @callback
    def _handle_connected(self) -> None:
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def _handle_disconnected(self) -> None:
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def _handle_update(self, data: dict) -> None:
        """Process NotifyStatus or GetStatus result."""
        params = data.get("params", data.get("result", {}))

        light_data = params.get("light:0", {})
        if not light_data:
            return

        if "output" in light_data:
            self._attr_is_on = light_data["output"]
        if "brightness" in light_data:
            # Shelly brightness: 0–100 → HA brightness: 0–255
            self._attr_brightness = round(light_data["brightness"] / 100 * 255)
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally set brightness."""
        params: dict[str, Any] = {"id": 0, "on": True}
        if ATTR_BRIGHTNESS in kwargs:
            # HA brightness 0–255 → Shelly 0–100
            params["brightness"] = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
        await self._client.call("Light.Set", params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._client.call("Light.Set", {"id": 0, "on": False})
