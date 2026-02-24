"""Button platform for Shelly Dimmer WebSocket – reboot."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .websocket_client import ShellyWebSocketClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Shelly reboot button."""
    client: ShellyWebSocketClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ShellyRebootButton(entry, client)])


class ShellyRebootButton(ButtonEntity):
    """Button to reboot the Shelly device."""

    _attr_has_entity_name = True
    _attr_name = "Neustart"
    _attr_icon = "mdi:restart"

    def __init__(self, entry: ConfigEntry, client: ShellyWebSocketClient) -> None:
        self._entry = entry
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_reboot"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Shelly",
            model="Dimmer 0/1-10V PM Gen3",
        )

    async def async_press(self) -> None:
        """Send reboot command to Shelly."""
        _LOGGER.info("Rebooting Shelly %s", self._entry.data[CONF_NAME])
        await self._client.call("Shelly.Reboot")
