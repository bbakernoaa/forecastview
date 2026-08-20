"""Tests for the full grid-transform pipeline: CoordinateMapper → CoordinateTransformer.

Verifies that a synthetic GEFS-Aerosols-like field (regular_ll, 0-360 longitude
convention, 0.25° resolution) correctly transforms to geographic lon/lat with
longitudes in -180 to 180 range and latitudes unchanged.

No S3 or real data access — all data is synthetic.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.data.field_selector import GridCoordinates, GridProjection
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer

# ---------------------------------------------------------------------------
# Fixtures mimicking GEFS-Aerosols grid (regular_ll, 0.25°, global, 0–360 lon)
# ---------------------------------------------------------------------------


@pytest.fixture
def gefs_aerosols_projection() -> GridProjection:
    """GEFS-Aerosols projection: regular_ll with 0-360 longitude convention."""
    return GridProjection(
        grid_type="regular_ll",
        crs_params={
            "latitudeOfFirstGridPointInDegrees": -90.0,
            "longitudeOfFirstGridPointInDegrees": 0.0,
            "latitudeOfLastGridPointInDegrees": 90.0,
            "longitudeOfLastGridPointInDegrees": 359.75,
            "iDirectionIncrementInDegrees": 0.25,
            "jDirectionIncrementInDegrees": 0.25,
        },
        scanning_mode={
            "iScansNegatively": 0,
            "jScansPositively": 1,
            "jPointsAreConsecutive": 0,
        },
    )


@pytest.fixture
def gefs_aerosols_coordinates() -> GridCoordinates:
    """Synthetic GEFS-Aerosols coordinates: 721 lats x 1440 lons, 0.25° spacing.

    Uses a smaller subset (73 lats x 144 lons at 2.5° spacing) for speed
    while preserving the same structure and lon range (0-360).
    """
    # Reduced grid mimicking full structure: 2.5° resolution for fast tests
    lats = np.linspace(-90.0, 90.0, 73)  # 73 points, -90 to 90
    lons = np.linspace(0.0, 357.5, 144)  # 144 points, 0 to 357.5 (0-360 range)
    return GridCoordinates(lats=lats, lons=lons, shape=(73, 144))


@pytest.fixture
def gefs_mapper(gefs_aerosols_coordinates, gefs_aerosols_projection):
    """CoordinateMapper configured for GEFS-Aerosols grid."""
    return CoordinateMapper(gefs_aerosols_coordinates, gefs_aerosols_projection)


@pytest.fixture
def gefs_transformer(gefs_aerosols_projection):
    """CoordinateTransformer configured for GEFS-Aerosols (regular_ll → EPSG:4326)."""
    return CoordinateTransformer.from_projection(gefs_aerosols_projection)


# ---------------------------------------------------------------------------
# Test: Longitude normalization from 0-360 to -180-180
# ---------------------------------------------------------------------------


class TestLongitudeNormalization:
    """Verify that 0-360 longitude grid is correctly normalized to -180-180."""

    def test_full_grid_lon_range_before_transform(self, gefs_mapper):
        """Original grid longitudes should be in 0-360 range."""
        lons_2d, _ = gefs_mapper.get_grid_meshgrid()
        assert lons_2d.min() >= 0.0
        assert lons_2d.max() < 360.0

    def test_full_grid_lon_range_after_transform(self, gefs_mapper, gefs_transformer):
        """After transform, longitudes should be in -180 to 180 range."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, _ = gefs_transformer.transform_grid(lons_2d, lats_2d)

        assert lons_geo.min() >= -180.0
        assert lons_geo.max() <= 180.0

    def test_specific_lon_values_transformed(self, gefs_transformer):
        """Specific 0-360 longitudes should map to expected -180-180 values."""
        # Single points across the 0-360 range
        test_cases = [
            (0.0, 0.0),  # 0 → 0
            (90.0, 90.0),  # 90 → 90
            (180.0, 180.0),  # 180 → 180 (boundary)
            (181.0, -179.0),  # 181 → -179
            (270.0, -90.0),  # 270 → -90
            (359.0, -1.0),  # 359 → -1
        ]
        for lon_native, lon_expected in test_cases:
            lon_geo, _ = gefs_transformer.native_to_geographic(lon_native, 0.0)
            assert lon_geo == pytest.approx(
                lon_expected
            ), f"Expected {lon_native}° → {lon_expected}°, got {lon_geo}°"

    def test_no_longitudes_in_forbidden_range(self, gefs_mapper, gefs_transformer):
        """No longitude in the transformed grid should exceed 180 or be below -180."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, _ = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # Check that ALL values are within [-180, 180]
        assert np.all(lons_geo >= -180.0)
        assert np.all(lons_geo <= 180.0)


# ---------------------------------------------------------------------------
# Test: Latitude values are unchanged
# ---------------------------------------------------------------------------


class TestLatitudePassthrough:
    """Verify that latitude values are unchanged by the transform (no-op for regular_ll)."""

    def test_latitude_unchanged_scalar(self, gefs_transformer):
        """Single latitude value passes through unchanged."""
        _, lat_geo = gefs_transformer.native_to_geographic(0.0, 45.0)
        assert lat_geo == pytest.approx(45.0)

    def test_latitude_unchanged_negative(self, gefs_transformer):
        """Negative latitude passes through unchanged."""
        _, lat_geo = gefs_transformer.native_to_geographic(100.0, -30.0)
        assert lat_geo == pytest.approx(-30.0)

    def test_full_grid_lats_unchanged(self, gefs_mapper, gefs_transformer):
        """All latitude values in the grid should be unchanged after transform."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        _, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        np.testing.assert_allclose(lats_geo, lats_2d, atol=1e-10)

    def test_lat_range_preserved(self, gefs_mapper, gefs_transformer):
        """Latitude range (-90 to 90) is preserved after transform."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        _, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        assert lats_geo.min() == pytest.approx(-90.0)
        assert lats_geo.max() == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# Test: Full pipeline (CoordinateMapper.get_grid_meshgrid → transform_grid)
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test the complete pipeline: meshgrid → transform → geographic output."""

    def test_output_shape_matches_grid(self, gefs_mapper, gefs_transformer):
        """Transformed grid output should have shape (ny, nx) = (73, 144)."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        assert lons_geo.shape == (73, 144)
        assert lats_geo.shape == (73, 144)

    def test_output_shape_matches_input(self, gefs_mapper, gefs_transformer):
        """Output shape should match input meshgrid shape."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        assert lons_geo.shape == lons_2d.shape
        assert lats_geo.shape == lats_2d.shape

    def test_transform_is_noop_for_regular_ll(self, gefs_transformer):
        """Regular_ll projection should be detected as no-op (only lon normalization)."""
        assert gefs_transformer.is_noop is True

    def test_geographic_extent_covers_globe(self, gefs_mapper, gefs_transformer):
        """Transformed grid should cover the full globe: lat -90..90, lon spans ~360°."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # Full latitude coverage
        assert lats_geo.min() == pytest.approx(-90.0)
        assert lats_geo.max() == pytest.approx(90.0)

        # Longitude should span nearly 360° (from -180 to ~177.5)
        lon_span = lons_geo.max() - lons_geo.min()
        assert lon_span > 350.0  # Nearly full circle

    def test_no_nans_in_output(self, gefs_mapper, gefs_transformer):
        """No NaN values should appear in the transformed grid."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        assert not np.any(np.isnan(lons_geo))
        assert not np.any(np.isnan(lats_geo))


# ---------------------------------------------------------------------------
# Test: Corner coordinates of the transformed grid
# ---------------------------------------------------------------------------


class TestCornerCoordinates:
    """Verify corner coordinates of the transformed GEFS-Aerosols grid."""

    def test_southwest_corner(self, gefs_mapper, gefs_transformer):
        """SW corner: (i=0, j=0) → lat=-90, lon=0 (no normalization needed)."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # (i=0, j=0): lat=-90, lon=0
        assert lats_geo[0, 0] == pytest.approx(-90.0)
        assert lons_geo[0, 0] == pytest.approx(0.0)

    def test_southeast_corner(self, gefs_mapper, gefs_transformer):
        """SE corner: (i=0, j=-1) → lat=-90, lon=357.5 → -2.5 after normalization."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # (i=0, j=-1): lat=-90, lon from 357.5 → -2.5
        assert lats_geo[0, -1] == pytest.approx(-90.0)
        assert lons_geo[0, -1] == pytest.approx(-2.5)

    def test_northwest_corner(self, gefs_mapper, gefs_transformer):
        """NW corner: (i=-1, j=0) → lat=90, lon=0."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # (i=-1, j=0): lat=90, lon=0
        assert lats_geo[-1, 0] == pytest.approx(90.0)
        assert lons_geo[-1, 0] == pytest.approx(0.0)

    def test_northeast_corner(self, gefs_mapper, gefs_transformer):
        """NE corner: (i=-1, j=-1) → lat=90, lon=357.5 → -2.5."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # (i=-1, j=-1): lat=90, lon from 357.5 → -2.5
        assert lats_geo[-1, -1] == pytest.approx(90.0)
        assert lons_geo[-1, -1] == pytest.approx(-2.5)

    def test_midpoint_transformed_correctly(self, gefs_mapper, gefs_transformer):
        """Midpoint of the grid (equator, 180°) transforms correctly.

        lon=180 is on the boundary: should remain 180 (not > 180).
        """
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, lats_geo = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # Find equator row (lat=0, which is row index 36 in our 73-point grid)
        equator_idx = 36
        assert lats_geo[equator_idx, 0] == pytest.approx(0.0)

        # lon=180 is at column index 72 (180/2.5 = 72)
        lon_180_idx = 72
        # lon=180 stays as 180 (boundary, not > 180)
        assert lons_geo[equator_idx, lon_180_idx] == pytest.approx(180.0)

    def test_prime_meridian_column(self, gefs_mapper, gefs_transformer):
        """Column at prime meridian (lon=0) should have lon_geo=0 throughout."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, _ = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # Column 0 is the prime meridian (lon=0)
        np.testing.assert_allclose(lons_geo[:, 0], 0.0)

    def test_western_hemisphere_after_transform(self, gefs_mapper, gefs_transformer):
        """Longitudes > 180 in native grid should map to negative (western hemisphere)."""
        lons_2d, lats_2d = gefs_mapper.get_grid_meshgrid()
        lons_geo, _ = gefs_transformer.transform_grid(lons_2d, lats_2d)

        # Native lons > 180 start at column index 73 (182.5°)
        # These should all be negative in the transformed grid
        western_lons = lons_geo[:, 73:]
        assert np.all(western_lons < 0.0)
