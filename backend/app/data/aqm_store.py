"""AQMv7 data store — reads GRIB2 files directly from S3.

Unlike the GEFS-Aerosol Kerchunk approach, AQMv7 files are small enough
to read directly. Each file contains all forecast hours for one variable.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

import grib2io
import numpy as np
import s3fs
import structlog
from cachetools import LRUCache

logger = structlog.get_logger(__name__)

_DEFAULT_STORE_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "manifests"


class AQMStore:
    """Data store for AQMv7 regional air quality forecasts."""

    def __init__(self, store_path: str | None = None, domain: str = "CS"):
        self.store_path = Path(store_path) if store_path else _DEFAULT_STORE_PATH
        self.domain = domain
        self._product_dir = self.store_path / f"aqm_{domain}"
        self._s3fs: s3fs.S3FileSystem | None = None
        self._data_cache: LRUCache = LRUCache(maxsize=16)
        self._latlons_cache: dict[str, tuple[np.ndarray, np.ndarray]] | None = None

        # Scan available dates
        self._available: dict[str, list[str]] = {}
        self._scan()

        logger.info(
            "aqm_store.initialized",
            domain=domain,
            dates=len(self._available),
        )

    @property
    def fs(self) -> s3fs.S3FileSystem:
        if self._s3fs is None:
            self._s3fs = s3fs.S3FileSystem(anon=True)
        return self._s3fs

    def _read_file_bytes(self, var_info: dict[str, Any]) -> bytes:
        """Read GRIB2 file bytes from local disk or S3."""
        local_path = var_info.get("local_path")
        s3_key = var_info.get("s3_key", "")

        if local_path and Path(local_path).is_file():
            with open(local_path, "rb") as f:
                return f.read()
        elif s3_key and Path(s3_key).is_file():
            with open(s3_key, "rb") as f:
                return f.read()
        else:
            with self.fs.open(s3_key, "rb") as f:
                return f.read()

    def _scan(self) -> None:
        """Scan manifest directory for available dates/runs."""
        self._available.clear()
        if not self._product_dir.is_dir():
            return
        for date_dir in sorted(self._product_dir.iterdir()):
            if not date_dir.is_dir() or len(date_dir.name) != 8:
                continue
            runs = []
            for run_dir in sorted(date_dir.iterdir()):
                if run_dir.is_dir() and (run_dir / "manifest.json").exists():
                    runs.append(run_dir.name)
            if runs:
                self._available[date_dir.name] = runs

    def available_dates(self) -> list[str]:
        return sorted(self._available.keys())

    def available_runs(self, date: str) -> list[str]:
        return self._available.get(date, [])

    def available_variables(self, date: str, run: str) -> list[str]:
        manifest = self._load_manifest(date, run)
        if not manifest:
            return []
        return sorted(manifest.get("variables", {}).keys())

    def _load_manifest(self, date: str, run: str) -> dict[str, Any] | None:
        path = self._product_dir / date / run / "manifest.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def select(
        self,
        date: str,
        run: str,
        variable: str,
        fhr: int | None = None,
    ) -> np.ndarray:
        """Extract a 2D field for the given variable and forecast hour.

        Parameters
        ----------
        date : str
            Date in YYYYMMDD format.
        run : str
            Model cycle (e.g., "06", "12").
        variable : str
            Variable name (e.g., "ave_1hr_pm25").
        fhr : int, optional
            Forecast hour (1-72). If None, returns first hour.

        Returns
        -------
        np.ndarray
            2D field array of shape (ny, nx).
        """
        cache_key = (date, run, variable, fhr)
        cached = self._data_cache.get(cache_key)
        if cached is not None:
            return cached

        manifest = self._load_manifest(date, run)
        if not manifest:
            raise ValueError(f"No manifest for {date}/{run}")

        var_info = manifest.get("variables", {}).get(variable)
        if not var_info:
            raise ValueError(f"Variable '{variable}' not found in {date}/{run}")

        target_fhr = fhr if fhr is not None else 1

        t0 = time.perf_counter()

        # Download GRIB2 from S3 or read from local disk
        data = self._read_file_bytes(var_info)

        with tempfile.NamedTemporaryFile(suffix=".grib2") as tmp:
            tmp.write(data)
            tmp.flush()

            with grib2io.open(tmp.name) as g:
                # Find message matching the target forecast hour
                # First try to match by lead time
                matched_msg = None
                for msg in g:
                    lead_hours = int(msg.leadTime.total_seconds() / 3600)
                    if lead_hours == target_fhr:
                        matched_msg = msg
                        break

                # If no match by lead time, use index (fhr-1 for 1-based)
                if matched_msg is None and target_fhr >= 1 and target_fhr <= len(g):
                    matched_msg = g[target_fhr - 1]

                # Last resort: first message
                if matched_msg is None and len(g) > 0:
                    matched_msg = g[0]

                if matched_msg is not None:
                    field = matched_msg.data
                    if callable(field):
                        field = field()
                    field = np.asarray(field, dtype=np.float32)

                    # Cache lat/lons from first successful read
                    if self._latlons_cache is None:
                        lats, lons = matched_msg.latlons()
                        self._latlons_cache = (
                            np.asarray(lats, dtype=np.float64),
                            np.asarray(lons, dtype=np.float64),
                        )

                    elapsed = (time.perf_counter() - t0) * 1000
                    logger.info(
                        "aqm_store.select.done",
                        variable=variable,
                        fhr=target_fhr,
                        shape=field.shape,
                        elapsed_ms=round(elapsed, 1),
                    )

                    self._data_cache[cache_key] = field
                    return field

        raise ValueError(f"Could not select data for {variable} fhr={target_fhr} in {date}/{run}")

    def get_latlons(self, date: str, run: str) -> tuple[np.ndarray, np.ndarray]:
        """Get 2D lat/lon arrays for the grid.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            (lats, lons) — both shape (ny, nx).
        """
        if self._latlons_cache is not None:
            return self._latlons_cache

        # Need to read one file to get grid coordinates
        manifest = self._load_manifest(date, run)
        if not manifest:
            raise ValueError(f"No manifest for {date}/{run}")

        # Pick first available variable
        variables = manifest.get("variables", {})
        if not variables:
            raise ValueError("No variables in manifest")

        first_var = next(iter(variables.values()))
        data = self._read_file_bytes(first_var)

        with tempfile.NamedTemporaryFile(suffix=".grib2") as tmp:
            tmp.write(data)
            tmp.flush()
            with grib2io.open(tmp.name) as g:
                msg = g[0]
                lats, lons = msg.latlons()
                self._latlons_cache = (
                    np.asarray(lats, dtype=np.float64),
                    np.asarray(lons, dtype=np.float64),
                )
                return self._latlons_cache

    def get_forecast_hours(self, date: str, run: str) -> list[int]:
        """Get available forecast hours for the first hourly variable.

        Returns hours 1-72 for hourly variables (ave_1hr_*).
        Daily max/average variables have fewer time steps.
        """
        # Return standard hourly range — individual variable selection
        # falls back to index-based access if lead time doesn't match.
        return list(range(1, 73))

    def get_geographic_bounds(self, date: str, run: str) -> dict[str, float]:
        """Get the geographic bounding box of the grid."""
        lats, lons = self.get_latlons(date, run)
        return {
            "lat_min": float(lats.min()),
            "lat_max": float(lats.max()),
            "lon_min": float(lons.min()),
            "lon_max": float(lons.max()),
        }
