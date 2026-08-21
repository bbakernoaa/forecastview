#!/usr/bin/env python
"""Pre-render fill image PNGs for all variables and forecast hours.

Generates Web Mercator-projected RGBA PNGs for every variable/fhr combination
in the manifest store. The images are saved to a directory structure that the
fill-image API endpoint can serve directly (bypassing on-the-fly generation).

Usage:
    python backend/scripts/prerender_images.py [OPTIONS]

Options:
    --date DATE          Specific date (YYYYMMDD) to render. Default: latest.
    --run RUN            Cycle to render (default: "00")
    --variables VAR,...  Comma-separated variable list. Default: all.
    --output-dir DIR     Output directory. Default: data/tiles/{date}/{run}/
    --workers N          Parallel workers (default: 4)
    --width W            Output image width (default: 2048)
    --height H           Output image height (default: 2048)
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.config.loader import get_domain_config_safe
from backend.app.contours.geojson import shift_grid_to_minus180
from backend.app.data.field_selector import FieldSelector
from backend.app.data.kerchunk_store import ManifestStore

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

WEB_MERCATOR_MAX_LAT = 85.06
CRS_4326 = CRS.from_epsg(4326)
CRS_3857 = CRS.from_epsg(3857)
MERCATOR_XMIN = -20037508.3427892
MERCATOR_XMAX = 20037508.3427892
MERCATOR_YMIN = -20037508.3427892
MERCATOR_YMAX = 20037508.3427892


# --------------------------------------------------------------------------
# Rendering logic (same as fill_image.py endpoint)
# --------------------------------------------------------------------------


def render_fill_image(
    field: np.ndarray,
    lons_1d: np.ndarray,
    lats_1d: np.ndarray,
    fill_levels: list[float],
    colormap_name: str,
    width: int = 2048,
    height: int = 2048,
) -> bytes:
    """Render a single field to a Web Mercator PNG."""
    # Shift grid
    shifted_field, shifted_lons, _ = shift_grid_to_minus180(field, lons_1d)
    if not np.array_equal(shifted_lons, lons_1d):
        field = shifted_field
        lons_1d = shifted_lons

    # Crop to Web Mercator bounds
    valid_mask = (lats_1d >= -WEB_MERCATOR_MAX_LAT) & (lats_1d <= WEB_MERCATOR_MAX_LAT)
    valid_rows = np.where(valid_mask)[0]
    row_start, row_end = valid_rows[0], valid_rows[-1]
    field = field[row_start : row_end + 1, :]
    lats_cropped = lats_1d[row_start : row_end + 1]

    src_height, src_width = field.shape
    src_lon_min = float(lons_1d[0])
    src_lon_max = float(lons_1d[-1]) + (float(lons_1d[1]) - float(lons_1d[0]))
    src_lat_min = float(lats_cropped[-1])
    src_lat_max = float(lats_cropped[0])

    src_transform = from_bounds(
        src_lon_min, src_lat_min, src_lon_max, src_lat_max, src_width, src_height
    )
    dst_transform = from_bounds(
        MERCATOR_XMIN, MERCATOR_YMIN, MERCATOR_XMAX, MERCATOR_YMAX, width, height
    )

    dst_field = np.zeros((height, width), dtype=np.float32)
    reproject(
        source=field.astype(np.float32),
        destination=dst_field,
        src_transform=src_transform,
        src_crs=CRS_4326,
        dst_transform=dst_transform,
        dst_crs=CRS_3857,
        resampling=Resampling.bilinear,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )

    # Classify into color bands
    n_levels = len(fill_levels)
    n_bands = n_levels + 1
    n_visible = n_bands - 2

    try:
        cmap = colormaps[colormap_name]
    except (KeyError, ValueError):
        cmap = colormaps["turbo"]

    rgba_colors = np.zeros((n_bands, 4), dtype=np.uint8)
    rgba_colors[0] = (0, 0, 0, 0)  # below min
    rgba_colors[1] = (0, 0, 0, 0)  # lowest band (transparent)
    for i in range(n_visible):
        t = i / max(n_visible - 1, 1)
        r, g, b, _ = cmap(t)
        rgba_colors[i + 2] = (int(r * 255), int(g * 255), int(b * 255), 255)

    band_indices = np.digitize(dst_field, fill_levels)
    band_indices[~np.isfinite(dst_field)] = 0

    image_data = rgba_colors[band_indices]
    img = Image.fromarray(image_data.astype(np.uint8), mode="RGBA")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_one(args: tuple) -> tuple[str, int, float, int]:
    """Render one variable+fhr combination. Returns (variable, fhr, elapsed_ms, size_bytes)."""
    (
        store_path,
        date,
        run,
        variable,
        fhr,
        fill_levels,
        colormap_name,
        output_dir,
        width,
        height,
    ) = args

    store = ManifestStore(store_path)
    selector = FieldSelector(store)

    t0 = time.perf_counter()

    field = selector.select(date, run, variable, fhr=fhr)
    coords = selector.get_coordinates(date, run)
    lons_1d = coords.lons[0, :] if coords.lons.ndim == 2 else coords.lons
    lats_1d = coords.lats[:, 0] if coords.lats.ndim == 2 else coords.lats

    png_bytes = render_fill_image(
        field, lons_1d, lats_1d, fill_levels, colormap_name, width, height
    )

    # Save to disk
    out_path = Path(output_dir) / variable / f"f{fhr:03d}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png_bytes)

    elapsed = (time.perf_counter() - t0) * 1000
    return (variable, fhr, elapsed, len(png_bytes))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Pre-render fill image PNGs")
    parser.add_argument("--date", type=str, default=None, help="Date (YYYYMMDD)")
    parser.add_argument("--run", type=str, default="00", help="Cycle (default: 00)")
    parser.add_argument(
        "--variables", type=str, default=None, help="Comma-separated variable names"
    )
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--width", type=int, default=2048, help="Image width")
    parser.add_argument("--height", type=int, default=2048, help="Image height")
    parser.add_argument("--product", type=str, default="air", help="Product (default: air)")

    args = parser.parse_args()

    store_path = str(Path(__file__).resolve().parent.parent.parent / "data" / "manifests")
    store = ManifestStore(store_path)

    # Determine date
    if args.date:
        date = args.date
    else:
        dates = store.available_dates()
        if not dates:
            print("ERROR: No dates available in manifest store.")
            sys.exit(1)
        date = sorted(dates)[-1]

    run = args.run

    # Determine variables
    domain_config = get_domain_config_safe(args.product)
    if domain_config is None:
        print(f"ERROR: No domain config for product '{args.product}'")
        sys.exit(1)

    if args.variables:
        variables = args.variables.split(",")
    else:
        # All variables that have fill levels configured
        variables = []
        selector = FieldSelector(store)
        raw_vars = selector.get_variables(date, run)
        for v in raw_vars:
            var_config = domain_config.get_variable(v["name"])
            if var_config and var_config.rendering.fillLevels:
                variables.append(v["name"])

    # Determine forecast hours
    fhrs = store.discover_forecast_hours(date, run)
    if not fhrs:
        print(f"ERROR: No forecast hours for {date}/{run}")
        sys.exit(1)

    # Output directory
    output_dir = args.output_dir or str(
        Path(__file__).resolve().parent.parent.parent / "data" / "rendered" / date / run
    )

    print("=" * 60)
    print("  Fill Image Pre-Renderer")
    print("=" * 60)
    print(f"  Date:       {date}")
    print(f"  Run:        {run}")
    print(f"  Variables:  {len(variables)}")
    print(f"  FHR range:  {min(fhrs)}-{max(fhrs)} ({len(fhrs)} steps)")
    print(f"  Image size: {args.width}x{args.height}")
    print(f"  Workers:    {args.workers}")
    print(f"  Output:     {output_dir}")
    print(f"  Total jobs: {len(variables) * len(fhrs)}")
    print("=" * 60)

    # Build job list
    jobs = []
    for variable in variables:
        var_config = domain_config.get_variable(variable)
        if not var_config or not var_config.rendering.fillLevels:
            continue
        fill_levels = var_config.rendering.fillLevels
        colormap_name = var_config.rendering.colormap or "turbo"

        for fhr in fhrs:
            jobs.append(
                (
                    store_path,
                    date,
                    run,
                    variable,
                    fhr,
                    fill_levels,
                    colormap_name,
                    output_dir,
                    args.width,
                    args.height,
                )
            )

    t_start = time.perf_counter()
    completed = 0
    total_bytes = 0

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(render_one, job): job for job in jobs}
        for future in as_completed(futures):
            try:
                variable, fhr, elapsed_ms, size_bytes = future.result()
                completed += 1
                total_bytes += size_bytes
                if completed % 20 == 0 or completed == len(jobs):
                    pct = 100 * completed / len(jobs)
                    print(
                        f"  [{completed}/{len(jobs)}] {pct:.0f}% "
                        f"(last: {variable} f{fhr:03d} {elapsed_ms:.0f}ms {size_bytes // 1024}KB)"
                    )
            except Exception as exc:
                job = futures[future]
                print(f"  FAILED: {job[3]} f{job[4]:03d}: {exc}")

    t_total = time.perf_counter() - t_start
    print("=" * 60)
    print(f"  Done: {completed}/{len(jobs)} images in {t_total:.1f}s")
    print(f"  Total size: {total_bytes / (1024 * 1024):.1f} MB")
    print(f"  Output: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
