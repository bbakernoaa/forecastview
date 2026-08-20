"""Coordinate transformation module for native CRS ↔ geographic (lon/lat).

Provides the CoordinateTransformer class that wraps pyproj.Transformer
to handle conversions between a dataset's native coordinate reference
system and geographic coordinates (EPSG:4326). Supports both scalar
and numpy array inputs, handles the no-op case efficiently when source
and target CRS are identical, and normalizes longitudes from GRIB2's
0–360 convention to -180–180.
"""

from __future__ import annotations

from typing import Union

import numpy as np
from pyproj import CRS, Transformer

from backend.app.data.field_selector import GridProjection

# Type alias for scalar or array coordinate inputs
CoordLike = Union[float, np.ndarray]


def _normalize_longitude(lon: CoordLike) -> CoordLike:
    """Normalize longitude values from 0–360 to -180–180 range.

    Parameters
    ----------
    lon : float or np.ndarray
        Longitude value(s), potentially in 0–360 convention.

    Returns
    -------
    float or np.ndarray
        Longitude value(s) in -180–180 convention.
    """
    lon = np.asarray(lon)
    result = np.where(lon > 180.0, lon - 360.0, lon)
    # Return scalar if input was scalar
    if result.ndim == 0:
        return float(result)
    return result


class CoordinateTransformer:
    """Transforms coordinates between a native CRS and geographic (lon/lat).

    Wraps pyproj.Transformer to provide efficient coordinate
    transformations. Detects when source and target CRS are equivalent
    (e.g., both EPSG:4326 for regular lat-lon grids) and skips the
    pyproj call in that case.

    Parameters
    ----------
    source_crs : str
        Source CRS string (pyproj-compatible), e.g. "EPSG:4326" or a
        proj4 string like "+proj=lcc +lat_1=25 ...".
    target_crs : str
        Target CRS string (default "EPSG:4326" for geographic lon/lat).

    Attributes
    ----------
    is_noop : bool
        True when source and target CRS are equivalent, meaning no
        actual projection math is needed.
    source_crs : CRS
        The source pyproj CRS object.
    target_crs : CRS
        The target pyproj CRS object.
    """

    def __init__(
        self,
        source_crs: str,
        target_crs: str = "EPSG:4326",
    ) -> None:
        self._source_crs = CRS.from_user_input(source_crs)
        self._target_crs = CRS.from_user_input(target_crs)

        # Determine if transformation is a no-op (CRS are equivalent)
        self._is_noop = self._source_crs.equals(self._target_crs)

        # Build the transformer (forward: source → target)
        if not self._is_noop:
            self._transformer = Transformer.from_crs(
                self._source_crs,
                self._target_crs,
                always_xy=True,
            )
        else:
            self._transformer = None

    @classmethod
    def from_projection(
        cls,
        projection: GridProjection,
        target_crs: str = "EPSG:4326",
    ) -> "CoordinateTransformer":
        """Create a CoordinateTransformer from a GridProjection instance.

        Convenience constructor that extracts the CRS string from the
        projection metadata.

        Parameters
        ----------
        projection : GridProjection
            Projection metadata with a to_crs_string() method.
        target_crs : str
            Target CRS string (default "EPSG:4326").

        Returns
        -------
        CoordinateTransformer
            Configured transformer for the projection's native CRS.
        """
        source_crs = projection.to_crs_string()
        return cls(source_crs=source_crs, target_crs=target_crs)

    @property
    def is_noop(self) -> bool:
        """Whether the transform is a no-op (source and target CRS match)."""
        return self._is_noop

    @property
    def source_crs(self) -> CRS:
        """The source pyproj CRS object."""
        return self._source_crs

    @property
    def target_crs(self) -> CRS:
        """The target pyproj CRS object."""
        return self._target_crs

    def native_to_geographic(
        self, x: CoordLike, y: CoordLike
    ) -> tuple[CoordLike, CoordLike]:
        """Transform native CRS coordinates to geographic (lon, lat).

        For regular lat-lon grids where source CRS is already EPSG:4326,
        this performs longitude normalization only (0–360 → -180–180).
        For projected grids (Lambert, Polar Stereographic, etc.), uses
        pyproj for the actual coordinate transformation.

        Parameters
        ----------
        x : float or np.ndarray
            Native x-coordinate(s). For geographic CRS, this is longitude.
            For projected CRS, this is easting in meters.
        y : float or np.ndarray
            Native y-coordinate(s). For geographic CRS, this is latitude.
            For projected CRS, this is northing in meters.

        Returns
        -------
        tuple[float | np.ndarray, float | np.ndarray]
            (lon, lat) — geographic coordinates in EPSG:4326.
            Longitudes are normalized to -180–180 range.
        """
        if self._is_noop:
            # Source is already geographic — just normalize longitudes
            lon = _normalize_longitude(x)
            # Latitude passes through unchanged
            lat = np.asarray(y)
            if lat.ndim == 0:
                lat = float(lat)
            return lon, lat

        # Use pyproj for actual coordinate transformation
        x_arr = np.asarray(x, dtype=np.float64)
        y_arr = np.asarray(y, dtype=np.float64)

        lon, lat = self._transformer.transform(x_arr, y_arr)

        # Normalize output longitudes
        lon = _normalize_longitude(lon)

        # Return scalars if inputs were scalar
        if np.ndim(x) == 0 and np.ndim(y) == 0:
            return float(lon), float(lat)

        return lon, lat

    def geographic_to_native(
        self, lon: CoordLike, lat: CoordLike
    ) -> tuple[CoordLike, CoordLike]:
        """Transform geographic (lon, lat) coordinates to native CRS.

        Inverse of native_to_geographic. For regular lat-lon grids, this
        is essentially a pass-through. For projected grids, uses pyproj
        for the inverse transformation.

        Parameters
        ----------
        lon : float or np.ndarray
            Longitude(s) in degrees (-180 to 180 or 0 to 360).
        lat : float or np.ndarray
            Latitude(s) in degrees (-90 to 90).

        Returns
        -------
        tuple[float | np.ndarray, float | np.ndarray]
            (x, y) — coordinates in the native CRS.
        """
        if self._is_noop:
            # Geographic to geographic — pass through
            x = np.asarray(lon)
            y = np.asarray(lat)
            if x.ndim == 0:
                x = float(x)
            if y.ndim == 0:
                y = float(y)
            return x, y

        # Use pyproj for inverse transformation (target → source)
        lon_arr = np.asarray(lon, dtype=np.float64)
        lat_arr = np.asarray(lat, dtype=np.float64)

        # Inverse: geographic (target) → native (source)
        x, y = self._transformer.transform(
            lon_arr, lat_arr, direction="INVERSE"
        )

        # Return scalars if inputs were scalar
        if np.ndim(lon) == 0 and np.ndim(lat) == 0:
            return float(x), float(y)

        return x, y

    def transform_grid(
        self,
        lons_native: np.ndarray,
        lats_native: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Batch transform full 2D coordinate grids to geographic.

        Efficiently transforms entire 2D arrays of native coordinates
        to geographic (lon/lat). This is the primary method for
        transforming contour vertices or meshgrid coordinate arrays.

        Parameters
        ----------
        lons_native : np.ndarray
            2D (or 1D) array of native x-coordinates (longitudes for
            geographic CRS, eastings for projected CRS).
        lats_native : np.ndarray
            2D (or 1D) array of native y-coordinates (latitudes for
            geographic CRS, northings for projected CRS).

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            (lons_geo, lats_geo) — 2D arrays of geographic coordinates.
            Longitudes are normalized to -180–180 range.
        """
        lons = np.asarray(lons_native, dtype=np.float64)
        lats = np.asarray(lats_native, dtype=np.float64)

        if self._is_noop:
            # Just normalize longitudes
            lons_geo = np.where(lons > 180.0, lons - 360.0, lons)
            return lons_geo, lats.copy()

        # Flatten for pyproj, then reshape back
        original_shape = lons.shape
        lons_flat = lons.ravel()
        lats_flat = lats.ravel()

        lons_out, lats_out = self._transformer.transform(lons_flat, lats_flat)

        # Reshape to original dimensions
        lons_geo = lons_out.reshape(original_shape)
        lats_geo = lats_out.reshape(original_shape)

        # Normalize output longitudes
        lons_geo = np.where(lons_geo > 180.0, lons_geo - 360.0, lons_geo)

        return lons_geo, lats_geo
