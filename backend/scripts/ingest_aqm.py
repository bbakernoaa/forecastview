#!/usr/bin/env python
"""Ingest AQMv7 data into the ForecastView manifest store.

AQMv7 files are structured as one GRIB2 per variable containing all
forecast hours. This script creates Kerchunk JSON manifests for each
date/run combination.

Usage:
    conda run -n forecastview python backend/scripts/ingest_aqm.py [--days N] [--domain CS]

The AQMv7 data lives at:
    s3://noaa-nws-naqfc-pds/AQMv7/{domain}/{date}/{run}/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import s3fs

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

_BUCKET = "noaa-nws-naqfc-pds"
_PRODUCT_ID = "aqm"
_DOMAINS = ["CS", "AK", "HI"]
_DEFAULT_DOMAIN = "CS"


def discover_dates(fs: s3fs.S3FileSystem, domain: str, limit: int = 5) -> list[str]:
    """Discover available dates from S3."""
    prefix = f"{_BUCKET}/AQMv7/{domain}/"
    dirs = fs.ls(prefix)
    dates = []
    for d in dirs:
        name = d.split("/")[-1]
        if len(name) == 8 and name.isdigit():
            dates.append(name)
    dates.sort()
    return dates[-limit:]


def discover_runs(fs: s3fs.S3FileSystem, domain: str, date: str) -> list[str]:
    """Discover available runs for a date."""
    prefix = f"{_BUCKET}/AQMv7/{domain}/{date}/"
    dirs = fs.ls(prefix)
    runs = []
    for d in dirs:
        name = d.split("/")[-1]
        if len(name) == 2 and name.isdigit():
            runs.append(name)
    return sorted(runs)


def list_grib_files(fs: s3fs.S3FileSystem, domain: str, date: str, run: str) -> list[str]:
    """List GRIB2 files for a date/run."""
    prefix = f"{_BUCKET}/AQMv7/{domain}/{date}/{run}/"
    files = fs.ls(prefix)
    return [f for f in files if f.endswith(".grib2")]


def parse_variable_from_filename(filename: str) -> str:
    """Extract variable name from AQM filename.

    Example: aqm.t12z.ave_1hr_pm25.20260820.227.grib2 → ave_1hr_pm25
    """
    parts = filename.split(".")
    # Format: aqm.t{run}z.{variable}.{date}.{xxx}.grib2
    if len(parts) >= 4:
        return parts[2]
    return filename


def build_manifest(
    fs: s3fs.S3FileSystem,
    domain: str,
    date: str,
    run: str,
    store_path: Path,
) -> bool:
    """Build a manifest for one date/run by storing file references.

    For AQM, we store a simple JSON manifest that maps variable names
    to their S3 URIs. The field selector will open them directly via
    grib2io + s3fs rather than using Kerchunk references.
    """
    files = list_grib_files(fs, domain, date, run)
    if not files:
        print(f"  No GRIB2 files found for {date}/{run}")
        return False

    manifest = {
        "product": _PRODUCT_ID,
        "domain": domain,
        "date": date,
        "run": run,
        "bucket": _BUCKET,
        "variables": {},
    }

    for filepath in files:
        filename = filepath.split("/")[-1]
        var_name = parse_variable_from_filename(filename)
        manifest["variables"][var_name] = {
            "s3_key": filepath,
            "filename": filename,
        }

    # Save manifest
    out_dir = store_path / f"{_PRODUCT_ID}_{domain}" / date / run
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return True


def main():
    parser = argparse.ArgumentParser(description="Ingest AQMv7 data")
    parser.add_argument("--days", type=int, default=3, help="Number of recent days to ingest")
    parser.add_argument("--domain", type=str, default=_DEFAULT_DOMAIN, choices=_DOMAINS)
    args = parser.parse_args()

    store_path = Path(__file__).resolve().parent.parent.parent / "data" / "manifests"
    fs = s3fs.S3FileSystem(anon=True)

    print("=" * 60)
    print("  AQMv7 Manifest Ingest")
    print("=" * 60)
    print(f"  Domain:    {args.domain}")
    print(f"  Days:      {args.days}")
    print(f"  Store:     {store_path}")
    print("=" * 60)

    t_start = time.time()

    # Discover dates
    dates = discover_dates(fs, args.domain, limit=args.days)
    print(f"\n  Found {len(dates)} dates: {dates}")

    succeeded = 0
    failed = 0

    for date in dates:
        runs = discover_runs(fs, args.domain, date)
        for run in runs:
            print(f"\n  [{date}/{run}] Ingesting...")
            try:
                ok = build_manifest(fs, args.domain, date, run, store_path)
                if ok:
                    files = list_grib_files(fs, args.domain, date, run)
                    print(f"    ✓ {len(files)} variables")
                    succeeded += 1
                else:
                    failed += 1
            except Exception as exc:
                print(f"    ✗ Error: {exc}")
                failed += 1

    t_total = time.time() - t_start
    print("\n" + "=" * 60)
    print(f"  Done: {succeeded} succeeded, {failed} failed in {t_total:.1f}s")
    print(f"  Store: {store_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
