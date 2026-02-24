"""Sensor platform for Shelly Dimmer WebSocket – power measurements."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SIGNAL_CONNECTED, SIGNAL_DISCONNECTED, SIGNAL_UPDATE
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShellySensorDescription(SensorEntityDescription):
    """Describes a Shelly sensor."""
    data_key: str = ""
    pm_key: str = "pm1:0"


SENSOR_DESCRIPTIONS: tuple[ShellySensorDescription, ...] = (
    ShellySensorDescription(
        key="power",
        name="Leistung",
        data_key="apower",
        pm_key="pm1:0",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ShellySensorDescription(
        key="voltage",
        name="Spannung",
        data_key="voltage",
        pm_key="pm1:0",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ShellySensorDescription(
        key="current",
        name="Stromstärke",
        data_key="current",
        pm_key="pm1:0",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ShellySensorDescription(
        key="energy",
        name="Energie",
        data_key="aenergy",
        pm_key="pm1:0",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Shelly power sensors."""
    async_add_entities(
        [ShellyPowerSensor(entry, desc) for desc in SENSOR_DESCRIPTIONS]
    )


class ShellyPowerSensor(SensorEntity):
    """A single Shelly power measurement sensor."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, description: ShellySensorDescription) -> None:
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Shelly",
            model="Dimmer 0/1-10V PM Gen3",
        )
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
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
        params = data.get("params", data.get("result", {}))
        desc: ShellySensorDescription = self.entity_description  # type: ignore[assignment]

        pm_data = params.get(desc.pm_key, {})
        if not pm_data:
            return

        raw = pm_data.get(desc.data_key)
        if raw is None:
            return

        # aenergy is a nested object: {"total": float, ...}
        if isinstance(raw, dict):
            raw = raw.get("total")

        if raw is not None:
            self._attr_native_value = round(raw, 3)
            self._attr_available = True
            self.async_write_ha_state()
