"""Animated GIF export endpoint.

Generates an animated GIF from all forecast hours for a given variable.
Each frame is the fill-image PNG rendered at a reduced resolution for
reasonable file sizes.
"""

from __future__ import annotations

import time
from io import BytesIO

import numpy as np
import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from matplotlib import colormaps
from PIL import Image, ImageDraw
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

from backend.app.api.dependencies import get_field_selector
from backend.app.config.loader import get_domain_config_safe
from backend.app.contours.geojson import shift_grid_to_minus180

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["export"])

# GIF frame dimensions (smaller than live view for file size)
GIF_WIDTH = 1024
GIF_HEIGHT = 1024

WEB_MERCATOR_MAX_LAT = 85.06
CRS_4326 = CRS.from_epsg(4326)
CRS_3857 = CRS.from_epsg(3857)
MERCATOR_XMIN = -20037508.3427892
MERCATOR_XMAX = 20037508.3427892
MERCATOR_YMIN = -20037508.3427892
MERCATOR_YMAX = 20037508.3427892


def _render_frame(
    field: np.ndarray,
    lons_1d: np.ndarray,
    lats_1d: np.ndarray,
    fill_levels: list[float],
    colormap_name: str,
    fhr: int,
    variable: str,
) -> Image.Image:
    """Render a single frame for the GIF."""
    # Shift grid
    shifted_field, shifted_lons, _ = shift_grid_to_minus180(field, lons_1d)
    if not np.array_equal(shifted_lons, lons_1d):
        field = shifted_field
        lons_1d = shifted_lons

    # Crop to Mercator bounds
    valid_mask = (lats_1d >= -WEB_MERCATOR_MAX_LAT) & (lats_1d <= WEB_MERCATOR_MAX_LAT)
    valid_rows = np.where(valid_mask)[0]
    field = field[valid_rows[0] : valid_rows[-1] + 1, :]
    lats_cropped = lats_1d[valid_rows[0] : valid_rows[-1] + 1]

    src_height, src_width = field.shape
    src_lon_min = float(lons_1d[0])
    src_lon_max = float(lons_1d[-1]) + (float(lons_1d[1]) - float(lons_1d[0]))
    src_lat_min = float(lats_cropped[-1])
    src_lat_max = float(lats_cropped[0])

    src_transform = from_bounds(
        src_lon_min, src_lat_min, src_lon_max, src_lat_max, src_width, src_height
    )
    dst_transform = from_bounds(
        MERCATOR_XMIN,
        MERCATOR_YMIN,
        MERCATOR_XMAX,
        MERCATOR_YMAX,
        GIF_WIDTH,
        GIF_HEIGHT,
    )

    dst_field = np.zeros((GIF_HEIGHT, GIF_WIDTH), dtype=np.float32)
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

    # Classify
    n_levels = len(fill_levels)
    n_bands = n_levels + 1

    try:
        cmap = colormaps[colormap_name]
    except (KeyError, ValueError):
        cmap = colormaps["turbo"]

    rgba_colors = np.zeros((n_bands, 4), dtype=np.uint8)
    rgba_colors[0] = (20, 20, 30, 255)  # dark background for GIF (no transparency in GIF)
    for i in range(n_levels):
        t = i / max(n_levels - 1, 1)
        r, g, b, _ = cmap(t)
        rgba_colors[i + 1] = (int(r * 255), int(g * 255), int(b * 255), 255)

    band_indices = np.digitize(dst_field, fill_levels)
    band_indices[~np.isfinite(dst_field)] = 0

    image_data = rgba_colors[band_indices]
    img = Image.fromarray(image_data.astype(np.uint8), mode="RGBA").convert("RGB")

    # Add label
    draw = ImageDraw.Draw(img)
    label = f"{variable}  F{fhr:03d}"
    draw.rectangle([(0, 0), (200, 22)], fill=(0, 0, 0))
    draw.text((4, 4), label, fill=(255, 255, 255))

    return img


@router.get("/export-gif")
async def export_gif(
    product: str = Query(...),
    date: str = Query(...),
    run: str = Query(...),
    variable: str = Query(...),
    level: float | None = Query(None),
) -> Response:
    """Generate an animated GIF of all forecast hours for a variable."""
    t_start = time.perf_counter()
    logger.info("api.export_gif.request", product=product, variable=variable)

    selector = get_field_selector()

    # Get fill levels and colormap
    domain_config = get_domain_config_safe(product)
    if domain_config is None:
        raise HTTPException(status_code=400, detail=f"Unknown product: {product}")

    var_config = domain_config.get_variable(variable)
    if var_config is None or not var_config.rendering.fillLevels:
        raise HTTPException(status_code=400, detail=f"No rendering config for {variable}")

    fill_levels = var_config.rendering.fillLevels
    colormap_name = var_config.rendering.colormap or "turbo"

    # Discover forecast hours
    fhrs = selector.get_forecast_hours(date, run)
    if not fhrs:
        raise HTTPException(status_code=404, detail="No forecast hours available")

    # Get coordinates once
    coordinates = selector.get_coordinates(date, run)
    lons_1d = coordinates.lons[0, :] if coordinates.lons.ndim == 2 else coordinates.lons
    lats_1d = coordinates.lats[:, 0] if coordinates.lats.ndim == 2 else coordinates.lats

    # Render all frames
    frames: list[Image.Image] = []
    for fhr_entry in fhrs:
        fhr = fhr_entry["fhr"] if isinstance(fhr_entry, dict) else fhr_entry
        try:
            field = selector.select(date, run, variable, level=level, fhr=fhr)
            frame = _render_frame(
                field, lons_1d.copy(), lats_1d, fill_levels, colormap_name, fhr, variable
            )
            frames.append(frame)
        except Exception as exc:
            logger.warning("api.export_gif.frame_failed", fhr=fhr, error=str(exc))
            continue

    if not frames:
        raise HTTPException(status_code=500, detail="No frames could be rendered")

    # Encode as animated GIF
    buf = BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=200,  # ms per frame
        loop=0,  # infinite loop
    )
    gif_bytes = buf.getvalue()

    t_total = time.perf_counter() - t_start
    logger.info(
        "api.export_gif.done",
        variable=variable,
        num_frames=len(frames),
        size_mb=round(len(gif_bytes) / (1024 * 1024), 2),
        timing_s=round(t_total, 1),
    )

    return Response(
        content=gif_bytes,
        media_type="image/gif",
        headers={
            "Content-Disposition": f'attachment; filename="{variable}_{date}_animation.gif"',
        },
    )
