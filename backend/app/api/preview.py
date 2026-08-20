"""Preview API endpoint for coarse field visualization.

Returns a downsampled field as a GeoJSON FeatureCollection of colored
points, used to visually verify geographic orientation on the MapLibre
map (e.g., confirming Saharan dust appears over Africa).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.api.dependencies import get_field_selector
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["preview"])


# --------------------------------------------------------------------------
# Response model
# --------------------------------------------------------------------------


class PreviewFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection of downsampled field points."""

    type: str = Field(default="FeatureCollection")
    features: list[dict[str, Any]] = Field(
        ..., description="GeoJSON Point features with value property"
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Collection-level metadata (min, max, variable, units)",
    )


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


@router.get("/preview", response_model=PreviewFeatureCollection)
async def get_preview(
    product: str = Query(..., description="Product identifier (e.g. 'air')"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
    variable: str = Query(..., description="Variable name"),
    fhr: int = Query(0, description="Forecast hour"),
    resolution: int = Query(
        4,
        ge=1,
        le=20,
        description="Downsample factor (e.g. 4 = every 4th point)",
    ),
) -> PreviewFeatureCollection:
    """Return a downsampled field as GeoJSON points for map preview.

    Opens the dataset, selects the field, downsamples by the given
    resolution factor, transforms coordinates to geographic lon/lat,
    and returns a GeoJSON FeatureCollection where each feature is a
    Point with a `value` property.

    Parameters
    ----------
    product : str
        Product identifier.
    date : str
        Forecast date in YYYYMMDD format.
    run : str
        Initialization cycle (e.g. "00").
    variable : str
        Variable name to extract.
    fhr : int
        Forecast hour (default 0).
    resolution : int
        Downsample factor (default 4). Every Nth point is kept.

    Returns
    -------
    PreviewFeatureCollection
        GeoJSON FeatureCollection with Point features.
    """
    logger.info(
        "api.preview.request",
        product=product,
        date=date,
        run=run,
        variable=variable,
        fhr=fhr,
        resolution=resolution,
    )

    selector = get_field_selector()

    # Extract the field
    try:
        field = selector.select(date, run, variable, fhr=fhr)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.preview.field_unavailable",
            product=product,
            date=date,
            run=run,
            variable=variable,
            error=str(exc),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Could not select field: {exc}",
        )

    # Get coordinates and projection
    try:
        coordinates = selector.get_coordinates(date, run)
        projection = selector.get_projection(date, run)
    except (ValueError, RuntimeError) as exc:
        logger.warning(
            "api.preview.coordinates_unavailable",
            error=str(exc),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Could not get coordinates: {exc}",
        )

    # Transform coordinates to geographic lon/lat
    transformer = CoordinateTransformer.from_projection(projection)
    mapper = CoordinateMapper(coordinates, projection)

    # Get the full meshgrid of native coordinates
    lons_native, lats_native = mapper.get_grid_meshgrid()

    # Transform to geographic
    lons_geo, lats_geo = transformer.transform_grid(lons_native, lats_native)

    # Downsample: take every Nth point in both dimensions
    field_ds = field[::resolution, ::resolution]
    lons_ds = lons_geo[::resolution, ::resolution]
    lats_ds = lats_geo[::resolution, ::resolution]

    # Compute min/max for color mapping (from full field for accuracy)
    field_valid = field[np.isfinite(field)]
    if field_valid.size > 0:
        field_min = float(np.nanmin(field_valid))
        field_max = float(np.nanmax(field_valid))
    else:
        field_min = 0.0
        field_max = 1.0

    # Build GeoJSON features
    features: list[dict[str, Any]] = []
    ny, nx = field_ds.shape

    for i in range(ny):
        for j in range(nx):
            val = float(field_ds[i, j])
            if not np.isfinite(val):
                continue
            lon = float(lons_ds[i, j])
            lat = float(lats_ds[i, j])
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat],
                    },
                    "properties": {
                        "value": val,
                    },
                }
            )

    result = PreviewFeatureCollection(
        features=features,
        properties={
            "variable": variable,
            "min": field_min,
            "max": field_max,
            "units": "",  # Could be enriched from domain config
            "resolution": resolution,
            "point_count": len(features),
            "original_shape": list(field.shape),
        },
    )

    logger.info(
        "api.preview.done",
        product=product,
        date=date,
        run=run,
        variable=variable,
        fhr=fhr,
        resolution=resolution,
        point_count=len(features),
        field_min=field_min,
        field_max=field_max,
    )

    return result
