"""Fill image API endpoint — raster PNG with Web Mercator reprojection.

Generates a discrete-classified RGBA PNG of the forecast field, reprojected
from EPSG:4326 (equirectangular) to EPSG:3857 (Web Mercator) so that it
aligns pixel-perfect with MapLibre's basemap tiles.

The colormap and fill levels are read from the domain config (air.yaml)
per variable, so each variable renders with its own color scheme.

The lowest fill band is transparent so the basemap shows through.
"""

from __future__ import annotations

import time
from pathlib import Path
from io import BytesIO

import numpy as np
import structlog
from cachetools import LRUCache
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from matplotlib import colormaps
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from rasterio.crs import CRS

from backend.app.api.dependencies import get_field_selector
from backend.app.config.loader import get_domain_config_safe
from backend.app.contours.geojson import shift_grid_to_minus180

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["fill-image"])

# --------------------------------------------------------------------------
# Web Mercator constants
# --------------------------------------------------------------------------

WEB_MERCATOR_MAX_LAT = 85.06

# Output image dimensions (Web Mercator)
MERCATOR_WIDTH = 2048
MERCATOR_HEIGHT = 2048

CRS_4326 = CRS.from_epsg(4326)
CRS_3857 = CRS.from_epsg(3857)

MERCATOR_XMIN = -20037508.3427892
MERCATOR_XMAX = 20037508.3427892
MERCATOR_YMIN = -20037508.3427892
MERCATOR_YMAX = 20037508.3427892

# --------------------------------------------------------------------------
# Fallback palette if colormap name isn't recognized
# --------------------------------------------------------------------------

FALLBACK_PALETTE = [
    "#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8",
    "#ffffbf", "#fee090", "#fdae61", "#f46d43", "#d73027",
    "#a50026", "#67001f",
]

# --------------------------------------------------------------------------
# Fill image cache
# --------------------------------------------------------------------------

# Path to pre-rendered images (populated by scripts/prerender_images.py)
_RENDERED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "rendered"

_fill_image_cache: LRUCache = LRUCache(maxsize=64)


def _cache_key(date: str, run: str, variable: str, level: float | None, fhr: int) -> tuple:
    return ("fill_image", date, run, variable, level, fhr)


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------


@router.get("/fill-image")
async def get_fill_image(
    product: str = Query(..., description="Product identifier (e.g. 'air')"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
    variable: str = Query(..., description="Variable name"),
    fhr: int = Query(..., description="Forecast hour"),
    level: float | None = Query(None, description="Vertical level value"),
) -> Response:
    """Return a Web Mercator-projected PNG raster of the filled field."""
    t_start = time.perf_counter()

    logger.info("api.fill_image.request", product=product, variable=variable, fhr=fhr)

    # Check for pre-rendered image on disk first
    prerendered_path = _RENDERED_DIR / date / run / variable / f"f{fhr:03d}.png"
    if prerendered_path.exists():
        logger.info("api.fill_image.prerendered", path=str(prerendered_path))
        return Response(
            content=prerendered_path.read_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    # Check in-memory cache
    key = _cache_key(date, run, variable, level, fhr)
    cached = _fill_image_cache.get(key)
    if cached is not None:
        return Response(
            content=cached,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    selector = get_field_selector()

    # Resolve fill levels and colormap from domain config
    fill_levels: list[float] | None = None
    colormap_name: str = "turbo"  # default

    domain_config = get_domain_config_safe(product)
    if domain_config is not None:
        var_config = domain_config.get_variable(variable)
        if var_config is not None:
            if var_config.rendering.fillLevels:
                fill_levels = var_config.rendering.fillLevels
            if var_config.rendering.colormap:
                colormap_name = var_config.rendering.colormap

    if not fill_levels:
        raise HTTPException(
            status_code=400,
            detail=f"No fill levels configured for variable '{variable}'.",
        )

    # --- Step 1: Extract field ---
    try:
        field = selector.select(date, run, variable, level=level, fhr=fhr)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=404, detail=f"Could not select field: {exc}")

    # --- Step 2: Get coordinates ---
    try:
        coordinates = selector.get_coordinates(date, run)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=404, detail=f"Could not get coordinates: {exc}")

    # --- Step 3: Shift grid from 0-360 to -180..180 ---
    lons_1d = coordinates.lons[0, :] if coordinates.lons.ndim == 2 else coordinates.lons
    lats_1d = coordinates.lats[:, 0] if coordinates.lats.ndim == 2 else coordinates.lats

    shifted_field, shifted_lons, _ = shift_grid_to_minus180(field, lons_1d)
    if not np.array_equal(shifted_lons, lons_1d):
        field = shifted_field
        lons_1d = shifted_lons

    t_field = time.perf_counter()

    # --- Step 4: Crop to Web Mercator latitude bounds ---
    valid_mask = (lats_1d >= -WEB_MERCATOR_MAX_LAT) & (lats_1d <= WEB_MERCATOR_MAX_LAT)
    valid_rows = np.where(valid_mask)[0]
    row_start, row_end = valid_rows[0], valid_rows[-1]
    field = field[row_start:row_end + 1, :]
    lats_cropped = lats_1d[row_start:row_end + 1]

    src_height, src_width = field.shape

    src_lon_min = float(lons_1d[0])
    src_lon_max = float(lons_1d[-1]) + (float(lons_1d[1]) - float(lons_1d[0]))
    src_lat_min = float(lats_cropped[-1])
    src_lat_max = float(lats_cropped[0])

    src_transform = from_bounds(
        src_lon_min, src_lat_min, src_lon_max, src_lat_max,
        src_width, src_height,
    )

    # --- Step 5: Reproject field to Web Mercator ---
    dst_transform = from_bounds(
        MERCATOR_XMIN, MERCATOR_YMIN, MERCATOR_XMAX, MERCATOR_YMAX,
        MERCATOR_WIDTH, MERCATOR_HEIGHT,
    )

    dst_field = np.zeros((MERCATOR_HEIGHT, MERCATOR_WIDTH), dtype=np.float32)

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

    t_reproject = time.perf_counter()

    # --- Step 6: Classify into color bands using domain colormap ---
    n_levels = len(fill_levels)
    n_bands = n_levels + 1  # below-min + between-levels + above-max

    # Build RGBA color array from the matplotlib colormap
    try:
        cmap = colormaps[colormap_name]
    except (KeyError, ValueError):
        logger.warning("api.fill_image.unknown_colormap", name=colormap_name)
        cmap = colormaps["turbo"]

    # Color assignment:
    # Band 0 = below fill_levels[0] → transparent (basemap shows through)
    # Band 1..n_levels = colored bands matching the legend
    n_visible_bands = n_levels  # bands 1 through n_levels get colors

    rgba_colors = np.zeros((n_bands, 4), dtype=np.uint8)
    # Band 0: transparent (values below the first fill level)
    rgba_colors[0] = (0, 0, 0, 0)  # transparent for below-min areas

    # Bands 1 through n_levels: sample from colormap
    for i in range(n_visible_bands):
        t = i / max(n_visible_bands - 1, 1)
        r, g, b, a = cmap(t)
        rgba_colors[i + 1] = (int(r * 255), int(g * 255), int(b * 255), 255)


    # Classify field values into bands
    band_indices = np.digitize(dst_field, fill_levels)

    # NaN/invalid → transparent
    invalid_mask = ~np.isfinite(dst_field)
    band_indices[invalid_mask] = 0

    image_data = rgba_colors[band_indices]

    # --- Step 7: Encode as PNG ---
    img = Image.fromarray(image_data.astype(np.uint8), mode="RGBA")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=False)
    png_bytes = buf.getvalue()

    _fill_image_cache[key] = png_bytes

    t_total = time.perf_counter()
    logger.info(
        "api.fill_image.done",
        product=product,
        variable=variable,
        colormap=colormap_name,
        fhr=fhr,
        n_levels=n_levels,
        png_size_kb=round(len(png_bytes) / 1024, 1),
        timing_field_ms=round((t_field - t_start) * 1000, 1),
        timing_reproject_ms=round((t_reproject - t_field) * 1000, 1),
        timing_total_ms=round((t_total - t_start) * 1000, 1),
    )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
