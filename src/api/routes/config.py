"""Configuration API routes."""

import logging

from fastapi import APIRouter

from src.api.models import AdapterConfigResponse, ConfigResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

SECRET_KEYS = {"token", "password", "secret", "api_key", "username"}


def _redact_config(config: dict) -> dict:
    """Return a copy of the adapter config with sensitive values masked."""
    return {
        k: "***" if k in SECRET_KEYS and v else v
        for k, v in config.items()
    }


@router.get("", response_model=ConfigResponse)
async def get_config():
    """Get the current adapter configuration (secrets are redacted)."""
    from src.main import get_config

    config = get_config()

    return ConfigResponse(
        input_adapters=[
            AdapterConfigResponse(
                type=a.type, name=a.name, enabled=a.enabled, order=i,
                config=_redact_config(a.config),
            )
            for i, a in enumerate(config.input_adapters)
        ],
        resolver_adapters=[
            AdapterConfigResponse(
                type=a.type, name=a.name, enabled=a.enabled, order=i,
                config=_redact_config(a.config),
            )
            for i, a in enumerate(config.resolver_adapters)
        ],
        output_adapters=[
            AdapterConfigResponse(
                type=a.type, name=a.name, enabled=a.enabled, order=i,
                config=_redact_config(a.config),
            )
            for i, a in enumerate(config.output_adapters)
        ],
    )
