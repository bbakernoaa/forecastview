#!/usr/bin/env python
"""Transform a GEFS-Aerosols field's coordinate grid from native CRS to geographic lon/lat.

This script demonstrates the full coordinate transform pipeline:
1. Open a real GEFS-Aerosols dataset (single fhr=0) via Kerchunk/S3
2. Extract grid coordinates and projection metadata
3. Create CoordinateMapper and CoordinateTransformer
4. Transform the full grid to geographic (lon/lat) coordinates
5. Print before/after statistics and verify geographic extent

Intended for manual execution with real S3 data access:
    conda run -n forecastview python -m backend.scripts.transform_grid

Or from the project root:
    conda run -n forecastview python backend/scripts/transform_grid.py
"""

from __future__ import annotations

import sys
import time

import numpy as np

from backend.app.data.field_selector import FieldSelector
from backend.app.data.kerchunk_store import KerchunkStore
from backend.app.projections.coordinates import CoordinateMapper
from backend.app.projections.transform import CoordinateTransformer


def main() -> int:
    """Run the coordinate grid transform demonstration."""
    print("=" * 70)
    print("GEFS-Aerosols Grid Transform: Native CRS → Geographic (lon/lat)")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # 1. Open dataset
    # -------------------------------------------------------------------------
    print("\n[1/5] Opening GEFS-Aerosols dataset (fhr=0)...")

    store = KerchunkStore(forecast_hours=[0])
    selector = FieldSelector(store)

    # Discover the most recent available date/run
    dates = selector.get_dates()
    if not dates:
        print("ERROR: No dates available. Check S3 connectivity.")
        return 1

    date = dates[-1]  # Most recent date
    runs = selector.get_runs(date)
    if not runs:
        print(f"ERROR: No runs available for date={date}.")
        return 1

    run = runs[-1]  # Most recent run
    print(f"  Using date={date}, run={run}")

    # -------------------------------------------------------------------------
    # 2. Extract coordinates and projection
    # -------------------------------------------------------------------------
    print("\n[2/5] Extracting grid coordinates and projection metadata...")

    t_start = time.perf_counter()

    coordinates = selector.get_coordinates(date, run)
    projection = selector.get_projection(date, run)

    t_extract = time.perf_counter()
    print(f"  Extraction time: {t_extract - t_start:.3f}s")
    print(f"  Grid type: {projection.grid_type}")
    print(f"  CRS string: {projection.to_crs_string()}")
    print(f"  Grid shape: {coordinates.shape}")
    print(f"  Lat array shape: {coordinates.lats.shape}")
    print(f"  Lon array shape: {coordinates.lons.shape}")

    # -------------------------------------------------------------------------
    # 3. Create CoordinateMapper and CoordinateTransformer
    # -------------------------------------------------------------------------
    print("\n[3/5] Creating CoordinateMapper and CoordinateTransformer...")

    mapper = CoordinateMapper(coordinates, projection)
    transformer = CoordinateTransformer.from_projection(projection)

    print(f"  Grid is regular: {mapper.is_regular}")
    print(f"  Transform is no-op: {transformer.is_noop}")

    # -------------------------------------------------------------------------
    # 4. Transform the full grid to geographic coordinates
    # -------------------------------------------------------------------------
    print("\n[4/5] Transforming coordinate grid to geographic (lon/lat)...")

    t_transform_start = time.perf_counter()

    # Get the full 2D meshgrid from the mapper
    lons_native, lats_native = mapper.get_grid_meshgrid()

    # Transform to geographic
    lons_geo, lats_geo = transformer.transform_grid(lons_native, lats_native)

    t_transform_end = time.perf_counter()
    print(f"  Transform time: {t_transform_end - t_transform_start:.3f}s")

    # -------------------------------------------------------------------------
    # 5. Print before/after statistics and verify
    # -------------------------------------------------------------------------
    print("\n[5/5] Before/After Statistics:")
    print("-" * 50)
    print("  BEFORE (native CRS):")
    print(f"    Longitude range: [{lons_native.min():.4f}, {lons_native.max():.4f}]")
    print(f"    Latitude range:  [{lats_native.min():.4f}, {lats_native.max():.4f}]")
    print(f"    Grid shape:      {lons_native.shape}")
    print()
    print("  AFTER (geographic lon/lat):")
    print(f"    Longitude range: [{lons_geo.min():.4f}, {lons_geo.max():.4f}]")
    print(f"    Latitude range:  [{lats_geo.min():.4f}, {lats_geo.max():.4f}]")
    print(f"    Grid shape:      {lons_geo.shape}")
    print()

    # -------------------------------------------------------------------------
    # Verification checks
    # -------------------------------------------------------------------------
    print("  VERIFICATION:")
    all_ok = True

    # Check longitude range
    if lons_geo.min() >= -180.0 and lons_geo.max() <= 180.0:
        print("    [PASS] Transformed longitudes are in [-180, 180] range")
    else:
        print("    [FAIL] Transformed longitudes OUT OF [-180, 180] range!")
        all_ok = False

    # Check latitude range
    if lats_geo.min() >= -90.0 and lats_geo.max() <= 90.0:
        print("    [PASS] Transformed latitudes are in [-90, 90] range")
    else:
        print("    [FAIL] Transformed latitudes OUT OF [-90, 90] range!")
        all_ok = False

    # Check latitude unchanged (for regular_ll grid)
    if transformer.is_noop:
        lat_diff = np.abs(lats_geo - lats_native).max()
        if lat_diff < 1e-10:
            print(f"    [PASS] Latitudes unchanged (max diff: {lat_diff:.2e})")
        else:
            print(f"    [FAIL] Latitudes changed (max diff: {lat_diff:.2e})")
            all_ok = False

    # Check shape preserved
    if lons_geo.shape == lons_native.shape:
        print(f"    [PASS] Grid shape preserved: {lons_geo.shape}")
    else:
        print(f"    [FAIL] Grid shape changed: {lons_native.shape} → {lons_geo.shape}")
        all_ok = False

    # Check no NaNs
    if not np.any(np.isnan(lons_geo)) and not np.any(np.isnan(lats_geo)):
        print("    [PASS] No NaN values in transformed coordinates")
    else:
        print("    [FAIL] NaN values found in transformed coordinates!")
        all_ok = False

    # Expected geographic extent for global GEFS-Aerosols
    lon_span = lons_geo.max() - lons_geo.min()
    if lon_span > 350.0:
        print(f"    [PASS] Longitude span covers near-global extent ({lon_span:.1f}°)")
    else:
        print(f"    [WARN] Longitude span may be narrower than expected ({lon_span:.1f}°)")

    # Corner coordinates
    print()
    print("  CORNER COORDINATES (geographic):")
    print(f"    SW (i=0, j=0):   lat={lats_geo[0, 0]:.4f}, lon={lons_geo[0, 0]:.4f}")
    print(f"    SE (i=0, j=-1):  lat={lats_geo[0, -1]:.4f}, lon={lons_geo[0, -1]:.4f}")
    print(f"    NW (i=-1, j=0):  lat={lats_geo[-1, 0]:.4f}, lon={lons_geo[-1, 0]:.4f}")
    print(f"    NE (i=-1, j=-1): lat={lats_geo[-1, -1]:.4f}, lon={lons_geo[-1, -1]:.4f}")

    print()
    print("=" * 70)
    if all_ok:
        print("RESULT: All verification checks PASSED")
    else:
        print("RESULT: Some verification checks FAILED")
    print("=" * 70)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
