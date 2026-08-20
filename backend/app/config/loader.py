"""Domain configuration loader.

Loads YAML domain configuration files and parses them into Pydantic
models. Provides a cached accessor for domain configs keyed by product ID.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# Default location for domain config files relative to project root.
_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "domains"


# --------------------------------------------------------------------------
# Pydantic models
# --------------------------------------------------------------------------


class RenderingConfig(BaseModel):
    """Rendering hints for a variable (colormaps, contour levels)."""

    colormap: str = Field("rainbow", description="Matplotlib colormap name")
    contourInterval: float = Field(
        0.1, description="Default contour line interval"
    )
    fillLevels: list[float] = Field(
        default_factory=list,
        description="Discrete fill level boundaries",
    )


class VariableConfig(BaseModel):
    """Configuration for a single forecast variable."""

    shortName: str = Field(..., description="Short display name")
    fullName: str = Field(..., description="Full descriptive name")
    units: str = Field("", description="Variable units")
    category: str = Field("Other", description="Grouping category")
    rendering: RenderingConfig = Field(
        default_factory=RenderingConfig,
        description="Rendering configuration",
    )


class ProductInfo(BaseModel):
    """Product-level metadata."""

    name: str = Field(..., description="Human-readable product name")
    id: str = Field(..., description="Product identifier")


class DomainConfig(BaseModel):
    """Complete domain configuration loaded from a YAML file."""

    product: ProductInfo
    categories: list[str] = Field(
        default_factory=list,
        description="Ordered list of variable categories",
    )
    variables: dict[str, VariableConfig] = Field(
        default_factory=dict,
        description="Variable configs keyed by variable name",
    )

    def get_variable(self, name: str) -> VariableConfig | None:
        """Look up a variable config by name.

        Parameters
        ----------
        name : str
            The variable name (xarray/GRIB2 key).

        Returns
        -------
        VariableConfig | None
            The variable config if found, else None.
        """
        return self.variables.get(name)

    def get_variables_by_category(self) -> dict[str, list[VariableConfig]]:
        """Return variables grouped by their category.

        Returns
        -------
        dict[str, list[VariableConfig]]
            Mapping from category name to list of VariableConfig objects,
            ordered by the categories list defined in the config.
        """
        grouped: dict[str, list[VariableConfig]] = {}
        for var in self.variables.values():
            grouped.setdefault(var.category, []).append(var)

        # Order by the explicit categories list if provided
        if self.categories:
            ordered: dict[str, list[VariableConfig]] = {}
            for cat in self.categories:
                if cat in grouped:
                    ordered[cat] = grouped[cat]
            # Include any categories not in the explicit list
            for cat, vars_ in grouped.items():
                if cat not in ordered:
                    ordered[cat] = vars_
            return ordered

        return grouped


# --------------------------------------------------------------------------
# Loader functions
# --------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file.

    Parameters
    ----------
    path : Path
        Path to the YAML file.

    Returns
    -------
    dict
        Parsed YAML content.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    yaml.YAMLError
        If the YAML is malformed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Domain config not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML dict at top level, got {type(data)}")

    return data


def _parse_domain_config(data: dict[str, Any]) -> DomainConfig:
    """Parse raw YAML dict into a validated DomainConfig.

    Parameters
    ----------
    data : dict
        Raw parsed YAML data.

    Returns
    -------
    DomainConfig
        Validated domain configuration.
    """
    return DomainConfig(**data)


@lru_cache(maxsize=8)
def get_domain_config(product: str) -> DomainConfig:
    """Load and return the domain configuration for a product.

    Configurations are cached after first load. The cache key is the
    product identifier (e.g. "air").

    Parameters
    ----------
    product : str
        Product identifier matching a YAML filename in config/domains/
        (e.g. "air" → config/domains/air.yaml).

    Returns
    -------
    DomainConfig
        The parsed and validated domain configuration.

    Raises
    ------
    FileNotFoundError
        If no config file exists for the given product.
    ValueError
        If the config file is malformed.
    """
    config_path = _CONFIG_DIR / f"{product}.yaml"
    logger.info(
        "config.loader.loading",
        product=product,
        path=str(config_path),
    )

    data = _load_yaml(config_path)
    config = _parse_domain_config(data)

    logger.info(
        "config.loader.loaded",
        product=product,
        variables_count=len(config.variables),
        categories=config.categories,
    )
    return config


def get_domain_config_safe(product: str) -> DomainConfig | None:
    """Load domain config, returning None if unavailable.

    This is a safe wrapper around get_domain_config that catches
    FileNotFoundError and returns None, allowing callers to gracefully
    fall back to dataset-derived metadata.

    Parameters
    ----------
    product : str
        Product identifier.

    Returns
    -------
    DomainConfig | None
        The domain config if available, else None.
    """
    try:
        return get_domain_config(product)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        logger.warning(
            "config.loader.fallback",
            product=product,
            error=str(exc),
        )
        return None
