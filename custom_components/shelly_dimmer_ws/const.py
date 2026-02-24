"""Constants for Shelly Dimmer WebSocket integration."""

DOMAIN = "shelly_dimmer_ws"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_PORT = 80
DEFAULT_NAME = "Shelly Dimmer"

PLATFORMS = ["light", "sensor", "button"]

# WebSocket reconnect
WS_RECONNECT_INTERVAL = 10  # seconds
WS_HEARTBEAT_INTERVAL = 30  # seconds

# Sensor types
SENSOR_POWER = "power"
SENSOR_VOLTAGE = "voltage"
SENSOR_CURRENT = "current"
SENSOR_ENERGY = "energy"
