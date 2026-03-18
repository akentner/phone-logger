"""Contacts CRUD API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.models import ContactCreate, ContactResponse, ContactUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactResponse])
async def list_contacts():
    """Get all contacts from the SQLite database."""
    from src.main import get_db

    db = get_db()
    contacts = await db.get_contacts()
    return contacts


@router.get("/{number}", response_model=ContactResponse)
async def get_contact(number: str):
    """Get a single contact by phone number."""
    from src.main import get_db, get_pipeline

    db = get_db()
    pipeline = get_pipeline()

    # Normalize the number for lookup
    normalized = pipeline.normalize(number)

    contact = await db.get_contact(normalized)
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact '{number}' not found")
    return contact


@router.post("", response_model=ContactResponse, status_code=201)
async def create_contact(data: ContactCreate):
    """Create a new contact."""
    from src.main import get_db, get_pipeline

    db = get_db()
    pipeline = get_pipeline()

    # Normalize the number before storing
    normalized = pipeline.normalize(data.number)

    # Check if contact already exists
    existing = await db.get_contact(normalized)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Contact with number '{data.number}' already exists",
        )

    contact = await db.create_contact(
        number=normalized,
        name=data.name,
        number_type=data.number_type.value,
        tags=data.tags,
        notes=data.notes,
        spam_score=data.spam_score,
    )
    return contact


@router.put("/{number}", response_model=ContactResponse)
async def update_contact(number: str, data: ContactUpdate):
    """Update an existing contact."""
    from src.main import get_db, get_pipeline

    db = get_db()
    pipeline = get_pipeline()

    # Normalize the number for lookup
    normalized = pipeline.normalize(number)

    contact = await db.update_contact(
        normalized,
        name=data.name,
        number_type=data.number_type.value if data.number_type else None,
        tags=data.tags,
        notes=data.notes,
        spam_score=data.spam_score,
    )
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact '{number}' not found")
    return contact


@router.delete("/{number}", status_code=204)
async def delete_contact(number: str):
    """Delete a contact."""
    from src.main import get_db, get_pipeline

    db = get_db()
    pipeline = get_pipeline()

    # Normalize the number for lookup
    normalized = pipeline.normalize(number)

    deleted = await db.delete_contact(normalized)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Contact '{number}' not found")
