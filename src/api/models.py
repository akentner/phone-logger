"""Pydantic models for the REST API."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NumberType(str, Enum):
    """Type of phone number for contacts."""

    PRIVATE = "private"
    BUSINESS = "business"
    MOBILE = "mobile"


# --- Contact Models ---


class ContactCreate(BaseModel):
    """Request model for creating a contact."""

    number: str = Field(..., min_length=3, description="Phone number")
    name: str = Field(..., min_length=1, description="Contact name")
    number_type: NumberType = Field(
        default=NumberType.PRIVATE, description="Type of phone number"
    )
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    spam_score: Optional[int] = Field(None, ge=1, le=10)


class ContactUpdate(BaseModel):
    """Request model for updating a contact."""

    name: Optional[str] = Field(None, min_length=1)
    number_type: Optional[NumberType] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    spam_score: Optional[int] = Field(None, ge=1, le=10)


class ContactResponse(BaseModel):
    """Response model for a contact."""

    number: str
    name: str
    number_type: NumberType = Field(default=NumberType.PRIVATE)
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    spam_score: Optional[int] = None
    source: str
    last_seen: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# --- Call Log Models ---


class CallLogEntry(BaseModel):
    """Response model for a call log entry (raw event)."""

    id: int
    number: str
    direction: str
    event_type: str
    source: Optional[str] = None
    timestamp: datetime


class CallLogResponse(BaseModel):
    """Paginated call log response."""

    items: list[CallLogEntry]
    next_cursor: Optional[str] = None
    limit: int


# --- Call Status and Aggregated Call Models ---


class CallStatus(str, Enum):
    """Status of an aggregated call."""

    RINGING = "ringing"  # Call is ringing/dialing
    DIALING = "dialing"  # Outbound call being dialed
    ANSWERED = "answered"  # Call connected
    MISSED = "missed"  # Inbound call not answered
    NOT_REACHED = "notReached"  # Outbound call not connected


class CallEntry(BaseModel):
    """Response model for an aggregated call."""

    id: str  # UUIDv7
    connection_id: int
    caller_number: str
    called_number: str
    direction: str  # 'inbound' or 'outbound'
    status: CallStatus
    caller_device: Optional["DeviceInfoResponse"] = None
    called_device: Optional["DeviceInfoResponse"] = None
    msn: Optional[str] = None
    trunk_id: Optional[str] = None
    line_id: Optional[int] = None
    is_internal: bool = False
    started_at: datetime
    connected_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    caller_display: Optional[str] = None
    called_display: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CallListResponse(BaseModel):
    """Paginated calls response."""

    items: list[CallEntry]
    next_cursor: Optional[str] = None
    limit: int


# --- Cache Models ---


class CacheEntry(BaseModel):
    """Response model for a cache entry."""

    number: str
    adapter: str
    result_name: Optional[str] = None
    spam_score: Optional[int] = None
    cached_at: datetime
    ttl_days: int
    expired: bool


class CacheResponse(BaseModel):
    """Cache overview response."""

    items: list[CacheEntry]
    total: int


# --- Resolve Models ---


class ResolveRequest(BaseModel):
    """Request model for manual resolve trigger."""

    number: str = Field(..., min_length=3)
    direction: str = Field(default="inbound")


class ResolveResponse(BaseModel):
    """Response model for resolve endpoint."""

    number: str
    name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    spam_score: Optional[int] = None
    source: str
    cached: bool = False


# --- Config Models ---


class AdapterConfigResponse(BaseModel):
    """Response model for adapter configuration."""

    type: str
    name: str
    enabled: bool
    order: int
    config: dict = Field(default_factory=dict)


class ConfigResponse(BaseModel):
    """Response model for full configuration."""

    input_adapters: list[AdapterConfigResponse]
    resolver_adapters: list[AdapterConfigResponse]
    output_adapters: list[AdapterConfigResponse]


# --- PBX Models ---


class DeviceResponse(BaseModel):
    """Response model for a PBX device."""

    id: str
    extension: str
    name: str
    type: str


class DeviceInfoResponse(BaseModel):
    """Lightweight device info within a line state."""

    id: str
    extension: str
    name: str
    type: str


class LineStatusResponse(BaseModel):
    """Response model for a PBX line state."""

    line_id: int
    status: str
    connection_id: Optional[str] = None
    caller_number: Optional[str] = None
    called_number: Optional[str] = None
    caller_display: Optional[str] = None
    called_display: Optional[str] = None
    direction: Optional[str] = None
    trunk_id: Optional[str] = None
    caller_device: Optional[DeviceInfoResponse] = None
    called_device: Optional[DeviceInfoResponse] = None
    is_internal: bool = False
    since: Optional[datetime] = None


class TrunkStatusResponse(BaseModel):
    """Response model for a PBX trunk."""

    id: str
    type: str
    label: str
    busy: bool


class MsnResponse(BaseModel):
    """Response model for a configured MSN."""

    number: str
    e164: str
    label: str


class PbxStatusResponse(BaseModel):
    """Full PBX status snapshot."""

    lines: list[LineStatusResponse]
    trunks: list[TrunkStatusResponse]
    msns: list[MsnResponse]
    devices: list[DeviceResponse]
