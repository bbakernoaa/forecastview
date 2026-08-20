"""Standalone verification script for GEFS-Aerosols data pipeline.

Exercises the full data pipeline with real data from the noaa-gefs-pds
S3 bucket and prints comprehensive diagnostics.

Usage:
    conda run -n forecastview python backend/scripts/verify_field.py

This script:
1. Discovers available dates/runs from S3
2. Opens a dataset with a single forecast hour (fhr=0)
3. Selects the totAOD550 variable (Total AOD at 550nm)
4. Prints field statistics, grid info, and projection metadata
5. Validates basic field properties (shape, value range, coord extents)
"""

from __future__ import annotations

import sys
import time


def main() -> int:
    """Run the field verification pipeline."""
    print("=" * 70)
    print("GEFS-Aerosols Field Verification Script")
    print("=" * 70)

    # Import here so import errors are visible
    from backend.app.data.field_selector import FieldSelector
    from backend.app.data.kerchunk_store import KerchunkStore
    from backend.app.utils.field_stats import print_field_stats, summarize_field
    from backend.app.utils.grid_inspector import get_grid_info, print_grid_info

    # --- Step 1: Initialize store with single forecast hour ---
    print("\n[1/6] Initializing KerchunkStore (fhr=0 only)...")
    t0 = time.perf_counter()
    store = KerchunkStore(forecast_hours=[0])
    selector = FieldSelector(store)
    print(f"       Done in {time.perf_counter() - t0:.2f}s")

    # --- Step 2: Discover available dates/runs ---
    print("\n[2/6] Discovering available dates from S3...")
    t0 = time.perf_counter()
    dates = store.discover_dates()
    elapsed = time.perf_counter() - t0
    if not dates:
        print("       ERROR: No dates discovered. S3 may be unreachable.")
        return 1
    print(f"       Found {len(dates)} dates in {elapsed:.2f}s")
    print(f"       Most recent: {dates[-1]}")

    # Use the most recent date
    date = dates[-1]
    print(f"\n       Discovering runs for {date}...")
    runs = store.discover_runs(date)
    if not runs:
        print(f"       ERROR: No runs found for {date}")
        return 1
    print(f"       Available runs: {runs}")
    run = runs[0]
    print(f"       Using: date={date}, run={run}")

    # --- Step 3: Open dataset and select field ---
    print("\n[3/6] Selecting field: totAOD550 (fhr=0)...")
    t0 = time.perf_counter()
    try:
        field = selector.select(
            date=date,
            run=run,
            variable="totAOD550",
            fhr=0,
        )
    except Exception as exc:
        print(f"       ERROR: Failed to select field: {exc}")
        return 1
    elapsed = time.perf_counter() - t0
    print(f"       Field extracted in {elapsed:.2f}s")
    print(f"       Shape: {field.shape}")

    # --- Step 4: Print field statistics ---
    print("\n[4/6] Field Statistics:")
    print_field_stats(field, variable_name="totAOD550", units="Numeric")

    # --- Step 5: Extract and print grid info ---
    print("\n[5/6] Grid / Coordinate Information:")
    t0 = time.perf_counter()
    try:
        coords = selector.get_coordinates(
            date=date,
            run=run,
            variable="totAOD550",
        )
    except Exception as exc:
        print(f"       ERROR: Failed to extract coordinates: {exc}")
        return 1

    try:
        projection = selector.get_projection(date=date, run=run)
    except Exception as exc:
        print(f"       WARNING: Could not extract projection: {exc}")
        projection = None

    print_grid_info(coords, projection)
    print(f"       Coordinates extracted in {time.perf_counter() - t0:.2f}s")

    # --- Step 6: Validate expected properties ---
    print("\n[6/6] Validation Checks:")
    print("-" * 40)

    stats = summarize_field(field, variable_name="totAOD550")
    info = get_grid_info(coords, projection)
    all_passed = True

    # Check 1: Shape
    rows, cols = field.shape
    shape_ok = rows > 100 and cols > 100
    _print_check("Field shape > 100x100", shape_ok, f"{rows}x{cols}")
    all_passed &= shape_ok

    # Check 2: AOD non-negative
    min_ok = stats["min"] >= 0
    _print_check("AOD min >= 0", min_ok, f"min={stats['min']:.6g}")
    all_passed &= min_ok

    # Check 3: AOD reasonable max
    max_ok = stats["max"] < 10
    _print_check("AOD max < 10", max_ok, f"max={stats['max']:.6g}")
    all_passed &= max_ok

    # Check 4: Latitude range
    lat_ok = info["lat_min"] <= -85 and info["lat_max"] >= 85
    _print_check(
        "Lat range ~[-90, 90]",
        lat_ok,
        f"[{info['lat_min']:.2f}, {info['lat_max']:.2f}]",
    )
    all_passed &= lat_ok

    # Check 5: Longitude range (0-360 convention)
    lon_ok = info["lon_min"] >= -1 and info["lon_max"] <= 361
    lon_span = info["lon_max"] - info["lon_min"]
    _print_check(
        "Lon range ~[0, 360]",
        lon_ok,
        f"[{info['lon_min']:.2f}, {info['lon_max']:.2f}] (span={lon_span:.1f})",
    )
    all_passed &= lon_ok

    # Check 6: Grid type
    grid_type_ok = info["grid_type"] in ("regular_ll", "regular_gg", "reduced_gg")
    _print_check(
        "Grid type is regular",
        grid_type_ok,
        f"type={info['grid_type']}",
    )
    all_passed &= grid_type_ok

    # --- Summary ---
    print()
    print("=" * 70)
    if all_passed:
        print("  ALL CHECKS PASSED")
    else:
        print("  SOME CHECKS FAILED")
    print("=" * 70)

    return 0 if all_passed else 1


def _print_check(label: str, passed: bool, detail: str) -> None:
    """Print a single validation check result."""
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {label}: {detail}")


if __name__ == "__main__":
    sys.exit(main())
