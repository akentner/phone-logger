"""Configuration management for phone-logger."""

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = "/addons_config/phone-logger"
DEFAULT_OPTIONS_PATH = "/data/options.json"


class AdapterConfig(BaseModel):
    """Configuration for a single adapter."""

    type: str  # Discriminator: "call_log", "webhook", "mqtt" (output); "fritz", "rest", "mqtt" (input); etc.
    name: str  # Label for the adapter instance (for logs, API, UI)
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class PhoneConfig(BaseModel):
    """Phone number normalization settings."""

    country_code: str = "49"
    """Default country code without leading +/00 (e.g. '49' for Germany)."""

    local_area_code: str = ""
    """Local area code without leading 0 (e.g. '6181' for Hanau).
    Required to expand short local numbers that arrive without area code."""


# --- PBX Configuration Models ---


class TrunkType(str, Enum):
    """Connection type of a PBX trunk."""

    SIP = "sip"
    ISDN = "isdn"
    ANALOG = "analog"


class DeviceType(str, Enum):
    """Type of a PBX device."""

    DECT = "dect"
    VOIP = "voip"
    ANALOG = "analog"
    FAX = "fax"
    VOICEBOX = "voicebox"


class LineConfig(BaseModel):
    """Configuration for a PBX line (concurrent call slot)."""

    id: int


class TrunkConfig(BaseModel):
    """Configuration for a PBX trunk (external connection)."""

    id: str  # "SIP0", "ISDN0", etc.
    type: TrunkType = TrunkType.SIP
    label: str = ""


class MsnConfig(BaseModel):
    """Configuration for an MSN (subscriber number without area code)."""

    number: str  # e.g. "990133" — resolved to E.164 via PhoneConfig at runtime
    label: str = ""


class DeviceConfig(BaseModel):
    """Configuration for a PBX device (phone, fax, etc.)."""

    id: str
    extension: str  # internal extension number
    name: str
    type: DeviceType = DeviceType.VOIP


class PbxConfig(BaseModel):
    """PBX infrastructure configuration."""

    lines: list[LineConfig] = Field(default_factory=list)
    trunks: list[TrunkConfig] = Field(default_factory=list)
    msns: list[MsnConfig] = Field(default_factory=list)
    devices: list[DeviceConfig] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Main application configuration."""

    data_path: str = DEFAULT_DATA_PATH
    ingress_port: int = 8080
    log_level: str = "INFO"
    timezone: str = "Europe/Berlin"

    phone: PhoneConfig = Field(default_factory=PhoneConfig)
    pbx: PbxConfig = Field(default_factory=PbxConfig)

    input_adapters: list[AdapterConfig] = Field(default_factory=lambda: [
        AdapterConfig(type="fritz", name="fritz", enabled=True, config={"host": "192.168.178.1", "port": 1012}),
        AdapterConfig(type="rest", name="rest", enabled=True),
        AdapterConfig(type="mqtt", name="mqtt", enabled=False, config={"broker": "homeassistant", "port": 1883, "topic_prefix": "phone-logger"}),
    ])

    resolver_adapters: list[AdapterConfig] = Field(default_factory=lambda: [
        AdapterConfig(type="json_file", name="json_file", enabled=True, config={"path": "contacts.json"}),
        AdapterConfig(type="sqlite", name="sqlite", enabled=True),
        AdapterConfig(type="tellows", name="tellows", enabled=True, config={"ttl_days": 7}),
        AdapterConfig(type="dastelefon", name="dastelefon", enabled=True, config={"ttl_days": 30}),
        AdapterConfig(type="klartelbuch", name="klartelbuch", enabled=False, config={"ttl_days": 30}),
    ])

    output_adapters: list[AdapterConfig] = Field(default_factory=lambda: [
        AdapterConfig(type="call_log", name="call_log", enabled=True),
        AdapterConfig(type="webhook", name="webhook", enabled=True, config={"url": "", "token": "", "events": ["ring", "call", "connect", "disconnect"]}),
        AdapterConfig(type="mqtt", name="mqtt", enabled=False, config={"broker": "homeassistant", "topic_prefix": "phone-logger"}),
    ])

    @property
    def db_path(self) -> str:
        """Path to SQLite database."""
        return str(Path(self.data_path) / "phone-logger.db")

    @property
    def contacts_json_path(self) -> str:
        """Path to contacts JSON file."""
        json_config = next(
            (a for a in self.resolver_adapters if a.name == "json_file"), None
        )
        filename = json_config.config.get("path", "contacts.json") if json_config else "contacts.json"
        return str(Path(self.data_path) / filename)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file or HA options."""
    # Try explicit config path
    if config_path and Path(config_path).exists():
        return _load_from_yaml(config_path)

    # Try HA addon options.json
    if Path(DEFAULT_OPTIONS_PATH).exists():
        return _load_from_json(DEFAULT_OPTIONS_PATH)

    # Try local config.yaml for development
    local_config = Path("config.yaml")
    if local_config.exists():
        return _load_from_yaml(str(local_config))

    logger.warning("No configuration found, using defaults")
    return AppConfig()


def _load_from_yaml(path: str) -> AppConfig:
    """Load config from YAML file."""
    logger.info("Loading configuration from %s", path)
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return AppConfig(**data)


def _load_from_json(path: str) -> AppConfig:
    """Load config from JSON file (HA addon options).
    
    HA options supports a separate 'webhooks' list. Bridge it into
    the output_adapters list as independent webhook instances.
    """
    import json

    logger.info("Loading configuration from %s", path)
    with open(path) as f:
        data = json.load(f)
    
    # Bridge: convert HA-format "webhooks" list → output_adapter entries
    webhooks = data.pop("webhooks", [])
    if webhooks:
        output_adapters = data.setdefault("output_adapters", [])
        for i, wh in enumerate(webhooks):
            if wh.get("url"):  # Only add webhook if URL is configured
                webhook_name = wh.get("name") or f"webhook-{i+1}"
                output_adapters.append({
                    "type": "webhook",
                    "name": webhook_name,
                    "enabled": True,
                    "config": {
                        "url": wh.get("url"),
                        "token": wh.get("token", ""),
                        "events": wh.get("events", ["ring", "call", "connect", "disconnect"]),
                    }
                })
        logger.info("Bridged %d webhook(s) from HA options into output_adapters", len([w for w in webhooks if w.get("url")]))
    
    return AppConfig(**data)
