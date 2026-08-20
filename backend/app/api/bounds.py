"""Bounds API endpoint for geographic alignment verification.

Provides a GeoJSON bounding polygon for a field's coordinate grid,
used to verify correct geographic alignment on the MapLibre map
before implementing full contour rendering.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.api.dependencies import get_field_selector
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["bounds"])


# --------------------------------------------------------------------------
# Response model
# --------------------------------------------------------------------------


class BoundsFeature(BaseModel):
    """GeoJSON Feature representing the field bounding polygon."""

    type: str = Field(default="Feature")
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon geometry")
    properties: dict[str, Any] = Field(..., description="Grid metadata (grid_type, shape)")


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


@router.get("/bounds", response_model=BoundsFeature)
async def get_bounds(
    product: str = Query(..., description="Product identifier (e.g. 'air')"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
) -> BoundsFeature:
    """Return a GeoJSON bounding polygon for the field grid.

    Opens the dataset, extracts coordinates, transforms to geographic
    lon/lat, and returns a GeoJSON Feature (Polygon) representing the
    bounding box of the field grid. Used for development/verification
    of geographic alignment.

    Parameters
    ----------
    product : str
        Product identifier.
    date : str
        Forecast date in YYYYMMDD format.
    run : str
        Initialization cycle (e.g. "00").

    Returns
    -------
    BoundsFeature
        GeoJSON Feature with Polygon geometry of the bounding box.
    """
    logger.info("api.bounds.request", product=product, date=date, run=run)

    selector = get_field_selector()

    # Get coordinates and projection
    try:
        coordinates = selector.get_coordinates(date, run)
        projection = selector.get_projection(date, run)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.bounds.dataset_unavailable",
            product=product,
            date=date,
            run=run,
            error=str(exc),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Could not open dataset for product={product}, "
            f"date={date}, run={run}: {exc}",
        )

    # Transform coordinates to geographic lon/lat
    transformer = CoordinateTransformer.from_projection(projection)
    mapper = CoordinateMapper(coordinates, projection)

    # Get the full meshgrid of native coordinates
    lons_native, lats_native = mapper.get_grid_meshgrid()

    # Transform to geographic
    lons_geo, lats_geo = transformer.transform_grid(lons_native, lats_native)

    # Compute bounding box from the geographic coordinates
    lon_min = float(lons_geo.min())
    lon_max = float(lons_geo.max())
    lat_min = float(lats_geo.min())
    lat_max = float(lats_geo.max())

    # Build GeoJSON Polygon (5-point closed ring for the bounding box)
    polygon_coords = [
        [lon_min, lat_min],
        [lon_max, lat_min],
        [lon_max, lat_max],
        [lon_min, lat_max],
        [lon_min, lat_min],  # close the ring
    ]

    feature = BoundsFeature(
        geometry={
            "type": "Polygon",
            "coordinates": [polygon_coords],
        },
        properties={
            "grid_type": projection.grid_type,
            "shape": list(coordinates.shape),
            "lon_min": lon_min,
            "lon_max": lon_max,
            "lat_min": lat_min,
            "lat_max": lat_max,
        },
    )

    logger.info(
        "api.bounds.done",
        product=product,
        date=date,
        run=run,
        grid_type=projection.grid_type,
        shape=list(coordinates.shape),
        lon_range=[lon_min, lon_max],
        lat_range=[lat_min, lat_max],
    )

    return feature
