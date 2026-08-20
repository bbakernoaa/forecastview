"""Tests for coordinate transform modules.

Verifies CoordinateTransformer (native CRS ↔ geographic) and
CoordinateMapper (grid index ↔ native CRS) against known reference
points using synthetic coordinate data. No S3 or real data access.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.data.field_selector import GridCoordinates, GridProjection
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer, _normalize_longitude

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def regular_ll_projection() -> GridProjection:
    """A regular lat-lon projection (EPSG:4326 no-op)."""
    return GridProjection(
        grid_type="regular_ll",
        crs_params={
            "latitudeOfFirstGridPointInDegrees": -90.0,
            "longitudeOfFirstGridPointInDegrees": 0.0,
            "latitudeOfLastGridPointInDegrees": 90.0,
            "longitudeOfLastGridPointInDegrees": 359.0,
            "iDirectionIncrementInDegrees": 1.0,
            "jDirectionIncrementInDegrees": 1.0,
        },
        scanning_mode={},
    )


@pytest.fixture
def lambert_projection() -> GridProjection:
    """A Lambert Conformal Conic projection centered over CONUS."""
    return GridProjection(
        grid_type="lambert",
        crs_params={
            "Latin1InDegrees": 25.0,
            "Latin2InDegrees": 25.0,
            "LaDInDegrees": 25.0,
            "LoVInDegrees": 265.0,
        },
        scanning_mode={},
    )


@pytest.fixture
def regular_grid_coords() -> GridCoordinates:
    """A small 5x8 regular lat-lon grid."""
    lats = np.linspace(30.0, 50.0, 5)  # 5 rows, 30 to 50 deg N
    lons = np.linspace(-120.0, -80.0, 8)  # 8 cols, 120W to 80W
    return GridCoordinates(lats=lats, lons=lons, shape=(5, 8))


@pytest.fixture
def regular_grid_coords_0_360() -> GridCoordinates:
    """A small 4x6 regular grid using 0-360 longitude convention."""
    lats = np.linspace(-10.0, 10.0, 4)
    lons = np.linspace(250.0, 290.0, 6)  # 250-290 in 0-360 → -110 to -70
    return GridCoordinates(lats=lats, lons=lons, shape=(4, 6))


# ---------------------------------------------------------------------------
# CoordinateTransformer: Longitude normalization
# ---------------------------------------------------------------------------


class TestLongitudeNormalization:
    """Test the _normalize_longitude helper function."""

    def test_longitude_270_normalizes_to_minus_90(self):
        """GRIB2 convention: 270° should map to -90°."""
        assert _normalize_longitude(270.0) == pytest.approx(-90.0)

    def test_longitude_0_unchanged(self):
        """0° stays 0°."""
        assert _normalize_longitude(0.0) == pytest.approx(0.0)

    def test_longitude_180_unchanged(self):
        """180° stays 180° (boundary case)."""
        assert _normalize_longitude(180.0) == pytest.approx(180.0)

    def test_longitude_181_normalizes(self):
        """181° should map to -179°."""
        assert _normalize_longitude(181.0) == pytest.approx(-179.0)

    def test_longitude_360_normalizes_to_0(self):
        """360° should map to 0°."""
        assert _normalize_longitude(360.0) == pytest.approx(0.0)

    def test_array_normalization(self):
        """Vectorized normalization on an array."""
        lons = np.array([0.0, 90.0, 180.0, 270.0, 360.0])
        expected = np.array([0.0, 90.0, 180.0, -90.0, 0.0])
        result = _normalize_longitude(lons)
        np.testing.assert_allclose(result, expected)


# ---------------------------------------------------------------------------
# CoordinateTransformer: Regular lat-lon (no-op) round-trip
# ---------------------------------------------------------------------------


class TestTransformerRegularLL:
    """Tests for CoordinateTransformer with regular lat-lon (no-op case)."""

    def test_is_noop(self, regular_ll_projection):
        """Regular lat-lon projection should be detected as no-op."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        assert t.is_noop is True

    def test_native_to_geographic_identity(self, regular_ll_projection):
        """For regular lat-lon, native→geographic is identity (+ lon normalization)."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        lon, lat = t.native_to_geographic(45.0, 30.0)
        assert lon == pytest.approx(45.0)
        assert lat == pytest.approx(30.0)

    def test_round_trip_regular_ll(self, regular_ll_projection):
        """native → geographic → native should be identity for regular lat-lon."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        x_orig, y_orig = -75.0, 40.0
        lon, lat = t.native_to_geographic(x_orig, y_orig)
        x_back, y_back = t.geographic_to_native(lon, lat)
        assert x_back == pytest.approx(x_orig)
        assert y_back == pytest.approx(y_orig)

    def test_0_360_normalization_in_transform(self, regular_ll_projection):
        """Longitude 270 (0-360 convention) normalizes to -90 via transform."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        lon, lat = t.native_to_geographic(270.0, 0.0)
        assert lon == pytest.approx(-90.0)
        assert lat == pytest.approx(0.0)

    def test_origin_maps_correctly(self, regular_ll_projection):
        """(lon=0, lat=0) maps to itself in geographic coordinates."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        lon, lat = t.native_to_geographic(0.0, 0.0)
        assert lon == pytest.approx(0.0)
        assert lat == pytest.approx(0.0)

    def test_array_round_trip(self, regular_ll_projection):
        """Array inputs round-trip correctly."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        x_arr = np.array([-100.0, -90.0, -80.0])
        y_arr = np.array([30.0, 40.0, 50.0])
        lon, lat = t.native_to_geographic(x_arr, y_arr)
        x_back, y_back = t.geographic_to_native(lon, lat)
        np.testing.assert_allclose(x_back, x_arr)
        np.testing.assert_allclose(y_back, y_arr)


# ---------------------------------------------------------------------------
# CoordinateTransformer: Lambert Conformal Conic round-trip
# ---------------------------------------------------------------------------


class TestTransformerLambert:
    """Tests for CoordinateTransformer with Lambert Conformal Conic projection."""

    def test_is_not_noop(self, lambert_projection):
        """Lambert projection should NOT be detected as no-op."""
        t = CoordinateTransformer.from_projection(lambert_projection)
        assert t.is_noop is False

    def test_round_trip_within_1m(self, lambert_projection):
        """Lambert → geographic → Lambert round-trip within 1m tolerance."""
        t = CoordinateTransformer.from_projection(lambert_projection)
        # Start with some native coordinates (meters from projection origin)
        x_native = 500000.0  # 500 km east
        y_native = 1000000.0  # 1000 km north

        # Forward: native → geographic
        lon, lat = t.native_to_geographic(x_native, y_native)

        # Inverse: geographic → native
        x_back, y_back = t.geographic_to_native(lon, lat)

        # Should recover within 1 meter
        assert x_back == pytest.approx(x_native, abs=1.0)
        assert y_back == pytest.approx(y_native, abs=1.0)

    def test_round_trip_multiple_points(self, lambert_projection):
        """Multiple Lambert points round-trip within 1m tolerance."""
        t = CoordinateTransformer.from_projection(lambert_projection)
        x_native = np.array([-200000.0, 0.0, 200000.0, 500000.0])
        y_native = np.array([500000.0, 800000.0, 1200000.0, 300000.0])

        lon, lat = t.native_to_geographic(x_native, y_native)
        x_back, y_back = t.geographic_to_native(lon, lat)

        np.testing.assert_allclose(x_back, x_native, atol=1.0)
        np.testing.assert_allclose(y_back, y_native, atol=1.0)

    def test_geographic_output_is_reasonable(self, lambert_projection):
        """Output lon/lat should be within valid geographic ranges."""
        t = CoordinateTransformer.from_projection(lambert_projection)
        # Point near center of CONUS Lambert domain
        lon, lat = t.native_to_geographic(0.0, 0.0)

        # The projection center should yield coordinates near the reference lat
        assert -180.0 <= lon <= 180.0
        assert -90.0 <= lat <= 90.0


# ---------------------------------------------------------------------------
# CoordinateTransformer: transform_grid (batch operations)
# ---------------------------------------------------------------------------


class TestTransformGrid:
    """Tests for batch coordinate grid transformation."""

    def test_shape_preserved_noop(self, regular_ll_projection):
        """Output grid shape matches input for no-op transform."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        lons = np.linspace(0.0, 60.0, 12).reshape(3, 4)
        lats = np.linspace(20.0, 50.0, 12).reshape(3, 4)

        lons_out, lats_out = t.transform_grid(lons, lats)

        assert lons_out.shape == (3, 4)
        assert lats_out.shape == (3, 4)

    def test_shape_preserved_lambert(self, lambert_projection):
        """Output grid shape matches input for projected transform."""
        t = CoordinateTransformer.from_projection(lambert_projection)
        x = np.linspace(-500000, 500000, 20).reshape(4, 5)
        y = np.linspace(0, 2000000, 20).reshape(4, 5)

        lons_out, lats_out = t.transform_grid(x, y)

        assert lons_out.shape == (4, 5)
        assert lats_out.shape == (4, 5)

    def test_noop_grid_normalization(self, regular_ll_projection):
        """0-360 longitudes in grid get normalized to -180-180."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        lons = np.array([[200.0, 250.0, 300.0], [200.0, 250.0, 300.0]])
        lats = np.array([[10.0, 10.0, 10.0], [20.0, 20.0, 20.0]])

        lons_out, lats_out = t.transform_grid(lons, lats)

        expected_lons = np.array([[-160.0, -110.0, -60.0], [-160.0, -110.0, -60.0]])
        np.testing.assert_allclose(lons_out, expected_lons)
        np.testing.assert_allclose(lats_out, lats)

    def test_1d_input_works(self, regular_ll_projection):
        """1D input arrays also work with transform_grid."""
        t = CoordinateTransformer.from_projection(regular_ll_projection)
        lons = np.array([10.0, 200.0, 350.0])
        lats = np.array([0.0, 45.0, -30.0])

        lons_out, lats_out = t.transform_grid(lons, lats)

        expected_lons = np.array([10.0, -160.0, -10.0])
        np.testing.assert_allclose(lons_out, expected_lons)
        np.testing.assert_allclose(lats_out, lats)


# ---------------------------------------------------------------------------
# CoordinateMapper: grid_to_native for regular grids
# ---------------------------------------------------------------------------


class TestCoordinateMapperGridToNative:
    """Tests for CoordinateMapper.grid_to_native on regular grids."""

    def test_corner_top_left(self, regular_grid_coords):
        """First grid point (i=0, j=0) maps to (lon[0], lat[0])."""
        mapper = CoordinateMapper(regular_grid_coords)
        x, y = mapper.grid_to_native(0, 0)
        assert x == pytest.approx(-120.0)  # lons[0]
        assert y == pytest.approx(30.0)  # lats[0]

    def test_corner_top_right(self, regular_grid_coords):
        """Grid point (i=0, j=7) maps to (lon[7], lat[0])."""
        mapper = CoordinateMapper(regular_grid_coords)
        x, y = mapper.grid_to_native(0, 7)
        assert x == pytest.approx(-80.0)  # lons[7]
        assert y == pytest.approx(30.0)  # lats[0]

    def test_corner_bottom_left(self, regular_grid_coords):
        """Grid point (i=4, j=0) maps to (lon[0], lat[4])."""
        mapper = CoordinateMapper(regular_grid_coords)
        x, y = mapper.grid_to_native(4, 0)
        assert x == pytest.approx(-120.0)  # lons[0]
        assert y == pytest.approx(50.0)  # lats[4]

    def test_corner_bottom_right(self, regular_grid_coords):
        """Grid point (i=4, j=7) maps to (lon[7], lat[4])."""
        mapper = CoordinateMapper(regular_grid_coords)
        x, y = mapper.grid_to_native(4, 7)
        assert x == pytest.approx(-80.0)  # lons[7]
        assert y == pytest.approx(50.0)  # lats[4]

    def test_middle_point(self, regular_grid_coords):
        """Grid point (i=2, j=4) maps to expected (lon[4], lat[2])."""
        mapper = CoordinateMapper(regular_grid_coords)
        x, y = mapper.grid_to_native(2, 4)
        expected_lon = np.linspace(-120.0, -80.0, 8)[4]
        expected_lat = np.linspace(30.0, 50.0, 5)[2]
        assert x == pytest.approx(expected_lon)
        assert y == pytest.approx(expected_lat)

    def test_shape_property(self, regular_grid_coords):
        """Mapper reports correct grid shape."""
        mapper = CoordinateMapper(regular_grid_coords)
        assert mapper.shape == (5, 8)

    def test_is_regular(self, regular_grid_coords):
        """Regular grid is detected as regular."""
        mapper = CoordinateMapper(regular_grid_coords)
        assert mapper.is_regular is True


# ---------------------------------------------------------------------------
# CoordinateMapper: native_to_grid for regular grids
# ---------------------------------------------------------------------------


class TestCoordinateMapperNativeToGrid:
    """Tests for CoordinateMapper.native_to_grid on regular grids."""

    def test_exact_grid_point(self, regular_grid_coords):
        """Exact grid coordinate maps back to the correct index."""
        mapper = CoordinateMapper(regular_grid_coords)
        lats = np.linspace(30.0, 50.0, 5)
        lons = np.linspace(-120.0, -80.0, 8)

        # Point at (i=2, j=3)
        i, j = mapper.native_to_grid(lons[3], lats[2])
        assert i == 2
        assert j == 3

    def test_near_grid_point_snaps(self, regular_grid_coords):
        """Point near a grid node snaps to the nearest index."""
        mapper = CoordinateMapper(regular_grid_coords)
        lats = np.linspace(30.0, 50.0, 5)
        lons = np.linspace(-120.0, -80.0, 8)

        # Slightly offset from (i=1, j=5)
        x_near = lons[5] + 0.1
        y_near = lats[1] + 0.1
        i, j = mapper.native_to_grid(x_near, y_near)
        assert i == 1
        assert j == 5

    def test_clips_to_valid_range(self, regular_grid_coords):
        """Coordinates outside the grid clip to boundary indices."""
        mapper = CoordinateMapper(regular_grid_coords)
        # Way outside the grid
        i, j = mapper.native_to_grid(-200.0, 100.0)
        # Should clip to valid range
        assert 0 <= i <= 4
        assert 0 <= j <= 7

    def test_array_input(self, regular_grid_coords):
        """Array of coordinates returns array of indices."""
        mapper = CoordinateMapper(regular_grid_coords)
        lats = np.linspace(30.0, 50.0, 5)
        lons = np.linspace(-120.0, -80.0, 8)

        x_arr = np.array([lons[0], lons[4], lons[7]])
        y_arr = np.array([lats[0], lats[2], lats[4]])
        i_arr, j_arr = mapper.native_to_grid(x_arr, y_arr)

        np.testing.assert_array_equal(i_arr, [0, 2, 4])
        np.testing.assert_array_equal(j_arr, [0, 4, 7])


# ---------------------------------------------------------------------------
# CoordinateMapper: Round-trip property (grid_to_native → native_to_grid)
# ---------------------------------------------------------------------------


class TestCoordinateMapperRoundTrip:
    """Property: for any valid grid point, grid→native→grid recovers indices."""

    def test_all_points_round_trip(self, regular_grid_coords):
        """Every grid point should round-trip through native coordinates."""
        mapper = CoordinateMapper(regular_grid_coords)
        ny, nx = regular_grid_coords.shape

        for i in range(ny):
            for j in range(nx):
                x, y = mapper.grid_to_native(i, j)
                i_back, j_back = mapper.native_to_grid(x, y)
                assert i_back == i, f"Row mismatch at ({i},{j}): got {i_back}"
                assert j_back == j, f"Col mismatch at ({i},{j}): got {j_back}"

    def test_vectorized_round_trip(self, regular_grid_coords):
        """Vectorized round-trip over all grid points."""
        mapper = CoordinateMapper(regular_grid_coords)
        ny, nx = regular_grid_coords.shape

        # Create arrays of all (i, j) pairs
        ii, jj = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
        i_flat = ii.ravel()
        j_flat = jj.ravel()

        # Forward: grid → native
        x_arr, y_arr = mapper.grid_to_native(i_flat, j_flat)

        # Inverse: native → grid
        i_back, j_back = mapper.native_to_grid(x_arr, y_arr)

        np.testing.assert_array_equal(i_back, i_flat)
        np.testing.assert_array_equal(j_back, j_flat)


# ---------------------------------------------------------------------------
# CoordinateMapper: get_grid_meshgrid
# ---------------------------------------------------------------------------


class TestCoordinateMapperMeshgrid:
    """Tests for CoordinateMapper.get_grid_meshgrid."""

    def test_meshgrid_shape(self, regular_grid_coords):
        """Meshgrid output has correct (ny, nx) shape."""
        mapper = CoordinateMapper(regular_grid_coords)
        lons_2d, lats_2d = mapper.get_grid_meshgrid()
        assert lons_2d.shape == (5, 8)
        assert lats_2d.shape == (5, 8)

    def test_meshgrid_values(self, regular_grid_coords):
        """Meshgrid values match expected lat/lon at corners."""
        mapper = CoordinateMapper(regular_grid_coords)
        lons_2d, lats_2d = mapper.get_grid_meshgrid()

        # Top-left corner
        assert lons_2d[0, 0] == pytest.approx(-120.0)
        assert lats_2d[0, 0] == pytest.approx(30.0)

        # Bottom-right corner
        assert lons_2d[4, 7] == pytest.approx(-80.0)
        assert lats_2d[4, 7] == pytest.approx(50.0)

    def test_meshgrid_lat_constant_along_rows(self, regular_grid_coords):
        """Latitude should be constant along each row for a regular grid."""
        mapper = CoordinateMapper(regular_grid_coords)
        _, lats_2d = mapper.get_grid_meshgrid()

        for i in range(5):
            # All columns in row i should have the same latitude
            assert np.all(lats_2d[i, :] == lats_2d[i, 0])

    def test_meshgrid_lon_constant_along_cols(self, regular_grid_coords):
        """Longitude should be constant along each column for a regular grid."""
        mapper = CoordinateMapper(regular_grid_coords)
        lons_2d, _ = mapper.get_grid_meshgrid()

        for j in range(8):
            # All rows in column j should have the same longitude
            assert np.all(lons_2d[:, j] == lons_2d[0, j])


# ---------------------------------------------------------------------------
# CoordinateMapper: Curvilinear grid support
# ---------------------------------------------------------------------------


class TestCoordinateMapperCurvilinear:
    """Tests for CoordinateMapper with 2D (curvilinear) coordinate arrays."""

    @pytest.fixture
    def curvilinear_coords(self) -> GridCoordinates:
        """A 3x4 curvilinear grid with slight distortion."""
        # Create a slightly curved grid (not perfectly rectilinear)
        lats = np.array(
            [
                [30.0, 30.1, 30.2, 30.3],
                [40.0, 40.1, 40.2, 40.3],
                [50.0, 50.1, 50.2, 50.3],
            ]
        )
        lons = np.array(
            [
                [-120.0, -110.0, -100.0, -90.0],
                [-120.1, -110.1, -100.1, -90.1],
                [-120.2, -110.2, -100.2, -90.2],
            ]
        )
        return GridCoordinates(lats=lats, lons=lons, shape=(3, 4))

    def test_curvilinear_detected(self, curvilinear_coords):
        """2D coordinate arrays are detected as non-regular."""
        mapper = CoordinateMapper(curvilinear_coords)
        assert mapper.is_regular is False

    def test_curvilinear_grid_to_native(self, curvilinear_coords):
        """Index (1, 2) returns correct 2D coordinate values."""
        mapper = CoordinateMapper(curvilinear_coords)
        x, y = mapper.grid_to_native(1, 2)
        assert x == pytest.approx(-100.1)
        assert y == pytest.approx(40.2)

    def test_curvilinear_native_to_grid(self, curvilinear_coords):
        """Known coordinate finds nearest grid index."""
        mapper = CoordinateMapper(curvilinear_coords)
        # Point very near (i=2, j=1) → lat=50.1, lon=-110.2
        i, j = mapper.native_to_grid(-110.2, 50.1)
        assert i == 2
        assert j == 1
