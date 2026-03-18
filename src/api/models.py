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
    number_type: NumberType = Field(default=NumberType.PRIVATE, description="Type of phone number")
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
    """Response model for a call log entry."""

    id: int
    number: str
    direction: str
    event_type: str
    resolved_name: Optional[str] = None
    source: Optional[str] = None
    timestamp: datetime


class CallLogResponse(BaseModel):
    """Paginated call log response."""

    items: list[CallLogEntry]
    total: int
    page: int
    page_size: int


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

    name: str
    enabled: bool
    order: int
    config: dict = Field(default_factory=dict)


class ConfigResponse(BaseModel):
    """Response model for full configuration."""

    input_adapters: list[AdapterConfigResponse]
    resolver_adapters: list[AdapterConfigResponse]
    output_adapters: list[AdapterConfigResponse]
