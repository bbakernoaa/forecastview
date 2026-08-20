"""Field selector module for metadata discovery and field extraction.

Provides a high-level interface for discovering available dates, runs,
variables, levels, and forecast hours from Kerchunk-backed datasets,
and for selecting individual 2D fields as numpy arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import structlog
import xarray as xr

from backend.app.config.loader import DomainConfig, get_domain_config_safe
from backend.app.data.kerchunk_store import KerchunkStore

logger = structlog.get_logger(__name__)

# Variable category mapping based on GRIB2 parameterCategory/parameterNumber.
# Category 20 = Optical properties, Category 14 = Mass density/concentration.
# Used as fallback when domain config is not available.
_CATEGORY_MAP: dict[tuple[int, int], str] = {
    (20, 0): "Optical Depth",
    (20, 1): "Optical Depth",
    (20, 2): "Optical Depth",
    (14, 0): "Mass Density",
    (14, 1): "Mass Density",
    (14, 2): "Mass Concentration",
    (13, 0): "Aerosols",
    (13, 1): "Aerosols",
    (13, 2): "Aerosols",
}

_DEFAULT_CATEGORY = "Other"

# Common coordinate name conventions for latitude/longitude
_LAT_NAMES = ("latitude", "lat", "XLAT", "TLAT")
_LON_NAMES = ("longitude", "lon", "XLONG", "TLONG")

# GRIB2 grid type to CRS mapping
_REGULAR_LL_GRID_TYPES = ("regular_ll", "regular_gg", "reduced_gg")


@dataclass(frozen=True)
class GridProjection:
    """Projection/CRS metadata extracted from GRIB2 dataset attributes.

    Encapsulates the coordinate reference system information needed to
    perform correct geographic transformations between the native model
    grid and geographic (lon/lat) coordinates.

    Attributes
    ----------
    grid_type : str
        GRIB2 grid type identifier (e.g. "regular_ll", "lambert",
        "polar_stereographic", "mercator").
    crs_params : dict[str, Any]
        Raw projection parameters extracted from GRIB2 attributes.
        Contents vary by grid type. For regular_ll, includes grid
        extents and increments. For Lambert, includes standard
        parallels and central meridian.
    scanning_mode : dict[str, Any]
        Scanning mode flags describing how the grid data is ordered:
        iScansNegatively, jScansPositively, jPointsAreConsecutive.
    """

    grid_type: str
    crs_params: dict[str, Any]
    scanning_mode: dict[str, Any]

    def to_crs_string(self) -> str:
        """Return a pyproj-compatible CRS string for this projection.

        For regular lat-lon grids, returns "EPSG:4326". For Lambert
        Conformal grids, returns a proj4 string. For other grid types,
        returns a best-effort proj4 string or falls back to EPSG:4326.

        Returns
        -------
        str
            A CRS string usable with pyproj.CRS.from_user_input().
        """
        if self.grid_type in _REGULAR_LL_GRID_TYPES:
            return "EPSG:4326"

        if self.grid_type == "lambert":
            lat1 = self.crs_params.get("Latin1InDegrees", 25.0)
            lat2 = self.crs_params.get("Latin2InDegrees", 25.0)
            lat0 = self.crs_params.get("LaDInDegrees", lat1)
            lon0 = self.crs_params.get("LoVInDegrees", 0.0)
            return (
                f"+proj=lcc +lat_1={lat1} +lat_2={lat2} "
                f"+lat_0={lat0} +lon_0={lon0} "
                f"+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
            )

        if self.grid_type == "polar_stereographic":
            lat_ts = self.crs_params.get("LaDInDegrees", 60.0)
            lon0 = self.crs_params.get("orientationOfTheGridInDegrees", 0.0)
            return (
                f"+proj=stere +lat_0=90 +lat_ts={lat_ts} "
                f"+lon_0={lon0} +x_0=0 +y_0=0 "
                f"+datum=WGS84 +units=m +no_defs"
            )

        if self.grid_type == "mercator":
            lat_ts = self.crs_params.get("LaDInDegrees", 0.0)
            return (
                f"+proj=merc +lat_ts={lat_ts} "
                f"+lon_0=0 +x_0=0 +y_0=0 "
                f"+datum=WGS84 +units=m +no_defs"
            )

        # Fallback: assume geographic
        return "EPSG:4326"


@dataclass(frozen=True)
class GridCoordinates:
    """Coordinate arrays describing the spatial grid of a dataset.

    Attributes
    ----------
    lats : np.ndarray
        Latitude values. 1D for regular grids, 2D for curvilinear grids.
    lons : np.ndarray
        Longitude values. 1D for regular grids, 2D for curvilinear grids.
    shape : tuple[int, ...]
        Shape of the spatial grid (ny, nx).
    """

    lats: np.ndarray
    lons: np.ndarray
    shape: tuple[int, ...]


def _categorize_variable(attrs: dict[str, Any]) -> str:
    """Determine the display category for a variable from its GRIB2 attributes."""
    param_cat = attrs.get("parameterCategory")
    param_num = attrs.get("parameterNumber")
    if param_cat is not None and param_num is not None:
        key = (int(param_cat), int(param_num))
        return _CATEGORY_MAP.get(key, _DEFAULT_CATEGORY)
    return _DEFAULT_CATEGORY


class FieldSelector:
    """High-level interface for metadata discovery and field selection.

    Wraps a KerchunkStore instance to provide discovery of available
    dates, runs, variables, levels, and forecast hours, as well as
    extraction of individual 2D fields as numpy arrays.

    Parameters
    ----------
    store : KerchunkStore
        The underlying data store for lazy dataset access.
    """

    def __init__(self, store: KerchunkStore) -> None:
        self._store = store
        logger.info("field_selector.initialized")

    # ------------------------------------------------------------------
    # Discovery methods
    # ------------------------------------------------------------------

    def get_dates(self) -> list[str]:
        """Get available forecast dates.

        Returns
        -------
        list[str]
            Sorted list of date strings in YYYYMMDD format.
        """
        logger.debug("field_selector.get_dates")
        return self._store.discover_dates()

    def get_runs(self, date: str) -> list[str]:
        """Get available initialization runs for a given date.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.

        Returns
        -------
        list[str]
            Sorted list of cycle strings (e.g. ["00", "06", "12", "18"]).
        """
        logger.debug("field_selector.get_runs", date=date)
        return self._store.discover_runs(date)

    def get_variables(
        self, date: str, run: str, product: str = "air"
    ) -> list[dict[str, Any]]:
        """Discover variables available in the dataset for a given date/run.

        Opens the dataset and inspects data variable attributes to build
        a list of variable information dicts grouped by category. When a
        domain configuration is available for the product, it enriches the
        metadata with configured labels, categories, and rendering hints.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Initialization cycle (e.g. "00").
        product : str
            Product identifier for domain config lookup (default: "air").

        Returns
        -------
        list[dict[str, Any]]
            List of variable info dicts, each containing:
            - name: internal variable name (xarray key)
            - shortName: short display name
            - fullName: full descriptive name
            - units: variable units
            - category: grouping category string
            - rendering: dict with colormap, contourInterval, fillLevels
              (only present when domain config is available)
        """
        logger.debug("field_selector.get_variables", date=date, run=run)
        try:
            ds = self._store.open_dataset(date, run)
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "field_selector.get_variables.dataset_unavailable",
                date=date,
                run=run,
                error=str(exc),
            )
            return []

        # Load domain config for enriched metadata (may be None)
        domain_config = get_domain_config_safe(product)

        variables: list[dict[str, Any]] = []
        for var_name in ds.data_vars:
            var = ds[var_name]
            attrs = var.attrs
            name_str = str(var_name)

            # Check if domain config has metadata for this variable
            var_config = (
                domain_config.get_variable(name_str) if domain_config else None
            )

            if var_config is not None:
                # Use domain config metadata (preferred)
                info: dict[str, Any] = {
                    "name": name_str,
                    "shortName": var_config.shortName,
                    "fullName": var_config.fullName,
                    "units": var_config.units,
                    "category": var_config.category,
                    "rendering": {
                        "colormap": var_config.rendering.colormap,
                        "contourInterval": var_config.rendering.contourInterval,
                        "fillLevels": var_config.rendering.fillLevels,
                    },
                }
            else:
                # Fall back to xarray attributes
                info = {
                    "name": name_str,
                    "shortName": attrs.get("shortName", name_str),
                    "fullName": attrs.get("fullName", name_str),
                    "units": attrs.get("units", ""),
                    "category": _categorize_variable(attrs),
                }

            variables.append(info)

        # Sort by category order from config, then shortName
        if domain_config and domain_config.categories:
            cat_order = {
                cat: idx for idx, cat in enumerate(domain_config.categories)
            }
            default_order = len(cat_order)
            variables.sort(
                key=lambda v: (
                    cat_order.get(v["category"], default_order),
                    v["shortName"],
                )
            )
        else:
            # Fallback: sort alphabetically by category then shortName
            variables.sort(key=lambda v: (v["category"], v["shortName"]))

        logger.info(
            "field_selector.get_variables.done",
            date=date,
            run=run,
            count=len(variables),
            config_enriched=domain_config is not None,
        )
        return variables

    def get_levels(
        self, date: str, run: str, variable: str
    ) -> list[dict[str, Any]]:
        """Discover available vertical levels for a given variable.

        Inspects the variable's typeOfFirstFixedSurface and
        valueOfFirstFixedSurface attributes to determine available levels.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Initialization cycle (e.g. "00").
        variable : str
            Variable name (xarray key).

        Returns
        -------
        list[dict[str, Any]]
            List of level info dicts, each containing:
            - surfaceType: typeOfFirstFixedSurface value
            - value: valueOfFirstFixedSurface (numeric level)
            - label: human-readable level description
            Returns empty list if the variable or dataset is not available.
        """
        logger.debug(
            "field_selector.get_levels",
            date=date,
            run=run,
            variable=variable,
        )
        try:
            ds = self._store.open_dataset(date, run)
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "field_selector.get_levels.dataset_unavailable",
                date=date,
                run=run,
                error=str(exc),
            )
            return []

        if variable not in ds.data_vars:
            logger.warning(
                "field_selector.get_levels.variable_not_found",
                date=date,
                run=run,
                variable=variable,
            )
            return []

        var = ds[variable]
        attrs = var.attrs

        surface_type = attrs.get("typeOfFirstFixedSurface")
        surface_value = attrs.get("valueOfFirstFixedSurface")

        # Build level list. For datasets where the variable spans multiple
        # levels via a dimension, iterate over that dimension. Otherwise
        # report the single level from attributes.
        levels: list[dict[str, Any]] = []

        # Check for a vertical dimension (common names)
        vertical_dims = [
            d for d in var.dims
            if d not in ("y", "x", "valid_time", "time", "latitude", "longitude")
        ]

        if vertical_dims:
            # If there's a vertical coordinate dimension, enumerate its values
            vert_dim = vertical_dims[0]
            if vert_dim in ds.coords:
                for val in ds.coords[vert_dim].values:
                    levels.append({
                        "surfaceType": surface_type,
                        "value": float(val),
                        "label": f"{vert_dim}={val}",
                    })
            else:
                # Dimension exists but no coordinate values
                levels.append({
                    "surfaceType": surface_type,
                    "value": float(surface_value) if surface_value is not None else 0.0,
                    "label": _surface_type_label(surface_type, surface_value),
                })
        else:
            # Single-level variable
            levels.append({
                "surfaceType": surface_type,
                "value": float(surface_value) if surface_value is not None else 0.0,
                "label": _surface_type_label(surface_type, surface_value),
            })

        logger.info(
            "field_selector.get_levels.done",
            date=date,
            run=run,
            variable=variable,
            count=len(levels),
        )
        return levels

    def get_forecast_hours(
        self, date: str, run: str
    ) -> list[dict[str, Any]]:
        """Discover available forecast hours and compute valid times.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Initialization cycle (e.g. "00").

        Returns
        -------
        list[dict[str, Any]]
            List of forecast hour info dicts, each containing:
            - fhr: forecast hour integer
            - valid_time: ISO-formatted valid time string
            Returns empty list if discovery fails.
        """
        logger.debug("field_selector.get_forecast_hours", date=date, run=run)
        hours = self._store.discover_forecast_hours(date, run)

        # Compute initialization time
        try:
            init_time = datetime.strptime(f"{date}{run}", "%Y%m%d%H").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            logger.warning(
                "field_selector.get_forecast_hours.invalid_date_run",
                date=date,
                run=run,
            )
            return []

        result: list[dict[str, Any]] = []
        for fhr in hours:
            valid_time = init_time + timedelta(hours=fhr)
            result.append({
                "fhr": fhr,
                "valid_time": valid_time.isoformat(),
            })

        logger.info(
            "field_selector.get_forecast_hours.done",
            date=date,
            run=run,
            count=len(result),
        )
        return result

    # ------------------------------------------------------------------
    # Projection / CRS discovery
    # ------------------------------------------------------------------

    def get_projection(self, date: str, run: str) -> GridProjection:
        """Extract projection/CRS metadata from the dataset's GRIB2 attributes.

        Opens the dataset for the given date/run and reads projection-related
        attributes from the first data variable. Constructs a GridProjection
        instance containing the grid type, raw CRS parameters, and scanning
        mode flags.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Initialization cycle (e.g. "00").

        Returns
        -------
        GridProjection
            Dataclass with grid_type, crs_params, scanning_mode, and a
            to_crs_string() method for pyproj integration.

        Raises
        ------
        ValueError
            If no data variables are found in the dataset.
        RuntimeError
            If the dataset cannot be opened.
        """
        logger.debug("field_selector.get_projection", date=date, run=run)

        ds = self._store.open_dataset(date, run)

        if not ds.data_vars:
            raise ValueError(
                f"No data variables found in dataset for "
                f"date={date}, run={run}."
            )

        # Use the first data variable's attributes for projection info
        first_var_name = next(iter(ds.data_vars))
        attrs = ds[first_var_name].attrs

        # Also check dataset-level attributes (some GRIB2 stores put
        # projection info there)
        ds_attrs = ds.attrs

        # Merge: variable attrs take precedence over dataset attrs
        merged_attrs: dict[str, Any] = {**ds_attrs, **attrs}

        # Extract grid type
        grid_type = str(
            merged_attrs.get("gridType", "regular_ll")
        )

        # Extract CRS parameters based on grid type
        crs_params: dict[str, Any] = {}

        if grid_type in _REGULAR_LL_GRID_TYPES:
            # Regular latitude-longitude grid parameters
            _lat_lon_keys = [
                "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
                "latitudeOfLastGridPointInDegrees",
                "longitudeOfLastGridPointInDegrees",
                "iDirectionIncrementInDegrees",
                "jDirectionIncrementInDegrees",
                "Ni",
                "Nj",
            ]
            for key in _lat_lon_keys:
                if key in merged_attrs:
                    crs_params[key] = merged_attrs[key]

        elif grid_type == "lambert":
            # Lambert Conformal Conic parameters
            _lambert_keys = [
                "LaDInDegrees",
                "LoVInDegrees",
                "Latin1InDegrees",
                "Latin2InDegrees",
                "Dx",
                "Dy",
                "Nx",
                "Ny",
                "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
            ]
            for key in _lambert_keys:
                if key in merged_attrs:
                    crs_params[key] = merged_attrs[key]

        elif grid_type == "polar_stereographic":
            # Polar stereographic parameters
            _polar_keys = [
                "LaDInDegrees",
                "orientationOfTheGridInDegrees",
                "Dx",
                "Dy",
                "Nx",
                "Ny",
                "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
            ]
            for key in _polar_keys:
                if key in merged_attrs:
                    crs_params[key] = merged_attrs[key]

        elif grid_type == "mercator":
            # Mercator parameters
            _mercator_keys = [
                "LaDInDegrees",
                "latitudeOfFirstGridPointInDegrees",
                "longitudeOfFirstGridPointInDegrees",
                "latitudeOfLastGridPointInDegrees",
                "longitudeOfLastGridPointInDegrees",
                "Dx",
                "Dy",
            ]
            for key in _mercator_keys:
                if key in merged_attrs:
                    crs_params[key] = merged_attrs[key]

        # Extract scanning mode flags
        scanning_mode: dict[str, Any] = {}
        _scan_keys = [
            "iScansNegatively",
            "jScansPositively",
            "jPointsAreConsecutive",
        ]
        for key in _scan_keys:
            if key in merged_attrs:
                scanning_mode[key] = merged_attrs[key]

        projection = GridProjection(
            grid_type=grid_type,
            crs_params=crs_params,
            scanning_mode=scanning_mode,
        )

        logger.info(
            "field_selector.get_projection.done",
            date=date,
            run=run,
            grid_type=grid_type,
            crs_string=projection.to_crs_string(),
            crs_params=crs_params,
            scanning_mode=scanning_mode,
        )

        return projection

    # ------------------------------------------------------------------
    # Coordinate extraction
    # ------------------------------------------------------------------

    def get_coordinates(
        self,
        date: str,
        run: str,
        variable: str | None = None,
    ) -> GridCoordinates:
        """Extract latitude and longitude coordinate arrays from the dataset.

        Handles common coordinate naming conventions used in GRIB2/xarray
        datasets: "latitude"/"longitude" (CF-standard), "lat"/"lon", or
        dimensions named "y"/"x" with separate coordinate variables.

        If a variable is specified, coordinate arrays are taken from that
        variable's dimensions to ensure correct shape for curvilinear grids.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Initialization cycle (e.g. "00").
        variable : str, optional
            Variable name to derive coordinates from. If None, coordinates
            are searched at the dataset level.

        Returns
        -------
        GridCoordinates
            Dataclass containing lats, lons, and grid shape.

        Raises
        ------
        ValueError
            If latitude or longitude coordinates cannot be found in the
            dataset, or if the specified variable does not exist.
        RuntimeError
            If the dataset cannot be opened.
        """
        logger.debug(
            "field_selector.get_coordinates",
            date=date,
            run=run,
            variable=variable,
        )

        ds = self._store.open_dataset(date, run)

        # If a variable is specified, scope coordinate search to it
        source: xr.Dataset | xr.DataArray = ds
        if variable is not None:
            if variable not in ds.data_vars:
                raise ValueError(
                    f"Variable '{variable}' not found in dataset for "
                    f"date={date}, run={run}. Available: {list(ds.data_vars)}"
                )
            source = ds[variable]

        lats = self._find_coordinate(source, _LAT_NAMES)
        lons = self._find_coordinate(source, _LON_NAMES)

        if lats is None:
            raise ValueError(
                f"Could not find latitude coordinates in dataset for "
                f"date={date}, run={run}. "
                f"Searched names: {_LAT_NAMES}, dims: {list(ds.dims)}"
            )
        if lons is None:
            raise ValueError(
                f"Could not find longitude coordinates in dataset for "
                f"date={date}, run={run}. "
                f"Searched names: {_LON_NAMES}, dims: {list(ds.dims)}"
            )

        lat_values = lats.values
        lon_values = lons.values

        # Determine grid shape from coordinate arrays
        if lat_values.ndim == 2:
            shape = lat_values.shape
        elif lat_values.ndim == 1 and lon_values.ndim == 1:
            shape = (lat_values.shape[0], lon_values.shape[0])
        else:
            shape = lat_values.shape

        result = GridCoordinates(
            lats=lat_values,
            lons=lon_values,
            shape=shape,
        )

        logger.info(
            "field_selector.get_coordinates.done",
            date=date,
            run=run,
            variable=variable,
            lat_shape=lat_values.shape,
            lon_shape=lon_values.shape,
            grid_shape=shape,
            lat_min=float(np.nanmin(lat_values)),
            lat_max=float(np.nanmax(lat_values)),
            lon_min=float(np.nanmin(lon_values)),
            lon_max=float(np.nanmax(lon_values)),
        )

        return result

    @staticmethod
    def _find_coordinate(
        source: xr.Dataset | xr.DataArray,
        names: tuple[str, ...],
    ) -> xr.DataArray | None:
        """Search for a coordinate array by common naming conventions.

        Checks coordinates first, then dimensions, then data variables
        (for dataset-level sources).

        Parameters
        ----------
        source : xr.Dataset or xr.DataArray
            The data object to search within.
        names : tuple[str, ...]
            Candidate coordinate names to look for.

        Returns
        -------
        xr.DataArray or None
            The coordinate array if found, otherwise None.
        """
        # Check coords (works for both Dataset and DataArray)
        for name in names:
            if name in source.coords:
                return source.coords[name]

        # For Dataset, also check data_vars (some GRIB2 datasets store
        # lat/lon as separate data variables rather than coordinates)
        if isinstance(source, xr.Dataset):
            for name in names:
                if name in source.data_vars:
                    return source[name]

        # Check if "y"/"x" dimensions exist with associated lat/lon coords
        # (common in WRF/GRIB2 curvilinear grids)
        if isinstance(source, xr.Dataset):
            dims_to_check = source.dims
        else:
            dims_to_check = dict.fromkeys(source.dims)

        if "y" in dims_to_check and "x" in dims_to_check:
            # Look for 2D lat/lon arrays attached as coordinates to a variable
            if isinstance(source, xr.Dataset):
                for var_name in source.data_vars:
                    var = source[var_name]
                    for name in names:
                        if name in var.coords:
                            return var.coords[name]

        return None

    # ------------------------------------------------------------------
    # Field selection
    # ------------------------------------------------------------------

    def select(
        self,
        date: str,
        run: str,
        variable: str,
        level: float | None = None,
        fhr: int | None = None,
    ) -> np.ndarray:
        """Select a single 2D field from the dataset.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Initialization cycle (e.g. "00").
        variable : str
            Variable name (xarray key).
        level : float, optional
            Vertical level value for selection. If None, selects the
            first available level or assumes single-level data.
        fhr : int, optional
            Forecast hour for time selection. If None, selects the first
            available time step.

        Returns
        -------
        np.ndarray
            2D numpy array of field values.

        Raises
        ------
        ValueError
            If the variable is not found in the dataset.
        RuntimeError
            If the dataset cannot be opened.
        """
        logger.info(
            "field_selector.select",
            date=date,
            run=run,
            variable=variable,
            level=level,
            fhr=fhr,
        )

        ds = self._store.open_dataset(date, run)

        if variable not in ds.data_vars:
            raise ValueError(
                f"Variable '{variable}' not found in dataset for "
                f"date={date}, run={run}. "
                f"Available: {list(ds.data_vars)}"
            )

        da: xr.DataArray = ds[variable]

        # Select by forecast hour / valid_time if provided
        if fhr is not None and "valid_time" in da.dims:
            try:
                init_time = datetime.strptime(f"{date}{run}", "%Y%m%d%H").replace(
                    tzinfo=timezone.utc
                )
                target_time = init_time + timedelta(hours=fhr)
                da = da.sel(valid_time=target_time, method="nearest")
            except Exception as exc:
                logger.warning(
                    "field_selector.select.time_selection_failed",
                    fhr=fhr,
                    error=str(exc),
                )
                # Fall back to first time step
                da = da.isel(valid_time=0)
        elif "valid_time" in da.dims:
            da = da.isel(valid_time=0)

        # Select by vertical level if provided
        vertical_dims = [
            d for d in da.dims
            if d not in ("y", "x", "valid_time", "time", "latitude", "longitude")
        ]

        if vertical_dims:
            vert_dim = vertical_dims[0]
            if level is not None and vert_dim in ds.coords:
                da = da.sel({vert_dim: level}, method="nearest")
            else:
                # Select first level
                da = da.isel({vert_dim: 0})

        # Load the data as a numpy array
        field = da.values

        # Ensure 2D output
        field = np.squeeze(field)
        if field.ndim != 2:
            raise ValueError(
                f"Expected 2D field after selection, got shape {field.shape} "
                f"for variable={variable}, level={level}, fhr={fhr}"
            )

        logger.info(
            "field_selector.select.done",
            variable=variable,
            shape=field.shape,
            min=float(np.nanmin(field)),
            max=float(np.nanmax(field)),
            mean=float(np.nanmean(field)),
        )
        return field


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _surface_type_label(
    surface_type: Any, surface_value: Any
) -> str:
    """Generate a human-readable label for a GRIB2 surface type."""
    # Common GRIB2 typeOfFirstFixedSurface codes
    _SURFACE_LABELS: dict[int, str] = {
        1: "Ground or Water Surface",
        8: "Top of Atmosphere",
        10: "Entire Atmosphere",
        100: "Isobaric Surface",
        103: "Height Above Ground",
        200: "Entire Atmosphere (as layer)",
    }

    if surface_type is not None:
        try:
            st = int(surface_type)
            base = _SURFACE_LABELS.get(st, f"Surface Type {st}")
            if surface_value is not None and st in (100, 103):
                return f"{base} ({surface_value})"
            return base
        except (TypeError, ValueError):
            pass

    if surface_value is not None:
        return f"Level {surface_value}"
    return "Surface"
