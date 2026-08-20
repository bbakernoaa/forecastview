"""GeoJSON serialization for contour isolines.

Transforms contour vertices from grid-index space to geographic
coordinates (lon/lat) and serializes them as a GeoJSON
FeatureCollection. Each contour level produces a single Feature with
MultiLineString geometry (one level may have multiple disconnected
line segments).

The transformation pipeline is:
    grid indices (col, row) → native CRS coords → geographic (lon, lat)
"""

from __future__ import annotations

import numpy as np
import orjson

from backend.app.contours.generator import ContourResult, FilledContourResult
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer


def shift_grid_to_minus180(
    field: np.ndarray,
    lons: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Shift a 0-360 longitude grid to -180..180 before contouring.

    Rolls the field and longitude array so that the grid starts at -180°,
    eliminating the 0°/360° seam that causes contour polygon artifacts.

    Parameters
    ----------
    field : np.ndarray
        2D field array with shape (ny, nx).
    lons : np.ndarray
        1D longitude array (must be monotonically increasing, 0..360 range).

    Returns
    -------
    tuple[np.ndarray, np.ndarray, int]
        (shifted_field, shifted_lons, split_index) where split_index is
        the number of columns rolled.
    """
    if lons.ndim != 1:
        return field, lons, 0

    # Only shift if lons are in 0-360 range
    if lons[0] >= 0 and lons[-1] > 180:
        split_idx = int(np.searchsorted(lons, 180.0))
        shifted_lons = np.concatenate([lons[split_idx:] - 360.0, lons[:split_idx]])
        shifted_field = np.roll(field, -split_idx, axis=1)
        return shifted_field, shifted_lons, split_idx

    return field, lons, 0


def _transform_vertices(
    verts: np.ndarray,
    mapper: CoordinateMapper,
    transformer: CoordinateTransformer,
) -> tuple[np.ndarray, np.ndarray]:
    """Transform contour vertices from grid-index space to geographic coordinates.

    Handles fractional grid indices properly via linear interpolation
    for regular grids, preserving sub-grid contour vertex precision.
    This avoids the integer-truncation artifacts that occur when
    snapping fractional indices to the nearest grid point.

    Parameters
    ----------
    verts : np.ndarray
        Nx2 array of (col_index, row_index) in floating-point grid space
        as produced by contourpy.
    mapper : CoordinateMapper
        Maps grid indices to native CRS coordinates. Used to access
        the underlying coordinate arrays.
    transformer : CoordinateTransformer
        Transforms native CRS coordinates to geographic (lon, lat).

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (lon, lat) arrays in geographic coordinates (EPSG:4326).
    """
    col_indices = verts[:, 0]
    row_indices = verts[:, 1]

    # Extract 1D coordinate vectors for interpolation.
    # Works for both truly 1D coords and regular grids stored as 2D meshgrids.
    coords = mapper._coordinates
    if coords.lons.ndim == 1:
        lons_1d = np.asarray(coords.lons, dtype=np.float64)
        lats_1d = np.asarray(coords.lats, dtype=np.float64)
    elif coords.lons.ndim == 2:
        # Regular grid stored as 2D meshgrid — extract 1D vectors
        lons_1d = np.asarray(coords.lons[0, :], dtype=np.float64)
        lats_1d = np.asarray(coords.lats[:, 0], dtype=np.float64)
    else:
        # Fallback for unexpected cases
        lons_1d = np.asarray(coords.lons.ravel()[:mapper.shape[1]], dtype=np.float64)
        lats_1d = np.asarray(coords.lats.ravel()[:mapper.shape[0]], dtype=np.float64)

    # Clip to valid index range
    col_clipped = np.clip(col_indices, 0, len(lons_1d) - 1)
    row_clipped = np.clip(row_indices, 0, len(lats_1d) - 1)

    # Linear interpolation for fractional grid indices
    x_native = np.interp(col_clipped, np.arange(len(lons_1d)), lons_1d)
    y_native = np.interp(row_clipped, np.arange(len(lats_1d)), lats_1d)

    # Transform native CRS → geographic (lon, lat)
    lon, lat = transformer.native_to_geographic(x_native, y_native)

    return np.asarray(lon), np.asarray(lat)


def contours_to_geojson(
    result: ContourResult,
    mapper: CoordinateMapper,
    transformer: CoordinateTransformer,
) -> dict:
    """Convert a ContourResult to a GeoJSON FeatureCollection.

    Transforms contour vertices from grid-index space through the
    coordinate pipeline (grid → native → geographic) and packages
    each contour level as a GeoJSON Feature with MultiLineString
    geometry.

    Parameters
    ----------
    result : ContourResult
        Output from ``generate_isolines``, containing contour lines
        in grid-index space.
    mapper : CoordinateMapper
        Maps grid indices (row, col) to native CRS coordinates.
    transformer : CoordinateTransformer
        Transforms native CRS coordinates to geographic (lon, lat).

    Returns
    -------
    dict
        A GeoJSON FeatureCollection dict with:
        - type: "FeatureCollection"
        - features: list of Feature dicts, each with:
            - type: "Feature"
            - geometry: { type: "MultiLineString", coordinates: [...] }
            - properties: { value: float, major: bool }

    Notes
    -----
    - Empty ContourResults produce an empty FeatureCollection.
    - Contour vertices follow contourpy convention: x = column index,
      y = row index. The transformation reverses this to (row, col)
      for the CoordinateMapper which expects (i=row, j=col).
    - Output coordinates are [lon, lat] per the GeoJSON spec (RFC 7946).
    """
    features: list[dict] = []

    if not result.lines:
        return {"type": "FeatureCollection", "features": features}

    for contour_line in result.lines:
        if not contour_line.vertices:
            continue

        multi_line_coords: list[list[list[float]]] = []

        for verts in contour_line.vertices:
            # Transform fractional grid indices → geographic coordinates
            lon_arr, lat_arr = _transform_vertices(verts, mapper, transformer)

            # Build coordinate list as [lon, lat] pairs (GeoJSON standard)
            line_coords: list[list[float]] = [
                [float(lon_arr[k]), float(lat_arr[k])]
                for k in range(len(lon_arr))
            ]

            if len(line_coords) >= 2:
                multi_line_coords.append(line_coords)

        if not multi_line_coords:
            continue

        feature: dict = {
            "type": "Feature",
            "geometry": {
                "type": "MultiLineString",
                "coordinates": multi_line_coords,
            },
            "properties": {
                "value": contour_line.level,
                "major": contour_line.is_major,
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def _split_rings_by_offsets(
    vertices: np.ndarray, offsets: np.ndarray
) -> list[np.ndarray]:
    """Split a polygon vertices array into individual rings using offset boundaries.

    Used with contourpy's FillType.OuterOffset output format, where
    offsets mark the start/end of each ring within the vertices array.

    Parameters
    ----------
    vertices : np.ndarray
        Nx2 array of polygon vertex coordinates.
    offsets : np.ndarray
        Array of ring boundary offsets. Ring i spans
        vertices[offsets[i]:offsets[i+1]].

    Returns
    -------
    list[np.ndarray]
        List of Mx2 arrays, each representing one closed ring.
    """
    rings: list[np.ndarray] = []

    for i in range(len(offsets) - 1):
        start = int(offsets[i])
        end = int(offsets[i + 1])
        ring_verts = vertices[start:end]
        if len(ring_verts) >= 3:
            rings.append(ring_verts)

    return rings


def filled_contours_to_geojson(
    result: FilledContourResult,
    mapper: CoordinateMapper,
    transformer: CoordinateTransformer,
) -> dict:
    """Convert a FilledContourResult to a GeoJSON FeatureCollection.

    Transforms filled polygon vertices from grid-index space through the
    coordinate pipeline (grid → native → geographic) and packages each
    fill band as a GeoJSON Feature with Polygon or MultiPolygon geometry.

    Parameters
    ----------
    result : FilledContourResult
        Output from ``generate_filled_contours``, containing filled
        polygons in grid-index space.
    mapper : CoordinateMapper
        Maps grid indices (row, col) to native CRS coordinates.
    transformer : CoordinateTransformer
        Transforms native CRS coordinates to geographic (lon, lat).

    Returns
    -------
    dict
        A GeoJSON FeatureCollection dict with:
        - type: "FeatureCollection"
        - features: list of Feature dicts, each with:
            - type: "Feature"
            - geometry: { type: "Polygon" or "MultiPolygon", coordinates: [...] }
            - properties: { level_low: float, level_high: float }

    Notes
    -----
    - Empty FilledContourResults produce an empty FeatureCollection.
    - Fill bands with no valid polygons are skipped.
    - Polygon vertices follow contourpy convention: x = column index,
      y = row index. The transformation reverses this to (row, col)
      for the CoordinateMapper which expects (i=row, j=col).
    - Output coordinates are [lon, lat] per the GeoJSON spec (RFC 7946).
    - Each polygon ring is closed (first point == last point) per GeoJSON.
    """
    features: list[dict] = []

    if not result.polygons:
        return {"type": "FeatureCollection", "features": features}

    for fill_band in result.polygons:
        if not fill_band.polygons:
            continue

        # Collect all transformed polygon rings for this band
        all_polygon_rings: list[list[list[list[float]]]] = []

        for verts, offsets in zip(fill_band.polygons, fill_band.codes):
            # Split into individual rings using offset boundaries
            rings = _split_rings_by_offsets(verts, offsets)
            if not rings:
                continue

            # Transform each ring
            polygon_rings: list[list[list[float]]] = []
            for ring in rings:
                # Transform fractional grid indices → geographic coordinates
                lon_arr, lat_arr = _transform_vertices(ring, mapper, transformer)

                # Filter out artifact polygons:
                # 1. Rings spanning > 100° longitude (grid seam wrap-arounds)
                # 2. Rings with extreme aspect ratios (horizontal bands)
                lon_range = float(np.max(lon_arr) - np.min(lon_arr))
                lat_range = float(np.max(lat_arr) - np.min(lat_arr))

                if lon_range > 100.0:
                    continue

                # Skip degenerate thin horizontal bands (aspect ratio > 50:1)
                if lat_range > 0 and lon_range / max(lat_range, 0.01) > 50:
                    continue
                if lat_range < 0.3 and lon_range > 10:
                    continue

                # Build coordinate list as [lon, lat] pairs
                ring_coords: list[list[float]] = [
                    [float(lon_arr[k]), float(lat_arr[k])]
                    for k in range(len(lon_arr))
                ]

                # Ensure ring is closed (GeoJSON requirement)
                if len(ring_coords) >= 3:
                    if ring_coords[0] != ring_coords[-1]:
                        ring_coords.append(ring_coords[0])
                    polygon_rings.append(ring_coords)

            if polygon_rings:
                all_polygon_rings.append(polygon_rings)

        if not all_polygon_rings:
            continue

        # Create geometry — MultiPolygon if multiple polygons, Polygon if one
        if len(all_polygon_rings) == 1:
            geometry: dict = {
                "type": "Polygon",
                "coordinates": all_polygon_rings[0],
            }
        else:
            geometry = {
                "type": "MultiPolygon",
                "coordinates": all_polygon_rings,
            }

        feature: dict = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "level_low": fill_band.level_low,
                "level_high": fill_band.level_high,
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def serialize_geojson_bytes(feature_collection: dict) -> bytes:
    """Serialize a GeoJSON FeatureCollection dict to bytes using orjson.

    Useful for caching or streaming raw bytes without going through
    Python's json module. orjson is significantly faster for large
    GeoJSON payloads.

    Parameters
    ----------
    feature_collection : dict
        A GeoJSON-compatible dict (typically from ``contours_to_geojson``).

    Returns
    -------
    bytes
        UTF-8 encoded JSON bytes.
    """
    return orjson.dumps(feature_collection)
