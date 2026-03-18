"""Configuration API routes."""

import logging

from fastapi import APIRouter

from src.api.models import AdapterConfigResponse, ConfigResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config():
    """Get the current adapter configuration."""
    from src.main import get_config

    config = get_config()

    return ConfigResponse(
        input_adapters=[
            AdapterConfigResponse(
                type=a.type, name=a.name, enabled=a.enabled, order=i, config=a.config
            )
            for i, a in enumerate(config.input_adapters)
        ],
        resolver_adapters=[
            AdapterConfigResponse(
                type=a.type, name=a.name, enabled=a.enabled, order=i, config=a.config
            )
            for i, a in enumerate(config.resolver_adapters)
        ],
        output_adapters=[
            AdapterConfigResponse(
                type=a.type, name=a.name, enabled=a.enabled, order=i, config=a.config
            )
            for i, a in enumerate(config.output_adapters)
        ],
    )
