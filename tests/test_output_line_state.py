"""Tests for LineState serialization in webhook and MQTT output adapters."""

import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.output.webhook import WebhookOutputAdapter, _serialize_line_state
from src.adapters.output.mqtt_pub import (
    MqttPublisherOutputAdapter,
    _serialize_line_state as mqtt_serialize_line_state,
)
from src.config import AdapterConfig
from src.core.event import (
    CallDirection,
    CallEvent,
    CallEventType,
    DeviceInfo,
    ResolveResult,
)
from src.core.pbx import LineState, LineStatus


# --- Fixtures ---


def _make_event(**overrides) -> CallEvent:
    defaults = {
        "number": "+491234567890",
        "direction": CallDirection.INBOUND,
        "event_type": CallEventType.RING,
        "source": "test",
        "connection_id": "1",
        "caller_number": "+491234567890",
        "called_number": "+496181123456",
        "line_id": 0,
    }
    defaults.update(overrides)
    return CallEvent(**defaults)


def _make_line_state(**overrides) -> LineState:
    defaults = {
        "line_id": 0,
        "status": LineStatus.RING,
        "connection_id": "1",
        "caller_number": "+491234567890",
        "called_number": "+496181123456",
        "direction": CallDirection.INBOUND,
        "trunk_id": "SIP0",
        "is_internal": False,
        "since": datetime(2026, 3, 19, 10, 0, 0),
    }
    defaults.update(overrides)
    return LineState(**defaults)


def _make_resolve_result() -> ResolveResult:
    return ResolveResult(name="Test User", number="+491234567890", source="test")


# --- _serialize_line_state ---


class TestSerializeLineState:
    def test_none_returns_none(self):
        assert _serialize_line_state(None) is None

    def test_basic_fields(self):
        ls = _make_line_state()
        result = _serialize_line_state(ls)

        assert result["line_id"] == 0
        assert result["status"] == "ring"
        assert result["connection_id"] == "1"
        assert result["caller_number"] == "+491234567890"
        assert result["called_number"] == "+496181123456"
        assert result["direction"] == "inbound"
        assert result["trunk_id"] == "SIP0"
        assert result["is_internal"] is False
        assert result["since"] == "2026-03-19T10:00:00"

    def test_device_serialized(self):
        device = DeviceInfo(id="1", extension="10", name="Telefon Flur", type="dect")
        ls = _make_line_state(device=device)
        result = _serialize_line_state(ls)

        assert result["device"] == {"id": "1", "name": "Telefon Flur", "type": "dect"}

    def test_device_none(self):
        ls = _make_line_state(device=None)
        result = _serialize_line_state(ls)
        assert result["device"] is None

    def test_direction_none(self):
        ls = _make_line_state(direction=None)
        result = _serialize_line_state(ls)
        assert result["direction"] is None

    def test_since_none(self):
        ls = _make_line_state(since=None)
        result = _serialize_line_state(ls)
        assert result["since"] is None

    def test_mqtt_serializer_same_output(self):
        """Both webhook and MQTT use identical serialization logic."""
        ls = _make_line_state()
        assert _serialize_line_state(ls) == mqtt_serialize_line_state(ls)


# --- Webhook: line_state in payload ---


class TestWebhookLineState:
    @pytest.mark.asyncio
    async def test_payload_includes_line_state(self):
        """Webhook payload should contain full line_state object."""
        config = AdapterConfig(
            type="webhook",
            name="test",
            enabled=True,
            config={
                "url": "https://example.com/hook",
                "token": "test-token",
            },
        )
        adapter = WebhookOutputAdapter(config)

        event = _make_event()
        result = _make_resolve_result()
        ls = _make_line_state()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        adapter._session = mock_session

        await adapter.handle(event, result, line_state=ls)

        # Extract the payload passed to session.post
        call_args = mock_session.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")

        assert "line_state" in payload
        assert payload["line_state"]["status"] == "ring"
        assert payload["line_state"]["line_id"] == 0
        assert payload["line_state"]["caller_number"] == "+491234567890"
        assert payload["line_state"]["is_internal"] is False

    @pytest.mark.asyncio
    async def test_payload_line_state_none_when_absent(self):
        """Webhook payload should have line_state: null when not provided."""
        config = AdapterConfig(
            type="webhook",
            name="test",
            enabled=True,
            config={
                "url": "https://example.com/hook",
            },
        )
        adapter = WebhookOutputAdapter(config)
        event = _make_event()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)
        adapter._session = mock_session

        await adapter.handle(event, None, line_state=None)

        call_args = mock_session.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["line_state"] is None


# --- MQTT: line_state in event payload + dedicated topic ---


def _fake_aiomqtt_module(fake_client_cls):
    """Create a mock aiomqtt module whose Client() returns a fake_client_cls instance."""
    mock_module = MagicMock()
    mock_module.Client = MagicMock(return_value=fake_client_cls())
    return mock_module


class TestMqttLineState:
    def _make_adapter(self) -> MqttPublisherOutputAdapter:
        config = AdapterConfig(
            type="mqtt",
            name="test",
            enabled=True,
            config={
                "broker": "localhost",
                "port": 1883,
                "topic_prefix": "phone-logger",
            },
        )
        return MqttPublisherOutputAdapter(config)

    @pytest.mark.asyncio
    async def test_event_payload_includes_line_state(self):
        """MQTT event payload should contain full line_state object."""
        adapter = self._make_adapter()
        event = _make_event()
        ls = _make_line_state()

        published = {}

        class FakeClient:
            async def publish(self, topic, message, **kwargs):
                published[topic] = message

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.dict(sys.modules, {"aiomqtt": _fake_aiomqtt_module(FakeClient)}):
            await adapter.handle(event, None, line_state=ls)

        import json

        event_payload = json.loads(published["phone-logger/event"])
        assert "line_state" in event_payload
        assert event_payload["line_state"]["status"] == "ring"
        assert event_payload["line_state"]["line_id"] == 0

    @pytest.mark.asyncio
    async def test_line_state_topic_published_on_change(self):
        """Dedicated line state topic should be published when status changes."""
        adapter = self._make_adapter()
        event = _make_event()
        ls = _make_line_state(status=LineStatus.RING)

        published = {}

        class FakeClient:
            async def publish(self, topic, message, **kwargs):
                published[topic] = (message, kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.dict(sys.modules, {"aiomqtt": _fake_aiomqtt_module(FakeClient)}):
            await adapter.handle(event, None, line_state=ls)

        assert "phone-logger/line/0/state" in published
        import json

        state_msg, state_kwargs = published["phone-logger/line/0/state"]
        state_data = json.loads(state_msg)
        assert state_data["status"] == "ring"
        assert state_kwargs["retain"] is True

    @pytest.mark.asyncio
    async def test_line_state_topic_not_published_when_unchanged(self):
        """Dedicated line state topic should NOT be published if status is same."""
        adapter = self._make_adapter()
        event = _make_event()
        ls = _make_line_state(status=LineStatus.RING)

        class FakeClient:
            async def publish(self, topic, message, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.dict(sys.modules, {"aiomqtt": _fake_aiomqtt_module(FakeClient)}):
            # First call: status changes from <none> to ring
            await adapter.handle(event, None, line_state=ls)

        # Second call with same status
        published_topics = []

        class TrackingClient:
            async def publish(self, topic, message, **kwargs):
                published_topics.append(topic)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.dict(sys.modules, {"aiomqtt": _fake_aiomqtt_module(TrackingClient)}):
            await adapter.handle(event, None, line_state=ls)

        # Event topics published, but NOT the line state topic
        assert "phone-logger/event" in published_topics
        assert "phone-logger/line/0/state" not in published_topics

    @pytest.mark.asyncio
    async def test_line_state_topic_published_on_transition(self):
        """Line state topic should be published when status transitions."""
        adapter = self._make_adapter()
        event_ring = _make_event(event_type=CallEventType.RING)
        event_connect = _make_event(event_type=CallEventType.CONNECT)
        ls_ring = _make_line_state(status=LineStatus.RING)
        ls_talking = _make_line_state(status=LineStatus.TALKING)

        published_topics = []

        class TrackingClient:
            async def publish(self, topic, message, **kwargs):
                published_topics.append(topic)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.dict(sys.modules, {"aiomqtt": _fake_aiomqtt_module(TrackingClient)}):
            # RING -> state published (new)
            await adapter.handle(event_ring, None, line_state=ls_ring)
            assert "phone-logger/line/0/state" in published_topics

            published_topics.clear()

            # CONNECT -> state published (ring -> talking)
            await adapter.handle(event_connect, None, line_state=ls_talking)
            assert "phone-logger/line/0/state" in published_topics

    @pytest.mark.asyncio
    async def test_no_line_state_no_crash(self):
        """Handle should work without line_state (no crash, no state topic)."""
        adapter = self._make_adapter()
        event = _make_event()

        published_topics = []

        class TrackingClient:
            async def publish(self, topic, message, **kwargs):
                published_topics.append(topic)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.dict(sys.modules, {"aiomqtt": _fake_aiomqtt_module(TrackingClient)}):
            await adapter.handle(event, None, line_state=None)

        assert "phone-logger/event" in published_topics
        assert not any("line" in t for t in published_topics)
