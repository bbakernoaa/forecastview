"""Point query API endpoint for nearest-gridpoint value extraction.

Provides a JSON response with the forecast field value at the nearest
grid point to a user-specified geographic location. Supports all
variable/level/forecast-hour combinations available in the dataset.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse
from typing import Any

from backend.app.api.dependencies import get_field_selector
from backend.app.config.loader import get_domain_config_safe
from backend.app.point_query.nearest import query_point

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["point"])


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


@router.get("/point")
async def get_point(
    product: str = Query(..., description="Product identifier (e.g. 'air')"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
    variable: str = Query(..., description="Variable name"),
    fhr: int = Query(..., description="Forecast hour"),
    lat: float = Query(..., description="Query latitude (-90 to 90)"),
    lon: float = Query(..., description="Query longitude (-180 to 180)"),
    level: float | None = Query(
        None, description="Vertical level value (for multi-level variables)"
    ),
) -> ORJSONResponse:
    """Return the forecast value at the nearest grid point to (lat, lon).

    Extracts the requested field, performs a nearest-gridpoint lookup,
    and returns the value along with metadata about the query location,
    variable, and forecast timing.

    Parameters
    ----------
    product : str
        Product identifier (e.g. "air").
    date : str
        Forecast date in YYYYMMDD format.
    run : str
        Initialization cycle (e.g. "00").
    variable : str
        Variable name to query.
    fhr : int
        Forecast hour.
    lat : float
        Query latitude in degrees (-90 to 90).
    lon : float
        Query longitude in degrees (-180 to 180).
    level : float, optional
        Vertical level for multi-level variables.

    Returns
    -------
    ORJSONResponse
        JSON with lat, lon, variable, value, units, level, fhr,
        valid_time, grid_lat, grid_lon.
    """
    logger.info(
        "api.point.request",
        product=product,
        date=date,
        run=run,
        variable=variable,
        fhr=fhr,
        lat=lat,
        lon=lon,
        level=level,
    )

    # Validate lat/lon range
    if lat < -90 or lat > 90:
        raise HTTPException(
            status_code=422,
            detail=f"Latitude must be between -90 and 90, got {lat}",
        )
    if lon < -180 or lon > 180:
        raise HTTPException(
            status_code=422,
            detail=f"Longitude must be between -180 and 180, got {lon}",
        )

    selector = get_field_selector()

    # --- Step 1: Extract field ---
    try:
        field = selector.select(date, run, variable, level=level, fhr=fhr)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.point.field_unavailable",
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

    # --- Step 2: Get coordinates and projection ---
    try:
        coordinates = selector.get_coordinates(date, run)
        projection = selector.get_projection(date, run)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.point.coordinates_unavailable",
            error=str(exc),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Could not get coordinates/projection: {exc}",
        )

    # --- Step 3: Perform point query ---
    result = query_point(lon, lat, field, coordinates, projection)

    # --- Step 4: Compute valid time ---
    try:
        init_time = datetime.strptime(f"{date}{run}", "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
        valid_time = init_time + timedelta(hours=fhr)
        valid_time_str = valid_time.isoformat()
    except ValueError:
        valid_time_str = None

    # --- Step 5: Get variable metadata ---
    units = ""
    domain_config = get_domain_config_safe(product)
    if domain_config is not None:
        var_config = domain_config.get_variable(variable)
        if var_config is not None:
            units = var_config.units

    # --- Step 6: Build response ---
    response_data: dict[str, Any] = {
        "lat": result.lat,
        "lon": result.lon,
        "variable": variable,
        "value": result.value,
        "units": units,
        "level": level,
        "fhr": fhr,
        "valid_time": valid_time_str,
        "grid_lat": result.nearest_lat,
        "grid_lon": result.nearest_lon,
    }

    logger.info(
        "api.point.done",
        product=product,
        variable=variable,
        fhr=fhr,
        lat=lat,
        lon=lon,
        value=result.value,
        grid_i=result.grid_i,
        grid_j=result.grid_j,
    )

    return ORJSONResponse(content=response_data)
