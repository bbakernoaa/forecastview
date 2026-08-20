"""Configuration module for domain-specific settings.

Provides YAML-driven variable metadata, categories, and rendering
configuration. The config loader caches parsed configs and provides
a safe fallback when config files are unavailable.
"""

from backend.app.config.loader import (
    DomainConfig,
    ProductInfo,
    RenderingConfig,
    VariableConfig,
    get_domain_config,
    get_domain_config_safe,
)

__all__ = [
    "DomainConfig",
    "ProductInfo",
    "RenderingConfig",
    "VariableConfig",
    "get_domain_config",
    "get_domain_config_safe",
]
