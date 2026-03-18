"""Core event models for the phone-logger pipeline."""

from datetime import datetime
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


class CallEvent(BaseModel):
    """Normalized call event from any input adapter."""

    number: str = Field(..., description="Phone number (normalized)")
    direction: CallDirection
    event_type: CallEventType
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(default="unknown", description="Input adapter that generated the event")
    connection_id: Optional[str] = Field(None, description="Fritz!Box connection ID for correlating events")
    extension: Optional[str] = Field(None, description="Internal extension number")
    raw_number: Optional[str] = Field(None, description="Original number before normalization")


class ResolveResult(BaseModel):
    """Result of resolving a phone number."""

    number: str
    name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    spam_score: Optional[int] = Field(None, ge=1, le=10)
    source: str = Field(..., description="Adapter that resolved the number")
    cached: bool = Field(default=False, description="Whether the result came from cache")

    @property
    def is_spam(self) -> bool:
        """Consider numbers with spam_score >= 7 as spam."""
        return self.spam_score is not None and self.spam_score >= 7


class PipelineResult(BaseModel):
    """Complete result of processing a call event through the pipeline."""

    event: CallEvent
    resolve_result: Optional[ResolveResult] = None
    resolved: bool = Field(default=False)
    processed_at: datetime = Field(default_factory=datetime.now)
