"""Configuration management for phone-logger."""

import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = "/addons_config/phone-logger"
DEFAULT_OPTIONS_PATH = "/data/options.json"


class AdapterConfig(BaseModel):
    """Configuration for a single adapter."""

    name: str
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class FritzConfig(BaseModel):
    """Fritz!Box connection settings."""

    host: str = "192.168.178.1"
    port: int = 1012


class WebhookConfig(BaseModel):
    """Home Assistant webhook settings."""

    url: str = ""
    token: str = ""
    events: list[str] = Field(default_factory=lambda: ["ring", "call", "connect", "disconnect"])


class MqttConfig(BaseModel):
    """MQTT connection settings."""

    broker: str = "homeassistant"
    port: int = 1883
    username: str = ""
    password: str = ""
    topic_prefix: str = "phone-logger"


class AppConfig(BaseModel):
    """Main application configuration."""

    data_path: str = DEFAULT_DATA_PATH
    ingress_port: int = 8080
    log_level: str = "INFO"

    fritz: FritzConfig = Field(default_factory=FritzConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)

    input_adapters: list[AdapterConfig] = Field(default_factory=lambda: [
        AdapterConfig(name="fritz", enabled=True),
        AdapterConfig(name="rest", enabled=True),
        AdapterConfig(name="mqtt", enabled=False),
    ])

    resolver_adapters: list[AdapterConfig] = Field(default_factory=lambda: [
        AdapterConfig(name="json_file", enabled=True, config={"path": "contacts.json"}),
        AdapterConfig(name="sqlite", enabled=True),
        AdapterConfig(name="tellows", enabled=True, config={"ttl_days": 7}),
        AdapterConfig(name="dastelefon", enabled=True, config={"ttl_days": 30}),
        AdapterConfig(name="klartelbuch", enabled=False, config={"ttl_days": 30}),
    ])

    output_adapters: list[AdapterConfig] = Field(default_factory=lambda: [
        AdapterConfig(name="call_log", enabled=True),
        AdapterConfig(name="ha_webhook", enabled=True),
        AdapterConfig(name="mqtt", enabled=False),
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
    """Load config from JSON file (HA addon options)."""
    import json

    logger.info("Loading configuration from %s", path)
    with open(path) as f:
        data = json.load(f)
    return AppConfig(**data)
