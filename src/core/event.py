"""Core event models for the phone-logger pipeline."""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CallDirection(str, Enum):
    """Direction of a phone call."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallEventType(str, Enum):
    """Type of call event from Fritz!Box Callmonitor."""

    RING = "ring"  # Inbound call ringing
    CALL = "call"  # Outbound call initiated
    CONNECT = "connect"  # Call connected
    DISCONNECT = "disconnect"  # Call ended


class NumberType(str, Enum):
    """Type of phone number for contacts."""

    PRIVATE = "private"
    BUSINESS = "business"
    MOBILE = "mobile"


class DeviceInfo(BaseModel):
    """Lightweight device information attached to call events."""

    id: str
    extension: str
    name: str
    type: str  # DeviceType value as string


class CallEvent(BaseModel):
    """Normalized call event from any input adapter."""

    number: str = Field(
        ..., description="Phone number of the remote party (normalized E.164)"
    )
    direction: CallDirection
    event_type: CallEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(
        default="unknown", description="Input adapter that generated the event"
    )
    connection_id: Optional[str] = Field(
        None, description="Fritz!Box connection ID for correlating events"
    )
    extension: Optional[str] = Field(None, description="Internal extension number")
    raw_number: Optional[str] = Field(
        None, description="Original number before normalization"
    )

    # Semantic direction fields
    caller_number: Optional[str] = Field(None, description="E.164 number of the caller")
    called_number: Optional[str] = Field(
        None, description="E.164 number of the called party"
    )

    # Raw input data (set by input adapters before pipeline processing)
    raw_input: Optional[str] = Field(
        None, description="Adapter-specific raw input (TCP line, JSON payload, etc.)"
    )

    # PBX enrichment fields (populated by PbxStateManager)
    line_id: Optional[int] = Field(
        None, description="PBX line index (from connection_id)"
    )
    trunk_id: Optional[str] = Field(
        None, description="Trunk ID as reported by input adapter (e.g. 'SIP0')"
    )
    caller_device: Optional[DeviceInfo] = Field(
        None,
        description="PBX device of the calling party (None if no match or unknown)",
    )
    called_device: Optional[DeviceInfo] = Field(
        None, description="PBX device of the called party (None if no match or unknown)"
    )


class ResolveResult(BaseModel):
    """Result of resolving a phone number."""

    number: str
    name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    spam_score: Optional[int] = Field(None, ge=1, le=10)
    source: str = Field(..., description="Adapter that resolved the number")
    cached: bool = Field(
        default=False, description="Whether the result came from cache"
    )

    @property
    def is_spam(self) -> bool:
        """Consider numbers with spam_score >= 7 as spam."""
        return self.spam_score is not None and self.spam_score >= 7


class PipelineResult(BaseModel):
    """Complete result of processing a call event through the pipeline."""

    event: CallEvent
    resolve_result: Optional[ResolveResult] = None
    resolved: bool = Field(default=False)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
