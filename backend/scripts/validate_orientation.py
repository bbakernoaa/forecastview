"""Orientation validation script for GEFS-Aerosols geographic alignment.

Selects a Dust AOD (duAOD550) field from the GEFS-Aerosols dataset and
generates a reference matplotlib/cartopy plot to validate geographic
orientation (no mirroring, rotation, or offset errors).

Field choice rationale:
    duAOD550 (Dust Aerosol Optical Depth at 550nm) is chosen because the
    Saharan dust plume creates a visually distinctive spatial pattern that
    serves as a clear geographic orientation marker. High dust AOD values
    are expected over North Africa / the Sahara Desert (approximately
    15-30°N, 0-30°E) and the Arabian Peninsula. This recognizable pattern
    allows quick visual confirmation that the field is correctly oriented
    on the map.

Usage:
    conda run -n forecastview python backend/scripts/validate_orientation.py

Output:
    - Reference plot saved to output/validation/dust_aod_reference.png
    - Human-readable summary printed to stdout
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Expected spatial features for duAOD550 orientation validation
EXPECTED_FEATURES = """
Expected Spatial Features (duAOD550 — Dust AOD at 550nm):
  - HIGH values over Sahara / North Africa:  ~15-30°N, ~345-030°E (0-360 convention)
  - HIGH values over Arabian Peninsula:      ~18-30°N, ~035-060°E
  - HIGH values over East Asian dust sources: ~35-45°N, ~075-110°E (Taklamakan/Gobi)
  - LOW values over oceans (except downwind plumes)
  - LOW values over polar regions

If the high-value region over North Africa appears in the correct
position (~center-left of a global plot, in the Northern Hemisphere),
then the field is correctly oriented (no mirroring or rotation).
"""

# Variable configuration
VALIDATION_VARIABLE = "duAOD550"
VALIDATION_VARIABLE_LABEL = "Dust Aerosol Optical Depth at 550nm"
FALLBACK_VARIABLE = "totAOD550"
FALLBACK_VARIABLE_LABEL = "Total Aerosol Optical Depth at 550nm"

# Output configuration
OUTPUT_DIR = Path("output/validation")
OUTPUT_FILENAME = "dust_aod_reference.png"


def main() -> int:
    """Run the orientation validation pipeline."""
    print("=" * 70)
    print("GEFS-Aerosols Orientation Validation")
    print("=" * 70)
    print()
    print("Purpose: Select a field with identifiable spatial features")
    print("         and generate a reference plot for orientation verification.")
    print()

    # Import here so import errors are visible and S3 access is lazy
    try:
        from backend.app.data.field_selector import FieldSelector
        from backend.app.data.kerchunk_store import KerchunkStore
        from backend.app.utils.field_stats import print_field_stats, summarize_field
        from backend.app.utils.grid_inspector import get_grid_info, print_grid_info
        from backend.app.utils.reference_plot import plot_field
    except ImportError as exc:
        print(f"ERROR: Failed to import required modules: {exc}")
        print("       Ensure the forecastview conda environment is active.")
        return 1

    # --- Step 1: Initialize store ---
    print("[1/5] Initializing KerchunkStore (fhr=0 only)...")
    t0 = time.perf_counter()
    store = KerchunkStore(forecast_hours=[0])
    selector = FieldSelector(store)
    print(f"      Done in {time.perf_counter() - t0:.2f}s")

    # --- Step 2: Discover available data ---
    print("\n[2/5] Discovering available dates from S3...")
    t0 = time.perf_counter()
    dates = store.discover_dates()
    elapsed = time.perf_counter() - t0

    if not dates:
        print("      WARNING: No dates discovered — S3 may be unreachable.")
        print("      Skipping validation (no data available).")
        print("\n      To run this validation, ensure network access to the")
        print("      noaa-gefs-pds S3 bucket (anonymous access).")
        return 0  # Graceful skip, not an error

    print(f"      Found {len(dates)} dates in {elapsed:.2f}s")
    print(f"      Most recent: {dates[-1]}")

    date = dates[-1]
    runs = store.discover_runs(date)
    if not runs:
        print(f"      WARNING: No runs found for {date}. Trying earlier date...")
        # Try second-most-recent date if available
        if len(dates) >= 2:
            date = dates[-2]
            runs = store.discover_runs(date)
        if not runs:
            print("      WARNING: No runs available. Skipping validation.")
            return 0

    run = runs[0]
    print(f"      Using: date={date}, run={run}")

    # --- Step 3: Select the validation field ---
    print("\n[3/5] Selecting validation field...")
    variable = VALIDATION_VARIABLE
    variable_label = VALIDATION_VARIABLE_LABEL

    t0 = time.perf_counter()
    try:
        field = selector.select(
            date=date,
            run=run,
            variable=variable,
            fhr=0,
        )
        print(f"      Selected: {variable} ({variable_label})")
    except (ValueError, RuntimeError) as exc:
        print(f"      WARNING: {variable} not available: {exc}")
        print(f"      Trying fallback: {FALLBACK_VARIABLE}...")
        try:
            variable = FALLBACK_VARIABLE
            variable_label = FALLBACK_VARIABLE_LABEL
            field = selector.select(
                date=date,
                run=run,
                variable=variable,
                fhr=0,
            )
            print(f"      Selected fallback: {variable} ({variable_label})")
        except (ValueError, RuntimeError) as exc2:
            print(f"      ERROR: Fallback also failed: {exc2}")
            return 1

    elapsed = time.perf_counter() - t0
    print(f"      Field shape: {field.shape}")
    print(f"      Extracted in {elapsed:.2f}s")

    # Print field statistics
    print()
    print_field_stats(field, variable_name=variable, units="Numeric (dimensionless)")

    # --- Step 4: Extract coordinates and generate reference plot ---
    print("\n[4/5] Generating reference plot...")
    t0 = time.perf_counter()

    try:
        coords = selector.get_coordinates(date=date, run=run, variable=variable)
    except (ValueError, RuntimeError) as exc:
        print(f"      ERROR: Failed to extract coordinates: {exc}")
        return 1

    try:
        projection = selector.get_projection(date=date, run=run)
    except Exception as exc:
        print(f"      WARNING: Could not extract projection: {exc}")
        projection = None

    # Print grid info for reference
    print_grid_info(coords, projection)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILENAME

    # Generate the reference plot
    try:
        crs_string = projection.to_crs_string() if projection else None
        plot_field(
            field,
            coords.lats,
            coords.lons,
            title=f"Orientation Validation: {variable_label}\n"
            f"Date: {date}, Run: {run}Z, FHR: 000",
            units="AOD (dimensionless)",
            crs_string=crs_string,
            cmap="YlOrRd",
            output_path=str(output_path),
            show=False,
        )
        print(f"      Reference plot saved to: {output_path}")
    except Exception as exc:
        print(f"      ERROR: Failed to generate plot: {exc}")
        print("      (matplotlib/cartopy may not be available in this environment)")
        return 1

    elapsed = time.perf_counter() - t0
    print(f"      Plot generated in {elapsed:.2f}s")

    # --- Step 5: Print validation summary ---
    print("\n[5/5] Orientation Validation Summary")
    print("=" * 70)
    print()
    print(f"  Variable selected:  {variable}")
    print(f"  Full name:          {variable_label}")
    print(f"  Date / Run:         {date} / {run}Z")
    print("  Forecast hour:      000 (analysis)")
    print(f"  Field shape:        {field.shape}")
    print()
    print("  Rationale for field choice:")
    print("    Dust AOD shows a distinctive spatial pattern (Saharan dust plume)")
    print("    that is easily recognizable on a map. If the high-value region")
    print("    appears over North Africa (15-30°N, ~0-30°E), the data is")
    print("    correctly oriented with no mirroring or rotation errors.")
    print()
    print(EXPECTED_FEATURES)

    # Quick orientation check from the data
    summarize_field(field, variable_name=variable)
    grid_info = get_grid_info(coords, projection)

    print("  Grid Orientation Check:")
    print(f"    Latitude ordering:      {grid_info['orientation']}")
    print(f"    Longitude convention:   {grid_info['lon_convention']}")
    print(f"    Latitude extent:        [{grid_info['lat_min']:.2f}, {grid_info['lat_max']:.2f}]")
    print(f"    Longitude extent:       [{grid_info['lon_min']:.2f}, {grid_info['lon_max']:.2f}]")
    print()
    print(f"  Reference plot:           {output_path}")
    print()
    print("  Next step: Compare this reference plot against the web viewer's")
    print("  rendering of the same field to confirm geographic alignment.")
    print()
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
