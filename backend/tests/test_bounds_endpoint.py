"""Tests verifying GET /api/bounds returns correct geographic extent for GEFS-Aerosols.

Validates that:
1. The bounds endpoint returns a valid GeoJSON Feature with Polygon geometry
2. The bounding box aligns with expected global extent for GEFS-Aerosols data:
   - lat_min close to -90, lat_max close to 90
   - lon_min close to -180, lon_max close to 180
3. Grid metadata (grid_type, shape) is included in properties

Mocks the FieldSelector to avoid S3/real data access — uses synthetic
GEFS-Aerosols-like coordinates (regular_ll, 0.25° spacing, 0-360 longitude).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.data.field_selector import GridCoordinates, GridProjection
from backend.app.main import app


# --------------------------------------------------------------------------
# Synthetic GEFS-Aerosols fixtures
# --------------------------------------------------------------------------


def _make_gefs_aerosols_projection() -> GridProjection:
    """Create a synthetic GEFS-Aerosols projection (regular_ll, 0-360 lon)."""
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


def _make_gefs_aerosols_coordinates() -> GridCoordinates:
    """Create synthetic GEFS-Aerosols coordinates.

    Uses a reduced grid (73 lats x 144 lons at 2.5° spacing) for speed
    while preserving the 0-360 longitude convention and global coverage.
    """
    lats = np.linspace(-90.0, 90.0, 73)
    lons = np.linspace(0.0, 357.5, 144)
    return GridCoordinates(lats=lats, lons=lons, shape=(73, 144))


def _make_mock_field_selector() -> MagicMock:
    """Create a mock FieldSelector that returns synthetic GEFS-Aerosols data."""
    mock_selector = MagicMock()
    mock_selector.get_coordinates.return_value = _make_gefs_aerosols_coordinates()
    mock_selector.get_projection.return_value = _make_gefs_aerosols_projection()
    return mock_selector


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@pytest.mark.anyio
class TestBoundsEndpoint:
    """Integration tests for GET /api/bounds with mocked GEFS-Aerosols data."""

    async def test_bounds_returns_200(self):
        """Bounds endpoint returns 200 for valid parameters."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        assert response.status_code == 200

    async def test_bounds_is_geojson_feature(self):
        """Response is a valid GeoJSON Feature with Polygon geometry."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        assert data["type"] == "Feature"
        assert "geometry" in data
        assert data["geometry"]["type"] == "Polygon"
        assert "coordinates" in data["geometry"]
        # A Polygon has a list of rings; the outer ring is first
        coords = data["geometry"]["coordinates"]
        assert len(coords) == 1  # one ring
        ring = coords[0]
        assert len(ring) == 5  # closed polygon: 4 corners + repeat first
        assert ring[0] == ring[-1]  # ring is closed

    async def test_bounds_geographic_extent_latitude(self):
        """Bounding box latitude covers approximately -90 to 90."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        props = data["properties"]

        # Latitude should span the full globe
        assert props["lat_min"] == pytest.approx(-90.0, abs=1.0)
        assert props["lat_max"] == pytest.approx(90.0, abs=1.0)

    async def test_bounds_geographic_extent_longitude(self):
        """Bounding box longitude spans approximately -180 to 180 after normalization."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        props = data["properties"]

        # After 0-360 → -180-180 normalization, longitudes should span
        # nearly the full globe. The minimum should be near -180 and
        # maximum near 180.
        assert props["lon_min"] >= -180.0
        assert props["lon_max"] <= 180.0
        # The span should be > 350° (nearly full circle)
        lon_span = props["lon_max"] - props["lon_min"]
        assert lon_span > 350.0

    async def test_bounds_grid_type_property(self):
        """Properties include grid_type matching the projection."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        props = data["properties"]
        assert props["grid_type"] in ("regular_ll", "regular_gg")

    async def test_bounds_shape_property(self):
        """Properties include grid shape matching synthetic coordinates."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        props = data["properties"]
        assert props["shape"] == [73, 144]

    async def test_bounds_polygon_corners_match_extent(self):
        """Polygon corners in geometry match the reported extent properties."""
        mock_selector = _make_mock_field_selector()

        with patch(
            "backend.app.api.bounds.get_field_selector",
            return_value=mock_selector,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/bounds",
                    params={"product": "air", "date": "20240101", "run": "00"},
                )

        data = response.json()
        props = data["properties"]
        ring = data["geometry"]["coordinates"][0]

        # Ring should be: [SW, SE, NE, NW, SW]
        # Each point is [lon, lat]
        lon_min = props["lon_min"]
        lon_max = props["lon_max"]
        lat_min = props["lat_min"]
        lat_max = props["lat_max"]

        assert ring[0] == [lon_min, lat_min]  # SW
        assert ring[1] == [lon_max, lat_min]  # SE
        assert ring[2] == [lon_max, lat_max]  # NE
        assert ring[3] == [lon_min, lat_max]  # NW
        assert ring[4] == ring[0]             # closed
