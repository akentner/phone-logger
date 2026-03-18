"""PBX status API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.api.models import (
    DeviceResponse,
    LineStatusResponse,
    MsnResponse,
    PbxStatusResponse,
    TrunkStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pbx", tags=["pbx"])


@router.get("/status", response_model=PbxStatusResponse)
async def get_pbx_status():
    """Get full PBX status: all lines, trunks, MSNs, and devices."""
    from src.main import get_pipeline

    pbx = get_pipeline().pbx
    status = pbx.get_status()

    return PbxStatusResponse(
        lines=[LineStatusResponse(**line) for line in status["lines"]],
        trunks=[TrunkStatusResponse(**trunk) for trunk in status["trunks"]],
        msns=[MsnResponse(**msn) for msn in status["msns"]],
        devices=[DeviceResponse(**dev) for dev in status["devices"]],
    )


@router.get("/lines", response_model=list[LineStatusResponse])
async def get_lines():
    """Get all PBX lines with current status."""
    from src.main import get_pipeline

    pbx = get_pipeline().pbx
    return [
        LineStatusResponse(**state.model_dump())
        for state in pbx.get_line_states()
    ]


@router.get("/lines/{line_id}", response_model=LineStatusResponse)
async def get_line(line_id: int):
    """Get a single PBX line status."""
    from src.main import get_pipeline

    pbx = get_pipeline().pbx
    state = pbx.get_line_state(line_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found")
    return LineStatusResponse(**state.model_dump())


@router.get("/trunks", response_model=list[TrunkStatusResponse])
async def get_trunks():
    """Get all PBX trunks with busy/idle status."""
    from src.main import get_pipeline

    pbx = get_pipeline().pbx
    return [TrunkStatusResponse(**trunk) for trunk in pbx.get_trunk_status()]


@router.get("/msns", response_model=list[MsnResponse])
async def get_msns():
    """Get all configured MSNs with E.164 representation."""
    from src.main import get_pipeline

    pbx = get_pipeline().pbx
    return [MsnResponse(**msn) for msn in pbx.get_msns_e164()]


@router.get("/devices", response_model=list[DeviceResponse])
async def get_devices():
    """Get all configured PBX devices."""
    from src.main import get_pipeline

    pbx = get_pipeline().pbx
    return [
        DeviceResponse(
            id=d.id,
            extension=d.extension,
            name=d.name,
            type=d.type.value,
        )
        for d in pbx.get_devices()
    ]
