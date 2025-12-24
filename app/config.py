"""Application configuration management."""

import os
from typing import Dict, Any
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field, validator
import yaml


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="SLA Tracking Service", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Database settings
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/sla_service",
        env="DATABASE_URL"
    )
    
    # SLA Configuration
    sla_config_path: str = Field(
        default="sla_config.yaml",
        env="SLA_CONFIG_PATH"
    )
    
    # Slack webhook
    slack_webhook_url: str = Field(default="", env="SLACK_WEBHOOK_URL")
    
    # Scheduler settings
    scheduler_interval: int = Field(default=60, env="SCHEDULER_INTERVAL")  # seconds
    
    # WebSocket settings
    ws_max_connections: int = Field(default=100, env="WS_MAX_CONNECTIONS")
    
    # Alert thresholds
    warning_threshold: float = Field(default=0.15, env="WARNING_THRESHOLD")
    critical_threshold: float = Field(default=0.05, env="CRITICAL_THRESHOLD")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    structured_logging: bool = Field(default=True, env="STRUCTURED_LOGGING")
    
    # CORS settings
    cors_origins: list[str] = Field(default=["*"], env="CORS_ORIGINS")

    HUGGINGFACE_API_KEY :str = Field(default="", env="HUGGINGFACE_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class SLAConfig:
    """SLA configuration manager with hot-reload support."""
    
    def __init__(self, config_path: str = "sla_config.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._callbacks = []
        self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            self._notify_callbacks()
            return self._config
        except Exception as e:
            # Return default config if file doesn't exist or is invalid
            self._config = self._get_default_config()
            return self._config
    
    def get_sla_target(self, sla_type: str, priority: str, customer_tier: str) -> int:
        """Get SLA target time in minutes."""
        print(sla_type, priority, customer_tier)

        return (
            self._config
            .get("sla_targets", {})
            .get(customer_tier, {})
            .get(priority, {})
            .get(sla_type, 1440)
        )
        
    
    def get_alert_threshold(self, level: str) -> float:
        """Get alert threshold percentage."""
        return self._config.get('alert_thresholds', {}).get(level, 0.15)
    
    def get_escalation_levels(self) -> Dict[int, str]:
        """Get escalation level mappings."""
        return self._config.get('escalation_levels', {})
    
    def get_webhook_config(self, service: str) -> Dict[str, Any]:
        """Get webhook configuration."""
        webhooks = self._config.get('webhooks', {})
        if service == 'slack':
            # Replace environment variable placeholder
            slack_config = webhooks.get('slack', {})
            url = slack_config.get('url', '')
            if url.startswith('${') and url.endswith('}'):
                env_var = url[2:-1]
                slack_config['url'] = os.getenv(env_var, '')
            return slack_config
        return webhooks.get(service, {})
    
    def subscribe_to_changes(self, callback):
        """Subscribe to configuration changes."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify all subscribers of configuration changes."""
        for callback in self._callbacks:
            try:
                callback(self._config)
            except Exception as e:
                # Log error but don't fail
                pass
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'sla_targets': {
                'response': {'P0': {'enterprise': 15}},
                'resolution': {'P0': {'enterprise': 240}}
            },
            'alert_thresholds': {'warning': 0.15, 'critical': 0.05},
            'escalation_levels': {0: 'No escalation'},
            'webhooks': {'slack': {'url': ''}}
        }


# Global settings instance
settings = Settings()

# Global SLA config instance
sla_config = SLAConfig(settings.sla_config_path)
