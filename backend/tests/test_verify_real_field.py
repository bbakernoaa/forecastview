"""Integration test: verify one real GEFS-Aerosols field from S3.

Exercises the full data pipeline (KerchunkStore → FieldSelector → field
extraction + coordinate extraction) against the real noaa-gefs-pds S3
bucket and validates field shape, value range, and coordinate extent.

Marked with @pytest.mark.integration so it is skipped in standard CI runs.
Run manually with:
    conda run -n forecastview pytest backend/tests/test_verify_real_field.py -m integration -v
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.data.field_selector import FieldSelector
from backend.app.data.kerchunk_store import KerchunkStore
from backend.app.utils.field_stats import print_field_stats, summarize_field
from backend.app.utils.grid_inspector import get_grid_info, print_grid_info


def _try_discover_date_and_run(store: KerchunkStore) -> tuple[str, str] | None:
    """Attempt to discover an available date/run from S3.

    Returns (date, run) tuple or None if S3 is unreachable or empty.
    """
    dates = store.discover_dates()
    if not dates:
        return None

    # Try the most recent date first (most likely to have data)
    for date in reversed(dates[-3:]):
        runs = store.discover_runs(date)
        if runs:
            return date, runs[0]

    return None


@pytest.mark.integration
class TestVerifyRealField:
    """Integration tests that hit the real noaa-gefs-pds S3 bucket."""

    @pytest.fixture(autouse=True)
    def setup_store(self):
        """Create a KerchunkStore with a single forecast hour to minimize traffic."""
        self.store = KerchunkStore(forecast_hours=[0])
        self.selector = FieldSelector(self.store)

        # Discover an available date/run or skip the whole class
        result = _try_discover_date_and_run(self.store)
        if result is None:
            pytest.skip(
                "S3 bucket noaa-gefs-pds is unreachable or has no available data"
            )
        self.date, self.run = result

    def test_field_shape_is_reasonable(self):
        """The extracted field has > 100 rows and > 100 cols (global grid)."""
        field = self.selector.select(
            date=self.date,
            run=self.run,
            variable="totAOD550",
            fhr=0,
        )

        # Print diagnostics for manual inspection
        print_field_stats(field, variable_name="totAOD550", units="Numeric")

        assert field.ndim == 2, f"Expected 2D field, got {field.ndim}D"
        rows, cols = field.shape
        assert rows > 100, f"Expected > 100 rows, got {rows}"
        assert cols > 100, f"Expected > 100 cols, got {cols}"

    def test_aod_values_non_negative(self):
        """AOD (Aerosol Optical Depth) values are non-negative."""
        field = self.selector.select(
            date=self.date,
            run=self.run,
            variable="totAOD550",
            fhr=0,
        )

        stats = summarize_field(field, variable_name="totAOD550")
        min_val = stats["min"]

        assert min_val >= 0, (
            f"AOD should be non-negative, but min value is {min_val}"
        )

    def test_aod_values_within_reasonable_range(self):
        """AOD max value is within a reasonable upper bound (< 10)."""
        field = self.selector.select(
            date=self.date,
            run=self.run,
            variable="totAOD550",
            fhr=0,
        )

        stats = summarize_field(field, variable_name="totAOD550")
        max_val = stats["max"]

        assert max_val < 10, (
            f"AOD should be < 10 for reasonable atmospheric conditions, "
            f"but max value is {max_val}"
        )

    def test_coordinate_latitude_range(self):
        """Latitude coordinates span approximately -90 to 90."""
        coords = self.selector.get_coordinates(
            date=self.date,
            run=self.run,
            variable="totAOD550",
        )

        # Print grid diagnostics
        print_grid_info(coords)

        lat_min = float(np.nanmin(coords.lats))
        lat_max = float(np.nanmax(coords.lats))

        # Allow some tolerance for grid cell centers not reaching exact poles
        assert lat_min <= -85, (
            f"Expected lat_min <= -85, got {lat_min}"
        )
        assert lat_max >= 85, (
            f"Expected lat_max >= 85, got {lat_max}"
        )

    def test_coordinate_longitude_range(self):
        """Longitude coordinates span approximately 0 to 360 (GRIB2 convention)."""
        coords = self.selector.get_coordinates(
            date=self.date,
            run=self.run,
            variable="totAOD550",
        )

        lon_min = float(np.nanmin(coords.lons))
        lon_max = float(np.nanmax(coords.lons))

        # GRIB2 convention: 0-360
        assert lon_min >= -1, (
            f"Expected lon_min >= -1 (0-360 convention), got {lon_min}"
        )
        assert lon_max <= 361, (
            f"Expected lon_max <= 361 (0-360 convention), got {lon_max}"
        )
        # Should span most of the globe
        assert (lon_max - lon_min) > 350, (
            f"Expected longitude span > 350 degrees, got {lon_max - lon_min}"
        )

    def test_projection_info(self):
        """Projection metadata is available and grid type is regular."""
        projection = self.selector.get_projection(
            date=self.date,
            run=self.run,
        )

        print(f"\n  Grid type: {projection.grid_type}")
        print(f"  CRS string: {projection.to_crs_string()}")
        print(f"  Scanning mode: {projection.scanning_mode}")
        print(f"  CRS params: {projection.crs_params}")

        # GEFS-Aerosols should be a regular lat-lon or Gaussian grid
        assert projection.grid_type in (
            "regular_ll",
            "regular_gg",
            "reduced_gg",
        ), f"Unexpected grid type: {projection.grid_type}"

    def test_grid_info_diagnostics(self):
        """Grid info utility produces valid diagnostics for the real dataset."""
        coords = self.selector.get_coordinates(
            date=self.date,
            run=self.run,
            variable="totAOD550",
        )
        projection = self.selector.get_projection(
            date=self.date,
            run=self.run,
        )

        info = get_grid_info(coords, projection)

        # Validate grid info dictionary
        ny, nx = info["shape"]
        assert ny > 100 and nx > 100
        assert info["lat_min"] < info["lat_max"]
        assert info["lon_min"] < info["lon_max"]
        assert info["orientation"] in ("N→S", "S→N")
        assert info["lon_convention"] in ("0-360", "-180-180")
        assert info["grid_type"] is not None
        assert info["crs_string"] is not None

        # Print full grid diagnostics for manual review
        print_grid_info(coords, projection)
