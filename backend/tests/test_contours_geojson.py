"""Tests for contour vertex mapping on non-separable coordinate grids."""

import numpy as np

from backend.app.contours.geojson import _transform_vertices
from backend.app.data.field_selector import GridCoordinates
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer


def test_contour_vertex_uses_full_curvilinear_coordinate_arrays():
    coords = GridCoordinates(
        lons=np.array([[0.0, 2.0], [1.0, 3.0]]),
        lats=np.array([[0.0, 1.0], [2.0, 3.0]]),
        shape=(2, 2),
    )
    mapper = CoordinateMapper(coords)
    transformer = CoordinateTransformer("EPSG:4326")

    longitude, latitude = _transform_vertices(
        np.array([[0.5, 0.5]]), mapper, transformer
    )

    np.testing.assert_allclose(longitude, [1.5])
    np.testing.assert_allclose(latitude, [1.5])
