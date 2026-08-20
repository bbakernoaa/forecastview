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
            # verts is Nx2 with columns [x=col_index, y=row_index]
            col_indices = verts[:, 0]
            row_indices = verts[:, 1]

            # Step 1: grid indices → native CRS coordinates
            # CoordinateMapper.grid_to_native(i=row, j=col) → (x_native, y_native)
            x_native, y_native = mapper.grid_to_native(
                row_indices.astype(int), col_indices.astype(int)
            )

            # Step 2: native CRS → geographic (lon, lat)
            lon, lat = transformer.native_to_geographic(
                np.asarray(x_native, dtype=np.float64),
                np.asarray(y_native, dtype=np.float64),
            )

            # Build coordinate list as [lon, lat] pairs (GeoJSON standard)
            lon_arr = np.asarray(lon)
            lat_arr = np.asarray(lat)

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


def _split_rings_by_codes(
    vertices: np.ndarray, codes: np.ndarray
) -> list[np.ndarray]:
    """Split a single polygon vertices array into individual rings using path codes.

    Path codes follow matplotlib conventions:
    - 1 = MOVETO (start of a new ring)
    - 2 = LINETO (continuation)
    - 79 = CLOSEPOLY (close the ring)

    Parameters
    ----------
    vertices : np.ndarray
        Nx2 array of polygon vertex coordinates.
    codes : np.ndarray
        N-length array of path codes.

    Returns
    -------
    list[np.ndarray]
        List of Mx2 arrays, each representing one closed ring.
    """
    rings: list[np.ndarray] = []
    # Find ring starts (MOVETO = 1)
    moveto_indices = np.where(codes == 1)[0]

    for idx, start in enumerate(moveto_indices):
        # Ring ends at next MOVETO or end of array
        if idx + 1 < len(moveto_indices):
            end = moveto_indices[idx + 1]
        else:
            end = len(codes)

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

        for verts, codes in zip(fill_band.polygons, fill_band.codes):
            # Split into individual rings using path codes
            rings = _split_rings_by_codes(verts, codes)
            if not rings:
                continue

            # Transform each ring
            polygon_rings: list[list[list[float]]] = []
            for ring in rings:
                # ring is Nx2 with columns [x=col_index, y=row_index]
                col_indices = ring[:, 0]
                row_indices = ring[:, 1]

                # Step 1: grid indices → native CRS coordinates
                x_native, y_native = mapper.grid_to_native(
                    row_indices.astype(int), col_indices.astype(int)
                )

                # Step 2: native CRS → geographic (lon, lat)
                lon, lat = transformer.native_to_geographic(
                    np.asarray(x_native, dtype=np.float64),
                    np.asarray(y_native, dtype=np.float64),
                )

                # Build coordinate list as [lon, lat] pairs
                lon_arr = np.asarray(lon)
                lat_arr = np.asarray(lat)

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
