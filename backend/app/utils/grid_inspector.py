"""Grid inspection utility for coordinate and projection diagnostics.

Provides functions to inspect and report grid coordinate extents,
spatial characteristics, latitude/longitude conventions, and
projection metadata from FieldSelector outputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from backend.app.data.field_selector import GridCoordinates, GridProjection


def check_orientation(lats: np.ndarray) -> str:
    """Determine latitude ordering direction.

    Parameters
    ----------
    lats : np.ndarray
        1D or 2D latitude array. For 2D arrays, the first column
        is used to determine north-south ordering.

    Returns
    -------
    str
        "N→S" if latitudes decrease along the first axis (row 0 is
        northernmost), "S→N" if they increase.
    """
    if lats.ndim == 2:
        col = lats[:, 0]
    else:
        col = lats

    if col.size < 2:
        return "N→S"

    first_valid = col[0]
    last_valid = col[-1]
    return "N→S" if first_valid > last_valid else "S→N"


def check_longitude_convention(lons: np.ndarray) -> str:
    """Determine longitude convention used in the grid.

    Parameters
    ----------
    lons : np.ndarray
        1D or 2D longitude array.

    Returns
    -------
    str
        "0-360" if all longitude values are >= 0 (typical GRIB2
        convention), "-180-180" if any values are negative.
    """
    flat = lons.ravel()
    valid = flat[~np.isnan(flat)]

    if valid.size == 0:
        return "0-360"

    if np.any(valid < 0):
        return "-180-180"
    return "0-360"


def get_grid_info(
    coords: GridCoordinates,
    projection: GridProjection | None = None,
) -> dict[str, Any]:
    """Compute grid inspection information as a dictionary.

    Parameters
    ----------
    coords : GridCoordinates
        Coordinate arrays from FieldSelector.get_coordinates().
    projection : GridProjection, optional
        Projection metadata from FieldSelector.get_projection().

    Returns
    -------
    dict[str, Any]
        Dictionary containing:
        - shape: (ny, nx) tuple
        - lat_min, lat_max: latitude extent
        - lon_min, lon_max: longitude extent
        - orientation: "N→S" or "S→N"
        - lon_convention: "0-360" or "-180-180"
        - approx_dy: approximate grid spacing in latitude (degrees)
        - approx_dx: approximate grid spacing in longitude (degrees)
        - is_regular: whether the grid appears regular (1D coords)
        - grid_type: projection grid type (if projection provided)
        - crs_string: CRS string (if projection provided)
        - scanning_mode: scanning mode flags (if projection provided)
    """
    info: dict[str, Any] = {}

    ny, nx = coords.shape
    info["shape"] = (ny, nx)

    lats = coords.lats
    lons = coords.lons

    # Latitude extent
    info["lat_min"] = float(np.nanmin(lats))
    info["lat_max"] = float(np.nanmax(lats))

    # Longitude extent
    info["lon_min"] = float(np.nanmin(lons))
    info["lon_max"] = float(np.nanmax(lons))

    # Orientation and convention
    info["orientation"] = check_orientation(lats)
    info["lon_convention"] = check_longitude_convention(lons)

    # Grid regularity — regular if coordinates are 1D
    info["is_regular"] = lats.ndim == 1 and lons.ndim == 1

    # Approximate grid spacing
    if lats.ndim == 1 and lats.size >= 2:
        info["approx_dy"] = float(abs(np.nanmean(np.diff(lats))))
    elif lats.ndim == 2 and lats.shape[0] >= 2:
        # Use first column for dy estimate
        col = lats[:, 0]
        info["approx_dy"] = float(abs(np.nanmean(np.diff(col))))
    else:
        info["approx_dy"] = float("nan")

    if lons.ndim == 1 and lons.size >= 2:
        info["approx_dx"] = float(abs(np.nanmean(np.diff(lons))))
    elif lons.ndim == 2 and lons.shape[1] >= 2:
        # Use first row for dx estimate
        row = lons[0, :]
        info["approx_dx"] = float(abs(np.nanmean(np.diff(row))))
    else:
        info["approx_dx"] = float("nan")

    # Projection info
    if projection is not None:
        info["grid_type"] = projection.grid_type
        info["crs_string"] = projection.to_crs_string()
        info["scanning_mode"] = projection.scanning_mode
    else:
        info["grid_type"] = None
        info["crs_string"] = None
        info["scanning_mode"] = None

    return info


def print_grid_info(
    coords: GridCoordinates,
    projection: GridProjection | None = None,
) -> None:
    """Print comprehensive grid inspection diagnostics to stdout.

    Parameters
    ----------
    coords : GridCoordinates
        Coordinate arrays from FieldSelector.get_coordinates().
    projection : GridProjection, optional
        Projection metadata from FieldSelector.get_projection().
    """
    info = get_grid_info(coords, projection)

    ny, nx = info["shape"]

    print(f"\n{'=' * 60}")
    print("Grid Inspection")
    print("=" * 60)

    # Shape
    print(f"  Grid shape:         {ny} rows (ny) x {nx} cols (nx)")
    print(f"  Grid type:          {'Regular' if info['is_regular'] else 'Curvilinear'}")

    # Latitude
    print()
    print(f"  Latitude extent:    {info['lat_min']:.6g} to {info['lat_max']:.6g}")
    print(f"  Latitude ordering:  {info['orientation']}")
    print(f"  Approx dy:          {info['approx_dy']:.6g} degrees")

    # Longitude
    print()
    print(f"  Longitude extent:   {info['lon_min']:.6g} to {info['lon_max']:.6g}")
    print(f"  Longitude convention: {info['lon_convention']}")
    print(f"  Approx dx:          {info['approx_dx']:.6g} degrees")

    # Projection
    if projection is not None:
        print()
        print("  Projection:")
        print(f"    Grid type:        {info['grid_type']}")
        print(f"    CRS string:       {info['crs_string']}")
        if info["scanning_mode"]:
            print(f"    Scanning mode:    {info['scanning_mode']}")
        else:
            print("    Scanning mode:    (not available)")
    else:
        print()
        print("  Projection:         (not provided)")

    print("=" * 60)
