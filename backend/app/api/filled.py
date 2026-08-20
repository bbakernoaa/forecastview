"""Filled contour API endpoint for GeoJSON polygon generation.

Provides a GeoJSON FeatureCollection of filled contour polygons for a
specified forecast field. Filled contours are generated on the native
scientific grid and transformed to geographic (lon/lat) coordinates
for display on MapLibre.

Fill levels are sourced from the domain configuration YAML per variable.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import structlog
from cachetools import LRUCache
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse

from backend.app.api.dependencies import get_field_selector
from backend.app.config.loader import get_domain_config_safe
from backend.app.contours.generator import generate_filled_contours
from backend.app.contours.geojson import filled_contours_to_geojson, shift_grid_to_minus180
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["filled"])


# --------------------------------------------------------------------------
# Filled contour geometry cache
# --------------------------------------------------------------------------

# LRU cache keyed on (date, run, variable, level, fhr)
_filled_cache: LRUCache = LRUCache(maxsize=64)


def _cache_key(
    date: str,
    run: str,
    variable: str,
    level: float | None,
    fhr: int,
) -> tuple:
    """Build a hashable cache key for a filled contour request."""
    return (date, run, variable, level, fhr)


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


@router.get("/filled")
async def get_filled(
    product: str = Query(..., description="Product identifier (e.g. 'air')"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
    variable: str = Query(..., description="Variable name"),
    fhr: int = Query(..., description="Forecast hour"),
    level: float | None = Query(
        None, description="Vertical level value (for multi-level variables)"
    ),
) -> ORJSONResponse:
    """Return GeoJSON filled contour polygons for a forecast field.

    Extracts the requested field, generates filled contour polygons on
    the native grid using contourpy, transforms vertices to geographic
    (lon/lat), and returns a GeoJSON FeatureCollection with fill band
    metadata.

    The response includes timing instrumentation in the metadata and
    Cache-Control headers for immutable forecast data.

    Parameters
    ----------
    product : str
        Product identifier (e.g. "air").
    date : str
        Forecast date in YYYYMMDD format.
    run : str
        Initialization cycle (e.g. "00").
    variable : str
        Variable name to generate filled contours for.
    fhr : int
        Forecast hour.
    level : float, optional
        Vertical level for multi-level variables.

    Returns
    -------
    ORJSONResponse
        GeoJSON FeatureCollection with filled contour features and metadata.
    """
    t_total_start = time.perf_counter()

    logger.info(
        "api.filled.request",
        product=product,
        date=date,
        run=run,
        variable=variable,
        fhr=fhr,
        level=level,
    )

    # Check cache first
    key = _cache_key(date, run, variable, level, fhr)
    cached = _filled_cache.get(key)
    if cached is not None:
        logger.info("api.filled.cache_hit", variable=variable, fhr=fhr)
        return ORJSONResponse(
            content=cached,
            headers={"Cache-Control": "public, max-age=3600, immutable"},
        )

    selector = get_field_selector()

    # Resolve fill levels from domain config
    fill_levels: list[float] | None = None
    domain_config = get_domain_config_safe(product)
    if domain_config is not None:
        var_config = domain_config.get_variable(variable)
        if var_config is not None and var_config.rendering.fillLevels:
            fill_levels = var_config.rendering.fillLevels

    # --- Step 1: Extract field ---
    t_field_start = time.perf_counter()
    try:
        field = selector.select(date, run, variable, level=level, fhr=fhr)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.filled.field_unavailable",
            product=product,
            date=date,
            run=run,
            variable=variable,
            level=level,
            fhr=fhr,
            error=str(exc),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Could not select field: {exc}",
        )
    t_field_ms = (time.perf_counter() - t_field_start) * 1000

    # --- Step 2: Get coordinates and projection ---
    try:
        coordinates = selector.get_coordinates(date, run)
        projection = selector.get_projection(date, run)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.filled.coordinates_unavailable",
            error=str(exc),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Could not get coordinates/projection: {exc}",
        )

    # --- Step 2.5: Shift grid from 0-360 to -180..180 to avoid seam artifacts ---
    import numpy as _np

    from backend.app.data.field_selector import GridCoordinates

    # Extract 1D lon array (use first row if 2D)
    _lons_1d = coordinates.lons[0, :] if coordinates.lons.ndim == 2 else coordinates.lons
    _lats_1d = coordinates.lats[:, 0] if coordinates.lats.ndim == 2 else coordinates.lats
    shifted_field, shifted_lons, _ = shift_grid_to_minus180(field, _lons_1d)
    if not _np.array_equal(shifted_lons, _lons_1d):
        # Rebuild 2D coords from shifted 1D arrays
        _lons_2d, _lats_2d = _np.meshgrid(shifted_lons, _lats_1d)
        shifted_coords = GridCoordinates(
            lats=_lats_2d,
            lons=_lons_2d,
            shape=coordinates.shape,
        )
        field = shifted_field
        coordinates = shifted_coords

    # --- Step 3: Generate filled contours ---
    t_contour_start = time.perf_counter()
    filled_result = generate_filled_contours(
        field,
        fill_levels=fill_levels,
    )
    t_contour_ms = (time.perf_counter() - t_contour_start) * 1000

    # --- Step 4: Transform to GeoJSON ---
    t_transform_start = time.perf_counter()
    transformer = CoordinateTransformer.from_projection(projection)
    mapper = CoordinateMapper(coordinates, projection)
    geojson = filled_contours_to_geojson(filled_result, mapper, transformer)
    t_transform_ms = (time.perf_counter() - t_transform_start) * 1000

    # --- Step 5: Attach metadata ---
    t_serialize_start = time.perf_counter()

    # Compute field statistics
    field_valid = field[np.isfinite(field)]
    field_min = float(np.nanmin(field_valid)) if field_valid.size > 0 else 0.0
    field_max = float(np.nanmax(field_valid)) if field_valid.size > 0 else 0.0

    metadata: dict[str, Any] = {
        "variable": variable,
        "level": level,
        "fhr": fhr,
        "fillLevels": fill_levels if fill_levels is not None else [],
        "fieldMin": field_min,
        "fieldMax": field_max,
        "numBands": len(filled_result.polygons),
        "numFeatures": len(geojson.get("features", [])),
    }

    # Assemble full response
    response_data: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": geojson.get("features", []),
        "metadata": metadata,
    }

    t_serialize_ms = (time.perf_counter() - t_serialize_start) * 1000
    t_total_ms = (time.perf_counter() - t_total_start) * 1000

    # Store in cache
    _filled_cache[key] = response_data

    # Log timing instrumentation
    logger.info(
        "api.filled.done",
        product=product,
        date=date,
        run=run,
        variable=variable,
        fhr=fhr,
        level=level,
        fill_levels=fill_levels,
        field_min=field_min,
        field_max=field_max,
        num_bands=len(filled_result.polygons),
        num_features=len(geojson.get("features", [])),
        timing_field_ms=round(t_field_ms, 2),
        timing_contour_ms=round(t_contour_ms, 2),
        timing_transform_ms=round(t_transform_ms, 2),
        timing_serialize_ms=round(t_serialize_ms, 2),
        timing_total_ms=round(t_total_ms, 2),
    )

    return ORJSONResponse(
        content=response_data,
        headers={"Cache-Control": "public, max-age=3600, immutable"},
    )
