"""Metadata API endpoints for the Air Composition Forecast Viewer.

Provides discovery endpoints for products, dates, runs, variables,
levels, and forecast times. These endpoints drive the frontend
selector components.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from matplotlib import colormaps as mpl_colormaps

from backend.app.api.dependencies import get_field_selector

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["metadata"])


# --------------------------------------------------------------------------
# Pydantic response models
# --------------------------------------------------------------------------


class CatalogEntry(BaseModel):
    """A single product entry in the catalog."""

    product: str = Field(..., description="Product identifier (e.g. 'air')")
    description: str = Field(..., description="Human-readable product name")


class CatalogResponse(BaseModel):
    """Response for GET /api/catalog."""

    products: list[CatalogEntry]


class DatesResponse(BaseModel):
    """Response for GET /api/dates."""

    product: str
    dates: list[str] = Field(
        ..., description="Available dates in YYYYMMDD format"
    )


class RunsResponse(BaseModel):
    """Response for GET /api/runs."""

    product: str
    date: str
    runs: list[str] = Field(
        ..., description="Available initialization cycles (e.g. '00', '06')"
    )


class VariableRenderingInfo(BaseModel):
    """Rendering hints for a variable."""

    colormap: str = Field("rainbow", description="Colormap name")
    contourInterval: float = Field(0.1, description="Default contour interval")
    fillLevels: list[float] = Field(
        default_factory=list, description="Fill level boundaries"
    )
    colors: list[str] = Field(
        default_factory=list,
        description="Hex colors for each fill band (computed from colormap)",
    )


class VariableInfo(BaseModel):
    """Metadata for a single forecast variable."""

    name: str = Field(..., description="Internal variable name (xarray key)")
    shortName: str = Field(..., description="Short display name")
    fullName: str = Field(..., description="Full descriptive name")
    units: str = Field(..., description="Variable units")
    category: str = Field(..., description="Grouping category")
    rendering: VariableRenderingInfo | None = Field(
        None, description="Rendering configuration (from domain config)"
    )


class VariablesResponse(BaseModel):
    """Response for GET /api/variables."""

    product: str
    date: str
    run: str
    variables: list[VariableInfo]


class LevelInfo(BaseModel):
    """Metadata for a single vertical level."""

    surfaceType: int | None = Field(
        None, description="GRIB2 typeOfFirstFixedSurface"
    )
    value: float = Field(..., description="Numeric level value")
    label: str = Field(..., description="Human-readable level description")


class LevelsResponse(BaseModel):
    """Response for GET /api/levels."""

    product: str
    date: str
    run: str
    variable: str
    levels: list[LevelInfo]


class ForecastHourEntry(BaseModel):
    """A single forecast hour with its valid time."""

    fhr: int = Field(..., description="Forecast hour")
    valid_time: str = Field(..., description="ISO-formatted valid time")


class TimesResponse(BaseModel):
    """Response for GET /api/times."""

    product: str
    date: str
    run: str
    init_time: str = Field(..., description="ISO-formatted initialization time")
    forecast_hours: list[ForecastHourEntry]


# --------------------------------------------------------------------------
# Static catalog data
# --------------------------------------------------------------------------


def _compute_band_colors(colormap_name: str, n_levels: int) -> list[str]:
    """Compute hex colors for fill bands from a matplotlib colormap.

    Returns n_levels colors (one per band between adjacent levels,
    plus the below-first-level band). This matches the fill image
    which colors bands 1..n_levels from the colormap.

    The legend shows n_levels-1 visible bands (between adjacent levels).
    colors[0] corresponds to the fill_levels[0]..fill_levels[1] band.
    """
    n_bands = n_levels  # total colored bands in the fill image
    if n_bands <= 0:
        return []

    try:
        cmap = mpl_colormaps[colormap_name]
    except (KeyError, ValueError):
        cmap = mpl_colormaps["turbo"]

    colors = []
    for i in range(n_bands):
        t = i / max(n_bands - 1, 1)
        r, g, b, _ = cmap(t)
        hex_color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        colors.append(hex_color)

    return colors


_CATALOG: list[CatalogEntry] = [
    CatalogEntry(product="air", description="Air Composition"),
]

_VALID_PRODUCTS = {entry.product for entry in _CATALOG}


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------


def _validate_product(product: str) -> None:
    """Raise 404 if product is not in the catalog."""
    if product not in _VALID_PRODUCTS:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product}' not found. Available: {sorted(_VALID_PRODUCTS)}",
        )


def _validate_date(date: str) -> None:
    """Raise 422 if date format is invalid."""
    if len(date) != 8 or not date.isdigit():
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date format: '{date}'. Expected YYYYMMDD.",
        )
    try:
        datetime.strptime(date, "%Y%m%d")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date: '{date}'. Must be a valid calendar date in YYYYMMDD format.",
        )


def _validate_run(run: str) -> None:
    """Raise 422 if run format is invalid."""
    if len(run) != 2 or not run.isdigit():
        raise HTTPException(
            status_code=422,
            detail=f"Invalid run format: '{run}'. Expected two-digit cycle (e.g. '00', '06', '12', '18').",
        )


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog() -> CatalogResponse:
    """Return the list of available forecast products."""
    logger.info("api.catalog.request")
    return CatalogResponse(products=_CATALOG)


@router.get("/dates", response_model=DatesResponse)
async def get_dates(
    product: str = Query(..., description="Product identifier (e.g. 'air')"),
) -> DatesResponse:
    """Return available forecast dates for a product."""
    _validate_product(product)
    logger.info("api.dates.request", product=product)

    selector = get_field_selector()
    dates = selector.get_dates()

    return DatesResponse(product=product, dates=dates)


@router.get("/runs", response_model=RunsResponse)
async def get_runs(
    product: str = Query(..., description="Product identifier"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
) -> RunsResponse:
    """Return available initialization runs for a product and date."""
    _validate_product(product)
    _validate_date(date)
    logger.info("api.runs.request", product=product, date=date)

    selector = get_field_selector()
    runs = selector.get_runs(date)

    return RunsResponse(product=product, date=date, runs=runs)


@router.get("/variables", response_model=VariablesResponse)
async def get_variables(
    product: str = Query(..., description="Product identifier"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
) -> VariablesResponse:
    """Return available variables grouped by category for a product/date/run."""
    _validate_product(product)
    _validate_date(date)
    _validate_run(run)
    logger.info("api.variables.request", product=product, date=date, run=run)

    selector = get_field_selector()
    raw_variables = selector.get_variables(date, run, product=product)

    variables = []
    for v in raw_variables:
        rendering = None
        if "rendering" in v:
            fill_levels = v["rendering"]["fillLevels"]
            colormap_name = v["rendering"]["colormap"]
            colors = _compute_band_colors(colormap_name, len(fill_levels))
            rendering = VariableRenderingInfo(
                colormap=colormap_name,
                contourInterval=v["rendering"]["contourInterval"],
                fillLevels=fill_levels,
                colors=colors,
            )
        variables.append(
            VariableInfo(
                name=v["name"],
                shortName=v["shortName"],
                fullName=v["fullName"],
                units=v["units"],
                category=v["category"],
                rendering=rendering,
            )
        )

    return VariablesResponse(
        product=product, date=date, run=run, variables=variables
    )


@router.get("/levels", response_model=LevelsResponse)
async def get_levels(
    product: str = Query(..., description="Product identifier"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
    variable: str = Query(..., description="Variable name"),
) -> LevelsResponse:
    """Return available vertical levels for a specific variable."""
    _validate_product(product)
    _validate_date(date)
    _validate_run(run)
    logger.info(
        "api.levels.request",
        product=product,
        date=date,
        run=run,
        variable=variable,
    )

    selector = get_field_selector()
    raw_levels = selector.get_levels(date, run, variable)

    levels = [
        LevelInfo(
            surfaceType=lv.get("surfaceType"),
            value=lv["value"],
            label=lv["label"],
        )
        for lv in raw_levels
    ]

    return LevelsResponse(
        product=product, date=date, run=run, variable=variable, levels=levels
    )


@router.get("/times", response_model=TimesResponse)
async def get_times(
    product: str = Query(..., description="Product identifier"),
    date: str = Query(..., description="Forecast date in YYYYMMDD format"),
    run: str = Query(..., description="Initialization cycle (e.g. '00')"),
) -> TimesResponse:
    """Return forecast hours and valid times for a product/date/run."""
    _validate_product(product)
    _validate_date(date)
    _validate_run(run)
    logger.info("api.times.request", product=product, date=date, run=run)

    selector = get_field_selector()
    raw_hours = selector.get_forecast_hours(date, run)

    # Compute initialization time
    try:
        init_time = datetime.strptime(f"{date}{run}", "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot compute init time from date={date}, run={run}.",
        )

    forecast_hours = [
        ForecastHourEntry(fhr=entry["fhr"], valid_time=entry["valid_time"])
        for entry in raw_hours
    ]

    return TimesResponse(
        product=product,
        date=date,
        run=run,
        init_time=init_time.isoformat(),
        forecast_hours=forecast_hours,
    )
