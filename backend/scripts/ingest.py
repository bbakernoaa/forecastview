"""Ingest GEFS-Aerosols GRIB2 data into local Kerchunk manifests.

Discovers available dates from the NOAA GEFS S3 bucket, builds Kerchunk
manifests using grib2io.kerchunk.ReferenceGenerator, and writes them to
a local directory structure for instant access by the ManifestStore.

Usage:
    python backend/scripts/ingest.py --days 3 --cycle 00 --store-path data/manifests
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import fsspec
import structlog

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

# Default S3 configuration
_DEFAULT_BUCKET = "noaa-gefs-pds"
_DEFAULT_PATH_PATTERN = (
    "gefs.{date}/{cycle}/chem/pgrb2ap25/gefs.chem.t{cycle}z.a2d_0p25.f{fhr:03d}.grib2"
)
_DEFAULT_STORAGE_OPTIONS: dict = {"anon": True}
_DEFAULT_MAX_WORKERS = 16
_DEFAULT_FORECAST_HOURS = list(range(0, 121, 3))


def discover_available_dates(
    bucket: str = _DEFAULT_BUCKET,
    storage_options: dict | None = None,
) -> list[str]:
    """Discover available forecast dates in the S3 bucket.

    Returns
    -------
    list[str]
        Sorted list of date strings in YYYYMMDD format.
    """
    opts = storage_options or _DEFAULT_STORAGE_OPTIONS
    prefix = "gefs."
    try:
        fs = fsspec.filesystem("s3", **opts)
        entries = fs.ls(bucket, detail=False)
        dates: list[str] = []
        for entry in entries:
            name = entry.rsplit("/", 1)[-1]
            if name.startswith(prefix) and len(name) == len(prefix) + 8:
                dates.append(name[len(prefix) :])
        dates.sort()
        return dates
    except Exception as exc:
        logger.error("discover_dates.failed", error=str(exc))
        return []


def build_urls(
    date: str,
    cycle: str,
    bucket: str = _DEFAULT_BUCKET,
    path_pattern: str = _DEFAULT_PATH_PATTERN,
    forecast_hours: list[int] | None = None,
    local_path_pattern: str | None = None,
) -> list[str]:
    """Build URLs (S3 or local file paths) for all forecast hours."""
    hours = forecast_hours or _DEFAULT_FORECAST_HOURS
    urls = []
    for fhr in hours:
        if local_path_pattern:
            # Local file path
            path = local_path_pattern.format(date=date, cycle=cycle, fhr=fhr)
            urls.append(path)
        else:
            # S3 URL
            path = path_pattern.format(date=date, cycle=cycle, fhr=fhr)
            urls.append(f"s3://{bucket}/{path}")
    return urls


def ingest_date(
    date: str,
    cycle: str,
    store_path: Path,
    bucket: str = _DEFAULT_BUCKET,
    path_pattern: str = _DEFAULT_PATH_PATTERN,
    forecast_hours: list[int] | None = None,
    max_workers: int = _DEFAULT_MAX_WORKERS,
    local_path_pattern: str | None = None,
) -> bool:
    """Build and save a Kerchunk manifest for a single date/cycle.

    Parameters
    ----------
    date : str
        Date in YYYYMMDD format.
    cycle : str
        Initialization cycle (e.g. "00").
    store_path : Path
        Base directory for storing manifests.
    bucket : str
        S3 bucket name.
    path_pattern : str
        Format string for GRIB2 file paths.
    forecast_hours : list[int]
        Forecast hours to include.
    max_workers : int
        Thread-pool size for concurrent scanning.
    local_path_pattern : str or None
        Optional local file path pattern with {date}, {cycle}, {fhr} placeholders.

    Returns
    -------
    bool
        True if manifest was successfully generated and saved.
    """
    from grib2io.kerchunk import ReferenceGenerator

    urls = build_urls(
        date=date,
        cycle=cycle,
        bucket=bucket,
        path_pattern=path_pattern,
        forecast_hours=forecast_hours,
        local_path_pattern=local_path_pattern,
    )
    if not urls:
        logger.warning("ingest_date.no_urls", date=date, cycle=cycle)
        return False

    if local_path_pattern:
        existing_urls = [u for u in urls if Path(u).is_file()]
        if not existing_urls:
            logger.warning(
                "ingest_date.no_local_files_found",
                date=date,
                cycle=cycle,
                searched=len(urls),
            )
            return False
        if len(existing_urls) < len(urls):
            logger.info(
                "ingest_date.filtered_missing_local_files",
                found=len(existing_urls),
                expected=len(urls),
            )
        urls = existing_urls

    # Create output directory
    manifest_dir = store_path / date / cycle
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.json"

    logger.info(
        "ingest_date.generating_manifest",
        date=date,
        cycle=cycle,
        num_urls=len(urls),
    )

    t_start = time.perf_counter()

    storage_opts = None if local_path_pattern else _DEFAULT_STORAGE_OPTIONS

    try:
        gen = ReferenceGenerator(
            urls,
            filters={"typeOfFirstFixedSurface": 10},
            storage_options=storage_opts,
            max_workers=max_workers,
        )
        manifest = gen.generate()
    except Exception as exc:
        logger.error(
            "ingest_date.manifest_generation_failed",
            date=date,
            cycle=cycle,
            error=str(exc),
        )
        return False

    t_manifest = time.perf_counter()
    logger.info(
        "ingest_date.manifest_generated",
        date=date,
        cycle=cycle,
        duration_s=round(t_manifest - t_start, 3),
    )

    # Save manifest to disk
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        logger.info(
            "ingest_date.manifest_saved",
            date=date,
            cycle=cycle,
            path=str(manifest_path),
            size_mb=round(manifest_path.stat().st_size / 1024 / 1024, 2),
        )
    except Exception as exc:
        logger.error(
            "ingest_date.save_failed",
            date=date,
            cycle=cycle,
            error=str(exc),
        )
        return False

    # Verify the manifest can be opened as an xarray dataset
    try:
        import xarray as xr

        remote_opts: dict = {"asynchronous": True}
        if not local_path_pattern:
            remote_opts.update(_DEFAULT_STORAGE_OPTIONS)

        ref_fs = fsspec.filesystem(
            "reference",
            fo=str(manifest_path),
            asynchronous=True,
            remote_options=remote_opts,
        )
        ds = xr.open_dataset(
            ref_fs.get_mapper(""),
            engine="zarr",
            consolidated=False,
        )
        logger.info(
            "ingest_date.verified",
            date=date,
            cycle=cycle,
            dimensions=dict(ds.sizes),
            variables=list(ds.data_vars)[:10],
        )
        ds.close()
    except Exception as exc:
        logger.warning(
            "ingest_date.verification_failed",
            date=date,
            cycle=cycle,
            error=str(exc),
        )
        # Keep the manifest even if verification fails - it might still
        # work with different xarray/zarr settings

    total_time = time.perf_counter() - t_start
    logger.info(
        "ingest_date.complete",
        date=date,
        cycle=cycle,
        total_duration_s=round(total_time, 3),
    )
    return True


def main() -> None:
    """CLI entry point for the ingest script."""
    parser = argparse.ArgumentParser(
        description="Ingest GEFS-Aerosols GRIB2 data into local Kerchunk manifests."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of most recent days to ingest (default: 3)",
    )
    parser.add_argument(
        "--store-path",
        type=str,
        default="data/manifests/gefs",
        help="Path to the manifest store directory (default: data/manifests/gefs)",
    )
    parser.add_argument(
        "--cycle",
        type=str,
        default="00",
        help="Model initialization cycle to ingest (default: 00)",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=_DEFAULT_BUCKET,
        help=f"S3 bucket name (default: {_DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=_DEFAULT_MAX_WORKERS,
        help=f"Thread-pool size for manifest generation (default: {_DEFAULT_MAX_WORKERS})",
    )
    parser.add_argument(
        "--forecast-hours",
        type=str,
        default=None,
        help="Comma-separated forecast hours (default: 0-120). Example: 0,3,6,12,24",
    )
    parser.add_argument(
        "--local-path",
        type=str,
        default=None,
        help=(
            "Path to local GRIB2 files (offline mode, no S3 access needed). "
            "Uses same path pattern with {date}, {cycle}, {fhr} placeholders. "
            "Example: /data/gefs.{date}/{cycle}/chem/pgrb2ap25/gefs.chem.t{cycle}z.a2d_0p25.f{fhr:03d}.grib2"
        ),
    )

    args = parser.parse_args()

    store_path = Path(args.store_path)
    store_path.mkdir(parents=True, exist_ok=True)

    # Parse forecast hours
    forecast_hours: list[int] | None = None
    if args.forecast_hours:
        forecast_hours = [int(h.strip()) for h in args.forecast_hours.split(",")]

    # Local mode: use local file paths instead of S3
    local_path = args.local_path

    print(f"\n{'=' * 60}")
    print("  GEFS-Aerosols Manifest Ingest")
    print(f"{'=' * 60}")
    print(f"  Days:           {args.days}")
    print(f"  Cycle:          {args.cycle}")
    print(f"  Store path:     {store_path.resolve()}")
    print(f"  Bucket:         {args.bucket}")
    print(f"  Max workers:    {args.max_workers}")
    print(f"  Forecast hours: {forecast_hours or '0-120 (all)'}")
    print(f"{'=' * 60}\n")

    # Discover available dates
    t0 = time.perf_counter()
    if local_path:
        import re

        print("[1/3] Discovering available dates from local path...")
        # Extract base directory before {date} placeholder
        base = local_path.split("{date}")[0] if "{date}" in local_path else local_path
        parent = Path(base).resolve()
        if not parent.is_dir() and parent.parent.is_dir():
            parent = parent.parent
        dates = []
        if parent.is_dir():
            for entry in sorted(parent.iterdir()):
                match = re.search(r"(\d{8})", entry.name)
                if match and entry.is_dir():
                    dates.append(match.group(1))
            if not dates:
                match = re.search(r"(\d{8})", parent.name)
                if match:
                    dates.append(match.group(1))
        dates.sort()
    else:
        print("[1/3] Discovering available dates from S3...")
        dates = discover_available_dates(args.bucket)
    t_discover = time.perf_counter() - t0

    if not dates:
        print("  ERROR: No dates discovered. Check path/connectivity.")
        sys.exit(1)

    print(f"  Found {len(dates)} dates in {t_discover:.1f}s")
    print(f"  Latest: {dates[-1]}, Earliest: {dates[0]}")

    # Select most recent N days
    selected_dates = dates[-args.days :]
    print(f"\n[2/3] Ingesting {len(selected_dates)} most recent date(s)...")
    print(f"  Dates: {selected_dates}")

    # Ingest each date
    successes = 0
    failures = 0
    t_ingest_start = time.perf_counter()

    for i, date in enumerate(selected_dates, 1):
        print(f"\n  [{i}/{len(selected_dates)}] Ingesting {date}/{args.cycle}...")
        success = ingest_date(
            date=date,
            cycle=args.cycle,
            store_path=store_path,
            bucket=args.bucket,
            forecast_hours=forecast_hours,
            max_workers=args.max_workers,
            local_path_pattern=local_path,
        )
        if success:
            successes += 1
        else:
            failures += 1

    t_ingest_total = time.perf_counter() - t_ingest_start

    # Summary
    print(f"\n{'=' * 60}")
    print("  [3/3] Ingest Complete")
    print(f"{'=' * 60}")
    print(f"  Succeeded: {successes}/{len(selected_dates)}")
    print(f"  Failed:    {failures}/{len(selected_dates)}")
    print(f"  Duration:  {t_ingest_total:.1f}s")
    print(f"  Store:     {store_path.resolve()}")
    print(f"{'=' * 60}\n")

    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
