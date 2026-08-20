"""Reference plotting utility for scientific validation.

Generates matplotlib/cartopy plots of 2D forecast fields for visual
validation against the web viewer's contour placement and geographic
alignment (NFR-13).

These plots serve as independent reference computations during
development and are not part of the production rendering pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np


def plot_field(
    field: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    title: str | None = None,
    units: str | None = None,
    crs_string: str | None = None,
    cmap: str = "viridis",
    output_path: str | Path | None = None,
    show: bool = True,
) -> None:
    """Create a filled contour plot with cartopy geographic features.

    Parameters
    ----------
    field : np.ndarray
        2D numpy array of field values.
    lats : np.ndarray
        Latitude values. 1D (regular grid) or 2D (curvilinear grid).
    lons : np.ndarray
        Longitude values. 1D (regular grid) or 2D (curvilinear grid).
    title : str, optional
        Plot title.
    units : str, optional
        Units string for the colorbar label.
    crs_string : str, optional
        CRS string for the data projection (e.g. "EPSG:4326" or a proj4
        string). If None, assumes PlateCarree (regular lat-lon).
    cmap : str
        Matplotlib colormap name. Default is "viridis".
    output_path : str or Path, optional
        If provided, saves the figure to this path. Supports PNG, PDF, SVG.
    show : bool
        If True, displays the plot interactively. Default is True.
    """
    data_crs = _parse_crs(crs_string)
    lons_2d, lats_2d = _ensure_2d(lons, lats)

    fig, ax = plt.subplots(
        figsize=(12, 8),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    cf = ax.contourf(
        lons_2d,
        lats_2d,
        field,
        levels=20,
        cmap=cmap,
        transform=data_crs,
        extend="both",
    )

    _add_geographic_features(ax)
    _add_colorbar(fig, cf, units=units)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    ax.set_global()
    ax.set_extent(
        _compute_extent(lons_2d, lats_2d),
        crs=ccrs.PlateCarree(),
    )

    plt.tight_layout()
    _save_or_show(fig, output_path, show)


def plot_contours(
    field: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    interval: float | None = None,
    title: str | None = None,
    units: str | None = None,
    crs_string: str | None = None,
    cmap: str = "coolwarm",
    output_path: str | Path | None = None,
    show: bool = True,
) -> None:
    """Create an isoline-only plot for contour validation.

    Parameters
    ----------
    field : np.ndarray
        2D numpy array of field values.
    lats : np.ndarray
        Latitude values. 1D (regular grid) or 2D (curvilinear grid).
    lons : np.ndarray
        Longitude values. 1D (regular grid) or 2D (curvilinear grid).
    interval : float, optional
        Contour interval. If None, matplotlib selects levels automatically.
    title : str, optional
        Plot title.
    units : str, optional
        Units string for labeling contour values.
    crs_string : str, optional
        CRS string for the data projection. If None, assumes PlateCarree.
    cmap : str
        Matplotlib colormap name for contour line colors. Default is
        "coolwarm".
    output_path : str or Path, optional
        If provided, saves the figure to this path.
    show : bool
        If True, displays the plot interactively. Default is True.
    """
    data_crs = _parse_crs(crs_string)
    lons_2d, lats_2d = _ensure_2d(lons, lats)

    fig, ax = plt.subplots(
        figsize=(12, 8),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    # Determine contour levels
    levels = _compute_levels(field, interval)

    cs = ax.contour(
        lons_2d,
        lats_2d,
        field,
        levels=levels,
        cmap=cmap,
        linewidths=0.8,
        transform=data_crs,
    )

    ax.clabel(cs, inline=True, fontsize=8, fmt="%.4g")

    _add_geographic_features(ax)

    label = "Contour Value"
    if units:
        label = f"{label} [{units}]"
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    ax.set_extent(
        _compute_extent(lons_2d, lats_2d),
        crs=ccrs.PlateCarree(),
    )

    plt.tight_layout()
    _save_or_show(fig, output_path, show)


def plot_comparison(
    field: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    *,
    title: str | None = None,
    units: str | None = None,
    interval: float | None = None,
    crs_string: str | None = None,
    cmap: str = "viridis",
    output_path: str | Path | None = None,
    show: bool = True,
) -> None:
    """Create a side-by-side plot (filled + contours) for quick validation.

    Parameters
    ----------
    field : np.ndarray
        2D numpy array of field values.
    lats : np.ndarray
        Latitude values. 1D (regular grid) or 2D (curvilinear grid).
    lons : np.ndarray
        Longitude values. 1D (regular grid) or 2D (curvilinear grid).
    title : str, optional
        Overall figure title.
    units : str, optional
        Units string for colorbar label.
    interval : float, optional
        Contour interval for the isoline panel. If None, auto-selected.
    crs_string : str, optional
        CRS string for the data projection. If None, assumes PlateCarree.
    cmap : str
        Matplotlib colormap name. Default is "viridis".
    output_path : str or Path, optional
        If provided, saves the figure to this path.
    show : bool
        If True, displays the plot interactively. Default is True.
    """
    data_crs = _parse_crs(crs_string)
    lons_2d, lats_2d = _ensure_2d(lons, lats)
    extent = _compute_extent(lons_2d, lats_2d)

    fig, (ax_filled, ax_contour) = plt.subplots(
        1,
        2,
        figsize=(18, 7),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    # Left panel: filled contours
    cf = ax_filled.contourf(
        lons_2d,
        lats_2d,
        field,
        levels=20,
        cmap=cmap,
        transform=data_crs,
        extend="both",
    )
    _add_geographic_features(ax_filled)
    _add_colorbar(fig, cf, units=units, ax=ax_filled)
    ax_filled.set_title("Filled Contours", fontsize=12)
    ax_filled.set_extent(extent, crs=ccrs.PlateCarree())

    # Right panel: isolines
    levels = _compute_levels(field, interval)
    cs = ax_contour.contour(
        lons_2d,
        lats_2d,
        field,
        levels=levels,
        cmap="coolwarm",
        linewidths=0.8,
        transform=data_crs,
    )
    ax_contour.clabel(cs, inline=True, fontsize=8, fmt="%.4g")
    _add_geographic_features(ax_contour)
    ax_contour.set_title("Contour Lines", fontsize=12)
    ax_contour.set_extent(extent, crs=ccrs.PlateCarree())

    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    plt.tight_layout()
    _save_or_show(fig, output_path, show)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _parse_crs(crs_string: str | None) -> ccrs.Projection:
    """Convert a CRS string to a cartopy projection.

    Supports EPSG:4326 (PlateCarree) and proj4 strings for Lambert
    Conformal, Polar Stereographic, and Mercator projections.

    Falls back to PlateCarree for unrecognized or None CRS strings.
    """
    if crs_string is None or crs_string == "EPSG:4326":
        return ccrs.PlateCarree()

    # Parse proj4-style strings
    if "+proj=" in crs_string:
        params = _parse_proj4(crs_string)
        proj_type = params.get("proj", "")

        if proj_type == "lcc":
            return ccrs.LambertConformal(
                central_longitude=float(params.get("lon_0", 0)),
                central_latitude=float(params.get("lat_0", 0)),
                standard_parallels=(
                    float(params.get("lat_1", 25)),
                    float(params.get("lat_2", 25)),
                ),
            )

        if proj_type == "stere":
            return ccrs.Stereographic(
                central_latitude=float(params.get("lat_0", 90)),
                central_longitude=float(params.get("lon_0", 0)),
                true_scale_latitude=float(params.get("lat_ts", 60)),
            )

        if proj_type == "merc":
            return ccrs.Mercator(
                latitude_true_scale=float(params.get("lat_ts", 0)),
            )

    # Fallback
    return ccrs.PlateCarree()


def _parse_proj4(proj4_string: str) -> dict[str, str]:
    """Parse a proj4 string into a key-value dictionary."""
    params: dict[str, str] = {}
    for token in proj4_string.split():
        if token.startswith("+"):
            token = token[1:]
        if "=" in token:
            key, value = token.split("=", 1)
            params[key] = value
        else:
            params[token] = "true"
    return params


def _ensure_2d(lons: np.ndarray, lats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Expand 1D coordinate arrays to 2D meshgrid if needed."""
    if lons.ndim == 1 and lats.ndim == 1:
        lons_2d, lats_2d = np.meshgrid(lons, lats)
        return lons_2d, lats_2d
    return lons, lats


def _compute_extent(lons: np.ndarray, lats: np.ndarray, pad: float = 1.0) -> list[float]:
    """Compute map extent [west, east, south, north] with padding."""
    lon_min = float(np.nanmin(lons))
    lon_max = float(np.nanmax(lons))
    lat_min = float(np.nanmin(lats))
    lat_max = float(np.nanmax(lats))

    return [
        max(lon_min - pad, -180.0),
        min(lon_max + pad, 180.0),
        max(lat_min - pad, -90.0),
        min(lat_max + pad, 90.0),
    ]


def _compute_levels(field: np.ndarray, interval: float | None) -> int | np.ndarray:
    """Compute contour levels from an interval, or fall back to auto."""
    if interval is None:
        return 15

    vmin = float(np.nanmin(field))
    vmax = float(np.nanmax(field))

    if vmin == vmax or not np.isfinite(vmin) or not np.isfinite(vmax):
        return 15

    # Generate levels from vmin to vmax at the specified interval
    start = np.ceil(vmin / interval) * interval
    stop = np.floor(vmax / interval) * interval
    levels = np.arange(start, stop + interval * 0.5, interval)

    # Ensure we have at least 2 levels for contour to work
    if len(levels) < 2:
        return 15

    return levels


def _add_geographic_features(ax: Any) -> None:
    """Add standard cartopy geographic features to an axes."""
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8, edgecolor="black")
    ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor="gray")
    ax.add_feature(cfeature.STATES, linewidth=0.3, edgecolor="gray", linestyle="--")
    ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)


def _add_colorbar(
    fig: Any,
    mappable: Any,
    *,
    units: str | None = None,
    ax: Any | None = None,
) -> None:
    """Add a colorbar to the figure."""
    label = units if units else ""
    if ax is not None:
        fig.colorbar(mappable, ax=ax, orientation="horizontal", pad=0.05, label=label)
    else:
        fig.colorbar(mappable, orientation="horizontal", pad=0.05, label=label)


def _save_or_show(
    fig: Any,
    output_path: str | Path | None,
    show: bool,
) -> None:
    """Save figure to file and/or display it."""
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=150, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)
