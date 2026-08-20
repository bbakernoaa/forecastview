"""Manifest-based store module for lazy GRIB2 data access.

Opens pre-built Kerchunk JSON manifests from a local directory structure.
Manifests are generated offline by the ingest script and read instantly
at serving time — no S3 scanning required for metadata discovery.

Directory layout:
    {store_path}/{date}/{run}/manifest.json
"""

from __future__ import annotations

import os
from datetime import UTC
from pathlib import Path
from typing import Any

import fsspec
import structlog
import xarray as xr
from cachetools import LRUCache

logger = structlog.get_logger(__name__)

# Default configuration
_DEFAULT_STORE_PATH = "data/manifests"
_DEFAULT_CACHE_SIZE = 8
_DEFAULT_STORAGE_OPTIONS: dict[str, Any] = {"anon": True}


def _resolve_store_path(path: str | None) -> Path:
    """Resolve the manifest store path to an absolute path.

    If the path is relative, it is resolved relative to the project root
    (detected as 4 levels up from this file: data/ -> app/ -> backend/ -> project/).
    """
    raw = path or os.environ.get("FORECASTVIEW_STORE_PATH", _DEFAULT_STORE_PATH)
    p = Path(raw)
    if not p.is_absolute():
        # Resolve relative to project root
        project_root = Path(__file__).resolve().parents[3]
        p = project_root / p
    return p


# Keep the old name as an alias for backward compatibility in scripts
# that still import KerchunkStore
KerchunkStore = None  # Will be set at module bottom after class definition


class ManifestStore:
    """Manages GRIB2 data access through pre-built Kerchunk JSON manifests.

    Reads manifests from a local directory structure. Manifests are
    generated offline by `backend/scripts/ingest.py` and provide instant
    metadata access without S3 scanning.

    Parameters
    ----------
    store_path : str or None
        Path to the manifest directory. Defaults to the
        ``FORECASTVIEW_STORE_PATH`` environment variable or
        ``data/manifests`` relative to the project root.
    cache_size : int or None
        Maximum number of open dataset handles to retain in the LRU cache.
    storage_options : dict or None
        Options passed to fsspec for remote data access when loading
        actual field values (default: anonymous S3).
    forecast_hours : list[int] or None
        Kept for backward compatibility with scripts that pass
        ``forecast_hours=[0]``. Ignored in the manifest-based workflow.
    """

    def __init__(
        self,
        store_path: str | None = None,
        cache_size: int | None = None,
        storage_options: dict[str, Any] | None = None,
        forecast_hours: list[int] | None = None,
    ) -> None:
        self.store_path = _resolve_store_path(store_path)
        self.storage_options = storage_options or _DEFAULT_STORAGE_OPTIONS.copy()

        cache_sz = cache_size or int(
            os.environ.get("FORECASTVIEW_CACHE_SIZE", str(_DEFAULT_CACHE_SIZE))
        )

        # LRU cache keyed by (date, run) → xr.Dataset
        self._dataset_cache: LRUCache[tuple[str, str], xr.Dataset] = LRUCache(maxsize=cache_sz)

        # Scan the manifest directory on init
        self._available: dict[str, list[str]] = {}  # date -> [runs]
        self._scan_manifests()

        logger.info(
            "manifest_store.initialized",
            store_path=str(self.store_path),
            cache_size=cache_sz,
            dates_available=len(self._available),
        )

    def _scan_manifests(self) -> None:
        """Scan the manifest directory for available date/run combinations."""
        self._available.clear()

        if not self.store_path.is_dir():
            logger.warning(
                "manifest_store.scan.no_directory",
                store_path=str(self.store_path),
            )
            return

        for date_dir in sorted(self.store_path.iterdir()):
            if not date_dir.is_dir():
                continue
            date = date_dir.name
            # Validate date format (YYYYMMDD — 8 digits)
            if not (len(date) == 8 and date.isdigit()):
                continue

            runs: list[str] = []
            for run_dir in sorted(date_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                run = run_dir.name
                # Validate run format (2 digits like "00", "06", etc.)
                if not (len(run) == 2 and run.isdigit()):
                    continue
                manifest_file = run_dir / "manifest.json"
                if manifest_file.is_file():
                    runs.append(run)

            if runs:
                self._available[date] = runs

        logger.info(
            "manifest_store.scan.complete",
            dates=len(self._available),
            total_manifests=sum(len(r) for r in self._available.values()),
        )

    # ------------------------------------------------------------------
    # Discovery methods
    # ------------------------------------------------------------------

    def discover_dates(self) -> list[str]:
        """Discover available forecast dates from local manifests.

        Returns
        -------
        list[str]
            Sorted list of date strings in ``YYYYMMDD`` format.
        """
        dates = sorted(self._available.keys())
        logger.info("manifest_store.discover_dates", count=len(dates))
        return dates

    def discover_runs(self, date: str) -> list[str]:
        """Discover available initialization runs for a given date.

        Parameters
        ----------
        date : str
            Date in ``YYYYMMDD`` format.

        Returns
        -------
        list[str]
            Sorted list of cycle strings (e.g. ``["00", "06", "12", "18"]``).
        """
        runs = self._available.get(date, [])
        logger.info(
            "manifest_store.discover_runs",
            date=date,
            count=len(runs),
        )
        return sorted(runs)

    def discover_forecast_hours(self, date: str, run: str) -> list[int]:
        """Discover available forecast hours from the dataset's time dimension.

        Parameters
        ----------
        date : str
            Date in ``YYYYMMDD`` format.
        run : str
            Initialization cycle (e.g. ``"00"``).

        Returns
        -------
        list[int]
            Sorted list of available forecast hours.
        """
        try:
            ds = self.open_dataset(date, run)
        except (ValueError, RuntimeError) as exc:
            logger.warning(
                "manifest_store.discover_forecast_hours.failed",
                date=date,
                run=run,
                error=str(exc),
            )
            return []

        # Try to extract forecast hours from the valid_time dimension
        if "valid_time" in ds.dims and "valid_time" in ds.coords:
            from datetime import datetime

            import numpy as np

            try:
                init_time = datetime.strptime(f"{date}{run}", "%Y%m%d%H").replace(tzinfo=UTC)
                valid_times = ds.coords["valid_time"].values
                hours: list[int] = []
                for vt in valid_times:
                    # Convert numpy datetime64 to python datetime
                    ts = (vt - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
                    dt = datetime.fromtimestamp(float(ts), tz=UTC)
                    fhr = int((dt - init_time).total_seconds() / 3600)
                    hours.append(fhr)
                hours.sort()
                logger.info(
                    "manifest_store.discover_forecast_hours",
                    date=date,
                    run=run,
                    count=len(hours),
                )
                return hours
            except Exception as exc:
                logger.warning(
                    "manifest_store.discover_forecast_hours.time_parse_failed",
                    error=str(exc),
                )

        # Fallback: check step or forecast_period dimensions
        for dim_name in ("step", "forecast_period", "forecast_hour"):
            if dim_name in ds.dims and dim_name in ds.coords:
                values = ds.coords[dim_name].values.tolist()
                hours = sorted(int(v) for v in values)
                logger.info(
                    "manifest_store.discover_forecast_hours",
                    date=date,
                    run=run,
                    count=len(hours),
                    source=dim_name,
                )
                return hours

        # If no time dimension found, return empty
        logger.warning(
            "manifest_store.discover_forecast_hours.no_time_dim",
            date=date,
            run=run,
            dims=list(ds.dims),
        )
        return []

    # ------------------------------------------------------------------
    # Dataset opening
    # ------------------------------------------------------------------

    def open_dataset(
        self,
        date: str,
        run: str,
        filters: dict[str, Any] | None = None,
    ) -> xr.Dataset:
        """Open a lazily-loaded xarray Dataset from a pre-built manifest.

        Uses the LRU cache to avoid re-opening manifests that have been
        recently accessed.

        Parameters
        ----------
        date : str
            Date in ``YYYYMMDD`` format.
        run : str
            Initialization cycle (e.g. ``"00"``).
        filters : dict, optional
            Ignored in manifest-based workflow (filters are applied at
            ingest time). Kept for API compatibility.

        Returns
        -------
        xr.Dataset
            Lazily-loaded xarray dataset backed by the Kerchunk manifest.

        Raises
        ------
        ValueError
            If no manifest exists for the given date/run.
        RuntimeError
            If the manifest cannot be opened as a dataset.
        """
        cache_key = (date, run)

        # Return cached dataset if available
        if cache_key in self._dataset_cache:
            logger.debug(
                "manifest_store.open_dataset.cache_hit",
                date=date,
                run=run,
            )
            return self._dataset_cache[cache_key]

        # Locate the manifest file
        manifest_path = self.store_path / date / run / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(
                f"No manifest found for date={date}, run={run}. "
                f"Expected at: {manifest_path}. "
                f"Run the ingest script to generate manifests."
            )

        logger.info(
            "manifest_store.open_dataset.opening",
            date=date,
            run=run,
            manifest=str(manifest_path),
        )

        try:
            fs = fsspec.filesystem(
                "reference",
                fo=str(manifest_path),
                asynchronous=True,
                remote_options={**self.storage_options, "asynchronous": True},
            )
            ds = xr.open_dataset(
                fs.get_mapper(""),
                engine="zarr",
                consolidated=False,
            )
        except Exception as exc:
            logger.error(
                "manifest_store.open_dataset.failed",
                date=date,
                run=run,
                error=str(exc),
            )
            raise RuntimeError(
                f"Failed to open manifest for date={date}, run={run}: {exc}"
            ) from exc

        logger.info(
            "manifest_store.open_dataset.opened",
            date=date,
            run=run,
            dimensions=dict(ds.sizes),
            variables=list(ds.data_vars),
        )

        # Cache the dataset
        self._dataset_cache[cache_key] = ds
        return ds

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-scan the manifest directory to pick up newly ingested data."""
        self._scan_manifests()
        logger.info("manifest_store.refreshed")


# Backward compatibility alias — scripts that import KerchunkStore will
# get ManifestStore instead.
KerchunkStore = ManifestStore
