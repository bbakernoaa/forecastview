"""Nearest-gridpoint point query module.

Provides the query_point function for extracting forecast field values
at a given geographic location via nearest-gridpoint lookup. Uses the
CoordinateMapper and CoordinateTransformer infrastructure to handle
arbitrary grid projections.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

from backend.app.data.field_selector import GridCoordinates, GridProjection
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PointQueryResult:
    """Result of a nearest-gridpoint point query.

    Attributes
    ----------
    lat : float
        Requested query latitude.
    lon : float
        Requested query longitude.
    grid_i : int
        Row index of the nearest grid point.
    grid_j : int
        Column index of the nearest grid point.
    value : float | None
        Field value at the nearest grid point. None if the value is
        NaN or the point falls outside the domain.
    nearest_lat : float
        Latitude of the nearest grid point center.
    nearest_lon : float
        Longitude of the nearest grid point center.
    """

    lat: float
    lon: float
    grid_i: int
    grid_j: int
    value: float | None
    nearest_lat: float
    nearest_lon: float


def query_point(
    lon: float,
    lat: float,
    field: np.ndarray,
    coordinates: GridCoordinates,
    projection: GridProjection,
) -> PointQueryResult:
    """Query the forecast field value at the nearest grid point to (lon, lat).

    Transforms the geographic query point to native CRS coordinates,
    finds the nearest grid index using CoordinateMapper, extracts the
    field value, and returns the result along with the actual grid point
    coordinates.

    Parameters
    ----------
    lon : float
        Query longitude in degrees (-180 to 180).
    lat : float
        Query latitude in degrees (-90 to 90).
    field : np.ndarray
        2D numpy array of field values with shape (ny, nx).
    coordinates : GridCoordinates
        Coordinate arrays (lats, lons, shape) from the dataset.
    projection : GridProjection
        Projection metadata for the dataset.

    Returns
    -------
    PointQueryResult
        Dataclass containing query coordinates, grid indices, field value,
        and nearest grid point coordinates.
    """
    logger.debug(
        "point_query.nearest.query",
        lon=lon,
        lat=lat,
        field_shape=field.shape,
    )

    # Build mapper and transformer
    transformer = CoordinateTransformer.from_projection(projection)
    mapper = CoordinateMapper(coordinates, projection)

    # Transform geographic (lon, lat) → native CRS (x, y)
    x_native, y_native = transformer.geographic_to_native(lon, lat)

    # Find nearest grid index
    i, j = mapper.native_to_grid(x_native, y_native)

    # Ensure indices are within bounds
    ny, nx = field.shape
    i = int(np.clip(i, 0, ny - 1))
    j = int(np.clip(j, 0, nx - 1))

    # Extract value at nearest grid point
    raw_value = field[i, j]
    value: float | None = float(raw_value) if np.isfinite(raw_value) else None

    # Get geographic coordinates of the actual nearest grid point
    x_grid, y_grid = mapper.grid_to_native(i, j)
    grid_lon, grid_lat = transformer.native_to_geographic(x_grid, y_grid)

    # Ensure scalar outputs
    nearest_lat = float(grid_lat) if not isinstance(grid_lat, float) else grid_lat
    nearest_lon = float(grid_lon) if not isinstance(grid_lon, float) else grid_lon

    result = PointQueryResult(
        lat=lat,
        lon=lon,
        grid_i=i,
        grid_j=j,
        value=value,
        nearest_lat=nearest_lat,
        nearest_lon=nearest_lon,
    )

    logger.info(
        "point_query.nearest.done",
        lon=lon,
        lat=lat,
        grid_i=i,
        grid_j=j,
        value=value,
        nearest_lat=nearest_lat,
        nearest_lon=nearest_lon,
    )

    return result
