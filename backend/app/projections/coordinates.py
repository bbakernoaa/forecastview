"""Coordinate mapping module for grid-index ↔ native CRS transformations.

Provides the CoordinateMapper class that handles mapping between grid
indices (i, j) and native CRS coordinates. Supports both regular
(rectilinear) grids where efficient index math can be used, and
curvilinear grids where full 2D coordinate arrays are required.
"""

from __future__ import annotations

from typing import Union

import numpy as np

from backend.app.data.field_selector import GridCoordinates, GridProjection

# Type alias for scalar or array inputs
IndexLike = Union[int, np.ndarray]
CoordLike = Union[float, np.ndarray]


class CoordinateMapper:
    """Maps between grid indices (i, j) and native CRS coordinates.

    For regular (rectilinear) grids, coordinate lookups use efficient
    index arithmetic on 1D coordinate vectors. For curvilinear grids
    (2D coordinate arrays), the full arrays are used directly.

    Parameters
    ----------
    coordinates : GridCoordinates
        Coordinate arrays (lats, lons, shape) from the dataset.
    projection : GridProjection, optional
        Projection metadata. Used to determine grid type and scanning
        mode. If None, the grid is assumed to be regular lat-lon.

    Attributes
    ----------
    is_regular : bool
        True if coordinate arrays are 1D (regular/rectilinear grid).
    shape : tuple[int, ...]
        Grid shape (ny, nx).
    """

    def __init__(
        self,
        coordinates: GridCoordinates,
        projection: GridProjection | None = None,
    ) -> None:
        self._coordinates = coordinates
        self._projection = projection
        self._shape = coordinates.shape

        # Determine if the grid is regular (1D coords) or curvilinear (2D)
        self._is_regular = (
            coordinates.lats.ndim == 1 and coordinates.lons.ndim == 1
        )

        # Pre-compute grid spacing for regular grids (used in inverse mapping)
        if self._is_regular:
            lats = coordinates.lats
            lons = coordinates.lons
            # Compute increments from coordinate arrays
            if len(lats) > 1:
                self._dlat = float(lats[1] - lats[0])
            else:
                self._dlat = 1.0
            if len(lons) > 1:
                self._dlon = float(lons[1] - lons[0])
            else:
                self._dlon = 1.0
            self._lat0 = float(lats[0])
            self._lon0 = float(lons[0])

    @property
    def is_regular(self) -> bool:
        """Whether the grid uses regular (rectilinear) 1D coordinates."""
        return self._is_regular

    @property
    def shape(self) -> tuple[int, ...]:
        """Grid shape (ny, nx)."""
        return self._shape

    def grid_to_native(
        self, i: IndexLike, j: IndexLike
    ) -> tuple[np.ndarray | float, np.ndarray | float]:
        """Map grid indices to native CRS coordinates.

        For regular lat-lon grids, this performs a direct lookup into
        the 1D coordinate vectors. For curvilinear grids, this indexes
        into the 2D coordinate arrays.

        Parameters
        ----------
        i : int or np.ndarray
            Row index/indices (latitude dimension, 0-based).
        j : int or np.ndarray
            Column index/indices (longitude dimension, 0-based).

        Returns
        -------
        tuple[float | np.ndarray, float | np.ndarray]
            (x_native, y_native) — for regular_ll grids this is (lon, lat).
            x corresponds to the column (j) dimension (longitude),
            y corresponds to the row (i) dimension (latitude).
        """
        lats = self._coordinates.lats
        lons = self._coordinates.lons

        if self._is_regular:
            # 1D coordinate vectors — simple indexing
            y_native = lats[i]
            x_native = lons[j]
        else:
            # 2D coordinate arrays — index with (i, j) pair
            y_native = lats[i, j]
            x_native = lons[i, j]

        return x_native, y_native

    def native_to_grid(
        self, x: CoordLike, y: CoordLike
    ) -> tuple[np.ndarray | int, np.ndarray | int]:
        """Map native CRS coordinates to nearest grid indices.

        For regular grids, uses efficient index arithmetic. For
        curvilinear grids, computes distances against the full 2D
        coordinate arrays.

        Parameters
        ----------
        x : float or np.ndarray
            Native x-coordinate(s) (longitude for regular_ll grids).
        y : float or np.ndarray
            Native y-coordinate(s) (latitude for regular_ll grids).

        Returns
        -------
        tuple[int | np.ndarray, int | np.ndarray]
            (i, j) — row and column indices of the nearest grid point.
            i is the latitude-dimension index, j is the longitude-dimension index.
        """
        if self._is_regular:
            return self._native_to_grid_regular(x, y)
        else:
            return self._native_to_grid_curvilinear(x, y)

    def _native_to_grid_regular(
        self, x: CoordLike, y: CoordLike
    ) -> tuple[np.ndarray | int, np.ndarray | int]:
        """Inverse mapping for regular grids using index arithmetic."""
        lats = self._coordinates.lats
        lons = self._coordinates.lons

        # Handle longitude wrapping: if the grid uses 0-360 but input is -180..180
        x_arr = np.asarray(x, dtype=np.float64)
        if self._lon0 >= 0 and float(lons[-1]) > 180:
            # Grid is 0-360, wrap negative longitudes
            x_arr = np.where(x_arr < 0, x_arr + 360, x_arr)

        # Compute fractional indices
        i_frac = (np.asarray(y) - self._lat0) / self._dlat
        j_frac = (x_arr - self._lon0) / self._dlon

        # Round to nearest and clip to valid range
        i = np.clip(np.round(i_frac).astype(int), 0, len(lats) - 1)
        j = np.clip(np.round(j_frac).astype(int), 0, len(lons) - 1)

        # Return scalar if inputs were scalar
        if np.ndim(y) == 0 and np.ndim(x) == 0:
            return int(i), int(j)
        return i, j

    def _native_to_grid_curvilinear(
        self, x: CoordLike, y: CoordLike
    ) -> tuple[np.ndarray | int, np.ndarray | int]:
        """Inverse mapping for curvilinear grids using distance minimization."""
        lats = self._coordinates.lats
        lons = self._coordinates.lons

        x_arr = np.atleast_1d(np.asarray(x, dtype=np.float64))
        y_arr = np.atleast_1d(np.asarray(y, dtype=np.float64))

        results_i = np.empty(x_arr.shape, dtype=int)
        results_j = np.empty(x_arr.shape, dtype=int)

        for idx in range(x_arr.size):
            query_x = x_arr.flat[idx]
            query_y = y_arr.flat[idx]

            # Handle longitude wrapping: compute the shortest angular distance
            # This handles both 0-360 and -180..180 grids correctly
            lon_diff = lons - query_x
            # Wrap to [-180, 180] for shortest-path distance
            lon_diff = (lon_diff + 180) % 360 - 180

            dist_sq = (lats - query_y) ** 2 + lon_diff ** 2
            min_idx = np.argmin(dist_sq)
            i_val, j_val = np.unravel_index(min_idx, lats.shape)
            results_i.flat[idx] = i_val
            results_j.flat[idx] = j_val

        # Return scalar if inputs were scalar
        if np.ndim(x) == 0 and np.ndim(y) == 0:
            return int(results_i.flat[0]), int(results_j.flat[0])
        return results_i.reshape(x_arr.shape), results_j.reshape(x_arr.shape)

    def get_grid_meshgrid(self) -> tuple[np.ndarray, np.ndarray]:
        """Return full 2D meshgrid of coordinates (lons_2d, lats_2d).

        For regular grids, constructs 2D arrays via np.meshgrid from
        the 1D vectors. For curvilinear grids, returns the existing
        2D coordinate arrays directly.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            (lons_2d, lats_2d) — 2D arrays of shape (ny, nx).
        """
        lats = self._coordinates.lats
        lons = self._coordinates.lons

        if self._is_regular:
            # Build 2D meshgrid from 1D vectors.
            # np.meshgrid with indexing='ij' maps (lat, lon) → (ny, nx)
            lats_2d, lons_2d = np.meshgrid(lats, lons, indexing="ij")
        else:
            # Already 2D
            lats_2d = lats
            lons_2d = lons

        return lons_2d, lats_2d
