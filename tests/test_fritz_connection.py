"""Tests for FritzCallmonitorAdapter TCP connection lifecycle.

Reproduces the half-open socket bug: when the Fritz!Box reboots without
sending TCP-FIN, the kernel keeps the socket in ESTABLISHED state and
``readline()`` blocks forever. The adapter must detect this via a readline
timeout (and SO_KEEPALIVE on the socket) and trigger its reconnect loop.
"""

import asyncio
import socket
from unittest.mock import AsyncMock

from src.adapters.input.fritz_callmonitor import FritzCallmonitorAdapter
from src.config import AdapterConfig
from src.core.event import CallEventType


class _ServerState:
    """Shared state between the test and the fake Fritz!Box server."""

    def __init__(self) -> None:
        self.connections: int = 0
        self.sockets: list[socket.socket] = []
        self.lines_written: list[bytes] = []


def _make_silent_handler(state: _ServerState):
    """Handler that accepts the connection then never sends or FINs.

    Simulates the half-open condition: the server forgets about the
    connection (e.g. Fritz!Box reboot) without sending TCP-FIN. The
    client kernel sees ESTABLISHED, ``readline()`` blocks forever.

    Blocks via ``reader.read()`` (which returns b'' on EOF) so the
    handler naturally exits when the test shuts the adapter down,
    allowing ``server.wait_closed()`` to complete in the test ``finally``.
    """

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        state.connections += 1
        sock = writer.get_extra_info("socket")
        if sock is not None:
            state.sockets.append(sock)
        try:
            await reader.read()
        except Exception:
            return

    return handler


def _make_one_line_handler(line: bytes, state: _ServerState):
    """Handler that sends one line + closes cleanly (normal call flow)."""

    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        state.connections += 1
        sock = writer.get_extra_info("socket")
        if sock is not None:
            state.sockets.append(sock)
        writer.write(line)
        await writer.drain()
        # Server-initiated FIN — graceful close.
        writer.close()
        await writer.wait_closed()

    return handler


async def _start_server(handler):
    """Start a fake server on 127.0.0.1 with auto-assigned port."""
    server = await asyncio.start_server(handler, host="127.0.0.1", port=0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def _make_adapter(port: int, *, readline_timeout: float, reconnect_delay: float = 0.1) -> FritzCallmonitorAdapter:
    config = AdapterConfig(
        type="fritz_callmonitor",
        name="fritz_callmonitor",
        config={
            "host": "127.0.0.1",
            "port": port,
            "readline_timeout": readline_timeout,
            "reconnect_delay": reconnect_delay,
        },
    )
    return FritzCallmonitorAdapter(config)


class TestFritzConnectionReconnect:
    """Half-open socket detection and reconnect."""

    async def test_half_open_connection_triggers_reconnect_after_timeout(self):
        """A silent server (no FIN) must cause the adapter to reconnect."""
        state = _ServerState()
        server, port = await _start_server(_make_silent_handler(state))

        try:
            adapter = _make_adapter(port, readline_timeout=0.5)
            callback = AsyncMock()
            await adapter.start(callback)

            # Wait long enough for at least 2 connect attempts:
            # initial connect + one reconnect after the 0.5s timeout.
            # Without the fix, the adapter is wedged in readline() and
            # `state.connections` stays at 1 — assertion fails.
            await asyncio.sleep(1.5)

            assert state.connections >= 2, (
                f"Expected reconnect after half-open timeout, "
                f"but only {state.connections} connection attempt(s) "
                f"were made — adapter is wedged in readline()."
            )

            await adapter.stop()
        finally:
            server.close()
            await server.wait_closed()

    async def test_socket_has_keepalive_enabled(self):
        """The adapter must enable TCP keepalive on its socket."""
        state = _ServerState()
        server, port = await _start_server(_make_silent_handler(state))

        try:
            adapter = _make_adapter(port, readline_timeout=10.0)
            callback = AsyncMock()
            await adapter.start(callback)

            # Wait for the connection to be established on the server side.
            for _ in range(50):
                if state.sockets:
                    break
                await asyncio.sleep(0.05)

            assert state.sockets, "Server never saw a connection"

            # The adapter sets SO_KEEPALIVE on its own client-side socket
            # (the writer it opened via asyncio.open_connection). Test the
            # socket the adapter actually configures — checking the server's
            # accepted socket would not work because TCP socket options are
            # per-FD, not per-connection.
            client_sock = adapter._writer.get_extra_info("socket")
            assert client_sock is not None, "Adapter must hold a connected socket"
            keepalive = client_sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
            assert keepalive == 1, f"SO_KEEPALIVE not enabled on client socket (got {keepalive})"

            # TCP_KEEPIDLE also set to a sane positive value.
            if hasattr(socket, "TCP_KEEPIDLE"):
                idle = client_sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE)
                assert idle > 0, f"TCP_KEEPIDLE must be > 0, got {idle}"

            await adapter.stop()
        finally:
            server.close()
            await server.wait_closed()

    async def test_default_readline_timeout_is_300_seconds(self):
        """When not in config, ``readline_timeout`` defaults to 300.0."""
        config = AdapterConfig(
            type="fritz_callmonitor",
            name="fritz_callmonitor",
            config={"host": "192.168.178.1", "port": 1012},
        )
        adapter = FritzCallmonitorAdapter(config)
        assert hasattr(adapter, "_readline_timeout")
        assert adapter._readline_timeout == 300.0

    async def test_custom_readline_timeout_from_config(self):
        """When set in config, ``readline_timeout`` is respected."""
        config = AdapterConfig(
            type="fritz_callmonitor",
            name="fritz_callmonitor",
            config={
                "host": "192.168.178.1",
                "port": 1012,
                "readline_timeout": 42.0,
            },
        )
        adapter = FritzCallmonitorAdapter(config)
        assert adapter._readline_timeout == 42.0


class TestFritzConnectionNormalFlow:
    """Normal call event flow still works (regression coverage)."""

    async def test_active_connection_processes_line_and_reconnects_after_close(self):
        """Server sends one RING line then closes — adapter fires callback and reconnects."""
        state = _ServerState()
        ring_line = b"15.03.26 10:15:00;RING;0;0123456789;987654321;SIP0\n"
        server, port = await _start_server(_make_one_line_handler(ring_line, state))

        try:
            adapter = _make_adapter(port, readline_timeout=0.5, reconnect_delay=0.1)
            callback = AsyncMock()
            await adapter.start(callback)

            # Wait for the callback to fire (should be quick).
            for _ in range(100):
                if callback.await_count >= 1:
                    break
                await asyncio.sleep(0.05)

            assert callback.await_count >= 1, "Callback was never invoked"
            event = callback.call_args_list[0][0][0]
            assert event.event_type == CallEventType.RING
            assert event.number == "0123456789"

            # After the server closes, the adapter should reconnect.
            await asyncio.sleep(0.5)
            assert state.connections >= 2, (
                f"Expected reconnect after server close, "
                f"got {state.connections} connection(s)"
            )

            await adapter.stop()
        finally:
            server.close()
            await server.wait_closed()
