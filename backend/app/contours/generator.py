"""Contour generation module using contourpy for native-grid isoline extraction.

Generates isolines from 2D numpy fields on their native grid. Contour
vertices are returned in grid-index space (column, row), suitable for
subsequent coordinate transformation to geographic (lon/lat) space.

The module operates entirely in native grid coordinates — no reprojection
occurs here. Geographic transformation is handled downstream (geojson.py).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from contourpy import FillType, LineType, contour_generator


@dataclass(frozen=True)
class ContourLine:
    """A single contour isoline at a specific level.

    Attributes
    ----------
    level : float
        The field value this contour represents.
    vertices : list[np.ndarray]
        List of Nx2 arrays of (x, y) coordinates in grid space.
        x corresponds to column index, y to row index (contourpy
        convention: x=column, y=row).
    is_major : bool
        Whether this is a major contour (thicker line, labeled).
    """

    level: float
    vertices: list[np.ndarray] = field(default_factory=list)
    is_major: bool = False


@dataclass(frozen=True)
class ContourResult:
    """Bundled result from contour generation.

    Attributes
    ----------
    lines : list[ContourLine]
        All generated contour lines.
    levels : np.ndarray
        Array of all contour levels that were computed.
    major_levels : np.ndarray
        Array of levels marked as major.
    field_min : float
        Minimum value of the input field (ignoring NaNs).
    field_max : float
        Maximum value of the input field (ignoring NaNs).
    """

    lines: list[ContourLine]
    levels: np.ndarray
    major_levels: np.ndarray
    field_min: float
    field_max: float


def _compute_levels(
    field_min: float,
    field_max: float,
    interval: float | None = None,
    num_levels: int = 10,
) -> np.ndarray:
    """Compute contour levels from field range and interval.

    Parameters
    ----------
    field_min : float
        Minimum field value.
    field_max : float
        Maximum field value.
    interval : float, optional
        Spacing between contour levels. If None, ``num_levels``
        evenly-spaced levels are used.
    num_levels : int
        Number of levels when ``interval`` is not provided.

    Returns
    -------
    np.ndarray
        1D array of contour level values.
    """
    if interval is not None and interval > 0:
        # Compute levels at regular interval aligned to multiples of interval
        first = np.ceil(field_min / interval) * interval
        last = np.floor(field_max / interval) * interval
        if first > last:
            # Interval larger than field range — use midpoint
            return np.array([round((field_min + field_max) / 2, 10)])
        levels = np.arange(first, last + interval * 0.5, interval)
        # Remove levels outside the field range (floating point edge cases)
        levels = levels[(levels >= field_min) & (levels <= field_max)]
        if len(levels) == 0:
            return np.array([round((field_min + field_max) / 2, 10)])
        return levels
    else:
        # Evenly spaced levels (exclude exact min/max for cleaner contours)
        return np.linspace(field_min, field_max, num_levels + 2)[1:-1]


def _determine_major_levels(
    levels: np.ndarray,
    major_interval: float | None = None,
) -> np.ndarray:
    """Determine which levels are major contours.

    Parameters
    ----------
    levels : np.ndarray
        All contour levels.
    major_interval : float, optional
        Interval for major contours. Levels that are multiples of this
        value (within tolerance) are considered major. If None, every
        5th level is major.

    Returns
    -------
    np.ndarray
        Array of major contour level values.
    """
    if major_interval is not None and major_interval > 0:
        # Levels that are near-multiples of major_interval
        remainder = np.abs(np.remainder(levels, major_interval))
        tolerance = major_interval * 1e-9
        is_major = (remainder < tolerance) | (
            np.abs(remainder - major_interval) < tolerance
        )
        return levels[is_major]
    else:
        # Default: every 5th level is major
        if len(levels) <= 5:
            return levels.copy()
        return levels[::5]


def generate_isolines(
    field: np.ndarray,
    levels: list[float] | np.ndarray | None = None,
    interval: float | None = None,
    major_interval: float | None = None,
) -> ContourResult:
    """Generate contour isolines from a 2D field on its native grid.

    Uses contourpy to extract isolines at specified or computed levels.
    Contour vertices are in grid-index space (x=column, y=row) as per
    contourpy conventions.

    Parameters
    ----------
    field : np.ndarray
        2D array of field values on the native grid. May contain NaN
        values for masked regions.
    levels : list[float] or np.ndarray, optional
        Explicit contour levels to generate. If provided, ``interval``
        is ignored.
    interval : float, optional
        Spacing between contour levels. Used to compute levels from
        the field's value range when ``levels`` is not provided.
    major_interval : float, optional
        Interval for major contour designation. Levels that are
        multiples of this value are marked as major contours
        (thicker lines, labeled on the map).

    Returns
    -------
    ContourResult
        Bundled result containing contour lines, levels, field statistics.

    Raises
    ------
    ValueError
        If the input field is not 2D.

    Notes
    -----
    - All-NaN fields return an empty ContourResult.
    - Constant fields (min == max) return an empty ContourResult.
    - Fields smaller than 2x2 return an empty ContourResult.
    - Contour vertices use contourpy's convention: x is column index,
      y is row index. This maps to (j, i) in the grid coordinate system.
    """
    if field.ndim != 2:
        raise ValueError(
            f"Expected 2D field, got shape {field.shape}"
        )

    ny, nx = field.shape

    # Edge case: field too small for contouring
    if ny < 2 or nx < 2:
        return ContourResult(
            lines=[],
            levels=np.array([]),
            major_levels=np.array([]),
            field_min=float("nan"),
            field_max=float("nan"),
        )

    # Compute field statistics (ignoring NaN)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        field_min = float(np.nanmin(field))
        field_max = float(np.nanmax(field))

    # Edge case: all-NaN field
    if np.isnan(field_min) or np.isnan(field_max):
        return ContourResult(
            lines=[],
            levels=np.array([]),
            major_levels=np.array([]),
            field_min=float("nan"),
            field_max=float("nan"),
        )

    # Edge case: constant field (no contours possible)
    if field_min == field_max:
        return ContourResult(
            lines=[],
            levels=np.array([]),
            major_levels=np.array([]),
            field_min=field_min,
            field_max=field_max,
        )

    # Determine contour levels
    if levels is not None:
        contour_levels = np.asarray(levels, dtype=np.float64)
        # Filter levels to those within field range
        contour_levels = contour_levels[
            (contour_levels >= field_min) & (contour_levels <= field_max)
        ]
        contour_levels = np.sort(contour_levels)
    else:
        contour_levels = _compute_levels(field_min, field_max, interval)

    if len(contour_levels) == 0:
        return ContourResult(
            lines=[],
            levels=np.array([]),
            major_levels=np.array([]),
            field_min=field_min,
            field_max=field_max,
        )

    # Determine major levels
    major_levels = _determine_major_levels(contour_levels, major_interval)
    major_set = set(major_levels.tolist())

    # Create contourpy generator
    # x-coordinates = column indices, y-coordinates = row indices
    x = np.arange(nx, dtype=np.float64)
    y = np.arange(ny, dtype=np.float64)

    gen = contour_generator(
        x=x,
        y=y,
        z=field,
        line_type=LineType.SeparateCode,
    )

    # Generate contours at each level
    contour_lines: list[ContourLine] = []

    for level_val in contour_levels:
        level_float = float(level_val)
        # contourpy returns (vertices_list, codes_list) for SeparateCode
        result = gen.lines(level_float)
        vertices_list = result[0]  # list of Nx2 arrays

        # Filter out empty or degenerate segments
        valid_vertices: list[np.ndarray] = []
        for verts in vertices_list:
            if verts is not None and len(verts) >= 2:
                valid_vertices.append(verts)

        is_major = level_float in major_set

        contour_lines.append(
            ContourLine(
                level=level_float,
                vertices=valid_vertices,
                is_major=is_major,
            )
        )

    return ContourResult(
        lines=contour_lines,
        levels=contour_levels,
        major_levels=major_levels,
        field_min=field_min,
        field_max=field_max,
    )


@dataclass(frozen=True)
class FilledContourPolygon:
    """A single filled contour band between two levels.

    Attributes
    ----------
    level_low : float
        Lower bound of the fill band.
    level_high : float
        Upper bound of the fill band.
    polygons : list[np.ndarray]
        List of Nx2 arrays of (x, y) coordinates in grid space.
        Each array represents a polygon ring (outer boundary or hole).
        x corresponds to column index, y to row index (contourpy convention).
    codes : list[np.ndarray]
        Corresponding path codes for each polygon ring. Codes follow
        matplotlib path conventions: 1=MOVETO, 2=LINETO, 79=CLOSEPOLY.
    """

    level_low: float
    level_high: float
    polygons: list[np.ndarray] = field(default_factory=list)
    codes: list[np.ndarray] = field(default_factory=list)


@dataclass(frozen=True)
class FilledContourResult:
    """Bundled result from filled contour generation.

    Attributes
    ----------
    polygons : list[FilledContourPolygon]
        All generated filled contour bands.
    fill_levels : np.ndarray
        Array of level boundaries used for filling.
    field_min : float
        Minimum value of the input field (ignoring NaNs).
    field_max : float
        Maximum value of the input field (ignoring NaNs).
    """

    polygons: list[FilledContourPolygon]
    fill_levels: np.ndarray
    field_min: float
    field_max: float


def generate_filled_contours(
    field: np.ndarray,
    fill_levels: list[float] | np.ndarray | None = None,
) -> FilledContourResult:
    """Generate filled contour polygons from a 2D field on its native grid.

    Uses contourpy with FillType.OuterCode to extract filled polygons
    for each band between consecutive fill levels. Polygon vertices are
    in grid-index space (x=column, y=row) as per contourpy conventions.

    Parameters
    ----------
    field : np.ndarray
        2D array of field values on the native grid. May contain NaN
        values for masked regions.
    fill_levels : list[float] or np.ndarray, optional
        Explicit boundaries for fill bands. Each consecutive pair
        (fill_levels[i], fill_levels[i+1]) defines a fill band.
        If None, 10 evenly-spaced levels spanning the field range
        are computed.

    Returns
    -------
    FilledContourResult
        Bundled result containing filled polygons, levels, field statistics.

    Raises
    ------
    ValueError
        If the input field is not 2D, or if fewer than 2 fill levels
        are provided.

    Notes
    -----
    - All-NaN fields return an empty FilledContourResult.
    - Constant fields (min == max) return an empty FilledContourResult.
    - Fields smaller than 2x2 return an empty FilledContourResult.
    - Polygon vertices use contourpy's convention: x is column index,
      y is row index.
    """
    if field.ndim != 2:
        raise ValueError(f"Expected 2D field, got shape {field.shape}")

    ny, nx = field.shape

    # Edge case: field too small for contouring
    if ny < 2 or nx < 2:
        return FilledContourResult(
            polygons=[],
            fill_levels=np.array([]),
            field_min=float("nan"),
            field_max=float("nan"),
        )

    # Compute field statistics (ignoring NaN)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        field_min = float(np.nanmin(field))
        field_max = float(np.nanmax(field))

    # Edge case: all-NaN field
    if np.isnan(field_min) or np.isnan(field_max):
        return FilledContourResult(
            polygons=[],
            fill_levels=np.array([]),
            field_min=float("nan"),
            field_max=float("nan"),
        )

    # Edge case: constant field (no fill bands possible)
    if field_min == field_max:
        return FilledContourResult(
            polygons=[],
            fill_levels=np.array([]),
            field_min=field_min,
            field_max=field_max,
        )

    # Determine fill levels
    if fill_levels is not None:
        levels = np.asarray(fill_levels, dtype=np.float64)
        levels = np.sort(levels)
    else:
        # Default: 11 boundaries → 10 bands spanning the field range
        levels = np.linspace(field_min, field_max, 11)

    if len(levels) < 2:
        raise ValueError(
            f"Need at least 2 fill levels to define a band, got {len(levels)}"
        )

    # Create contourpy generator with FillType.OuterCode
    x = np.arange(nx, dtype=np.float64)
    y = np.arange(ny, dtype=np.float64)

    gen = contour_generator(
        x=x,
        y=y,
        z=field,
        fill_type=FillType.ChunkCombinedOffsetOffset,
        chunk_size=0,  # No chunking - use full grid
    )

    # Generate filled polygons for each band between consecutive levels
    filled_polygons: list[FilledContourPolygon] = []

    for i in range(len(levels) - 1):
        lower = float(levels[i])
        upper = float(levels[i + 1])

        # contourpy filled returns (points_list, offsets_list, outer_offsets_list)
        # for ChunkCombinedOffsetOffset. Each list element is one chunk.
        result = gen.filled(lower, upper)
        points_list = result[0]
        offsets_list = result[1]
        outer_offsets_list = result[2]

        # Process each chunk: split into individual polygons using outer_offsets
        valid_polygons: list[np.ndarray] = []
        valid_offsets: list[np.ndarray] = []

        for points, offsets, outer_offsets in zip(
            points_list, offsets_list, outer_offsets_list
        ):
            if points is None or len(points) < 3:
                continue

            # Each polygon spans outer_offsets[i] to outer_offsets[i+1] in the offsets array
            for poly_idx in range(len(outer_offsets) - 1):
                ring_start = int(outer_offsets[poly_idx])
                ring_end = int(outer_offsets[poly_idx + 1])

                # Get the ring offsets for this polygon
                poly_ring_offsets = offsets[ring_start:ring_end + 1]

                # Get the vertices for this polygon
                vert_start = int(poly_ring_offsets[0])
                vert_end = int(poly_ring_offsets[-1])
                poly_verts = points[vert_start:vert_end]

                if len(poly_verts) >= 3:
                    # Adjust offsets to be relative to poly_verts start
                    relative_offsets = poly_ring_offsets - vert_start
                    valid_polygons.append(poly_verts)
                    valid_offsets.append(relative_offsets)

        filled_polygons.append(
            FilledContourPolygon(
                level_low=lower,
                level_high=upper,
                polygons=valid_polygons,
                codes=valid_offsets,
            )
        )

    return FilledContourResult(
        polygons=filled_polygons,
        fill_levels=levels,
        field_min=field_min,
        field_max=field_max,
    )
