"""Product registry — routes data access to the appropriate store.

Each product (air, aqm, etc.) has its own data store implementation.
The registry provides a unified interface for the API layer.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import structlog

from backend.app.api.dependencies import get_field_selector
from backend.app.data.aqm_store import AQMStore

logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_aqm_store() -> AQMStore:
    """Get the singleton AQM data store."""
    return AQMStore()


class ProductDataAccess:
    """Unified data access interface for any product."""

    def __init__(self, product: str):
        self.product = product

    def available_dates(self) -> list[str]:
        if self.product == "aqm":
            return get_aqm_store().available_dates()
        else:
            selector = get_field_selector()
            return selector.get_dates()

    def available_runs(self, date: str) -> list[str]:
        if self.product == "aqm":
            return get_aqm_store().available_runs(date)
        else:
            selector = get_field_selector()
            return selector.get_runs(date)

    def available_variables(self, date: str, run: str) -> list[dict]:
        """Return list of variable metadata dicts."""
        if self.product == "aqm":
            store = get_aqm_store()
            var_names = store.available_variables(date, run)
            from backend.app.config.loader import get_domain_config_safe

            domain_config = get_domain_config_safe("aqm")
            result = []
            for name in var_names:
                info = {
                    "name": name,
                    "shortName": name,
                    "fullName": name,
                    "units": "",
                    "category": "Other",
                }
                if domain_config:
                    var_config = domain_config.get_variable(name)
                    if var_config:
                        info["shortName"] = var_config.shortName
                        info["fullName"] = var_config.fullName
                        info["units"] = var_config.units
                        info["category"] = var_config.category
                        info["rendering"] = {
                            "colormap": var_config.rendering.colormap,
                            "contourInterval": var_config.rendering.contourInterval,
                            "fillLevels": var_config.rendering.fillLevels,
                        }
                result.append(info)
            return result
        else:
            selector = get_field_selector()
            return selector.get_variables(date, run)

    def select_field(
        self, date: str, run: str, variable: str, fhr: int | None = None, level: float | None = None
    ) -> np.ndarray:
        if self.product == "aqm":
            return get_aqm_store().select(date, run, variable, fhr=fhr)
        else:
            selector = get_field_selector()
            return selector.select(date, run, variable, fhr=fhr, level=level)

    def get_latlons(self, date: str, run: str) -> tuple[np.ndarray, np.ndarray]:
        """Get lat/lon arrays. Returns (lats, lons) — either 1D or 2D."""
        if self.product == "aqm":
            return get_aqm_store().get_latlons(date, run)
        else:
            selector = get_field_selector()
            coords = selector.get_coordinates(date, run)
            return coords.lats, coords.lons

    def get_forecast_hours(self, date: str, run: str) -> list[int]:
        if self.product == "aqm":
            return get_aqm_store().get_forecast_hours(date, run)
        else:
            selector = get_field_selector()
            entries = selector.get_forecast_hours(date, run)
            return [e["fhr"] if isinstance(e, dict) else e for e in entries]

    def get_geographic_bounds(self, date: str, run: str) -> dict[str, float] | None:
        """Get geographic bounds for regional grids. None for global."""
        if self.product == "aqm":
            return get_aqm_store().get_geographic_bounds(date, run)
        return None  # Global (GEFS)
