"""WebSocket client for Shelly Dimmer Gen3 RPC API."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Callable

import aiohttp

from .const import WS_HEARTBEAT_INTERVAL, WS_RECONNECT_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ShellyWebSocketClient:
    """Manages a persistent WebSocket connection to a Shelly Gen3 device."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        on_update: Callable[[dict], None],
        on_connected: Callable[[], None] | None = None,
        on_disconnected: Callable[[], None] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._on_update = on_update
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._connected = False
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def uri(self) -> str:
        return f"ws://{self._host}:{self._port}/rpc"

    @property
    def connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        """Start the WebSocket connection loop."""
        self._running = True
        self._task = asyncio.create_task(self._connection_loop())

    async def stop(self) -> None:
        """Stop the WebSocket connection."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._task:
            self._task.cancel()
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        self._connected = False

    async def _connection_loop(self) -> None:
        """Reconnect loop – keeps connection alive."""
        while self._running:
            try:
                await self._connect()
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.warning("WebSocket connection error: %s – retrying in %ss", err, WS_RECONNECT_INTERVAL)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Unexpected WebSocket error: %s", err)

            if self._connected:
                self._connected = False
                if self._on_disconnected:
                    self._on_disconnected()

            if self._running:
                await asyncio.sleep(WS_RECONNECT_INTERVAL)

    async def _connect(self) -> None:
        """Open WebSocket and listen for messages."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        _LOGGER.debug("Connecting to %s", self.uri)
        async with self._session.ws_connect(self.uri, heartbeat=WS_HEARTBEAT_INTERVAL) as ws:
            self._ws = ws
            self._connected = True
            _LOGGER.info("Connected to Shelly at %s", self.uri)

            if self._on_connected:
                self._on_connected()

            # Authenticate if credentials are provided
            if self._username and self._password:
                await self._authenticate()
            else:
                # Send initial request to register as a client for push notifications
                await self._send_rpc("Shelly.GetStatus", client_id="ha-client")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", ws.exception())
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                    _LOGGER.debug("WebSocket closed")
                    break

    async def _authenticate(self) -> None:
        """Shelly Gen3 Digest-based WebSocket authentication."""
        # Step 1: Send request without auth to get the challenge
        msg_id = self._next_id()
        payload = {
            "id": msg_id,
            "src": "ha-client",
            "method": "Shelly.GetStatus",
        }
        await self._ws.send_str(json.dumps(payload))

        # Wait for auth challenge (error code 401)
        raw = await self._ws.receive_str(timeout=5)
        data = json.loads(raw)

        if data.get("error", {}).get("code") == 401:
            auth_info = data["error"]["message"]
            # Parse realm and nonce from error message
            # Format: "realm:nonce" or JSON
            try:
                auth_data = json.loads(auth_info)
            except (json.JSONDecodeError, TypeError):
                parts = auth_info.split(":")
                auth_data = {"realm": parts[0], "nonce": parts[1]} if len(parts) >= 2 else {}

            realm = auth_data.get("realm", self._host)
            nonce = auth_data.get("nonce", "")

            # Build HA1 digest
            ha1 = hashlib.sha256(f"{self._username}:{realm}:{self._password}".encode()).hexdigest()
            ha2 = hashlib.sha256(b"dummy_method:dummy_uri").hexdigest()
            nc = "00000001"
            cnonce = hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
            response = hashlib.sha256(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode()).hexdigest()

            auth_payload = {
                "id": self._next_id(),
                "src": "ha-client",
                "method": "Shelly.GetStatus",
                "auth": {
                    "realm": realm,
                    "username": self._username,
                    "nonce": nonce,
                    "cnonce": cnonce,
                    "response": response,
                    "algorithm": "SHA-256",
                },
            }
            await self._ws.send_str(json.dumps(auth_payload))
            _LOGGER.debug("Authentication payload sent")
        else:
            # No auth required – process the response directly
            await self._handle_message(raw)

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def _send_rpc(self, method: str, params: dict | None = None, client_id: str = "ha-client") -> int:
        """Send an RPC call over WebSocket."""
        msg_id = self._next_id()
        payload: dict[str, Any] = {
            "id": msg_id,
            "src": client_id,
            "method": method,
        }
        if params:
            payload["params"] = params
        await self._ws.send_str(json.dumps(payload))
        return msg_id

    async def call(self, method: str, params: dict | None = None) -> dict:
        """Send RPC and await response."""
        if not self._connected or self._ws is None:
            raise ConnectionError("WebSocket not connected")
        msg_id = await self._send_rpc(method, params)
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[msg_id] = future
        try:
            return await asyncio.wait_for(future, timeout=10)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise TimeoutError(f"RPC call {method} timed out")

    async def _handle_message(self, raw: str) -> None:
        """Dispatch incoming WebSocket message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON received: %s", raw)
            return

        _LOGGER.debug("WS message: %s", data)

        msg_id = data.get("id")
        method = data.get("method")

        # Resolve pending futures (responses to our calls)
        if msg_id and msg_id in self._pending:
            future = self._pending.pop(msg_id)
            if not future.done():
                if "error" in data:
                    future.set_exception(Exception(data["error"].get("message", "RPC error")))
                else:
                    future.set_result(data.get("result", data))
            return

        # Handle push notifications
        if method in ("NotifyStatus", "NotifyEvent"):
            self._on_update(data)
        elif "result" in data:
            # Unsolicited result (e.g. from initial GetStatus)
            self._on_update({"method": "NotifyStatus", "params": data["result"]})
