#!/usr/bin/env python
"""Inspect and validate local GRIB2 dataset definitions for static exports."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import re
import shutil
import stat
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config" / "domains"


def load_definition(path: Path) -> tuple[dict, Path]:
    path = path.resolve()
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("product"), dict):
        raise ValueError("expected a YAML mapping with a product mapping")
    product = raw["product"]
    product_id = product.get("id")
    if not isinstance(product_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", product_id):
        raise ValueError("product.id must start with a letter and contain only letters, numbers, _ or -")
    if not isinstance(product.get("name"), str) or not product["name"].strip():
        raise ValueError("product.name must be a non-empty display name")
    ingest = raw.get("ingest")
    if not isinstance(ingest, dict):
        raise ValueError("ingest must define source_dir and store_path for local static onboarding")
    source = ingest.get("source_dir")
    store = ingest.get("store_path")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("ingest.source_dir must name a local GRIB2 directory")
    if not isinstance(store, str) or not store.strip():
        raise ValueError("ingest.store_path must name a manifest directory")
    input_format = ingest.get("format", "grib2")
    if not isinstance(input_format, str) or input_format.lower() != "grib2":
        raise ValueError("ingest.format currently supports only 'grib2'")
    expected_hours = ingest.get("expected_forecast_hours")
    if expected_hours is not None and (
        not isinstance(expected_hours, list)
        or not expected_hours
        or any(isinstance(hour, bool) or not isinstance(hour, int) or hour < 0 for hour in expected_hours)
        or len(expected_hours) != len(set(expected_hours))
    ):
        raise ValueError("ingest.expected_forecast_hours must be unique non-negative integer hours")
    source_path = (path.parent / source).resolve() if not Path(source).is_absolute() else Path(source)
    if not source_path.is_dir():
        raise ValueError(f"ingest.source_dir does not exist or is not a directory: {source_path}")
    pattern = ingest.get("file_glob", "**/*.grib2")
    if (
        not isinstance(pattern, str)
        or not pattern.strip()
        or Path(pattern).is_absolute()
        or ".." in Path(pattern).parts
    ):
        raise ValueError("ingest.file_glob must be a relative pattern contained in source_dir")
    if not any(candidate.is_file() for candidate in source_path.glob(pattern)):
        raise ValueError(f"ingest.file_glob matched no files: {pattern!r} in {source_path}")
    variables = raw.get("variables")
    if not isinstance(variables, dict) or not variables:
        raise ValueError("variables must contain at least one configured GRIB variable")
    for name, var in variables.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
            raise ValueError(f"unsafe variable name {name!r}; use letters, numbers, _ or -")
        if not isinstance(var, dict):
            raise ValueError(f"variables.{name} must be a mapping")
        for display_field in ("shortName", "fullName"):
            if not isinstance(var.get(display_field), str) or not var[display_field].strip():
                raise ValueError(f"variables.{name}.{display_field} must be a non-empty string")
        rendering = var.get("rendering", {})
        if not isinstance(rendering, dict):
            raise ValueError(f"variables.{name}.rendering must be a mapping")
        levels = rendering.get("fillLevels", [])
        if (
            not isinstance(levels, list)
            or any(
                isinstance(x, bool)
                or not isinstance(x, (int, float))
                or not math.isfinite(x)
                for x in levels
            )
            or levels != sorted(set(levels))
        ):
            raise ValueError(f"variables.{name}.rendering.fillLevels must be strictly increasing numbers")
        interval = rendering.get("contourInterval", 0.1)
        if (
            isinstance(interval, bool)
            or not isinstance(interval, (int, float))
            or not math.isfinite(interval)
            or interval <= 0
        ):
            raise ValueError(f"variables.{name}.rendering.contourInterval must be a positive finite number")
    return raw, source_path


def list_definitions() -> int:
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text()) or {}
            product = raw.get("product", {})
            print(f"{product.get('id', '?')}\t{product.get('name', path.stem)}\t{path}")
        except (OSError, yaml.YAMLError) as exc:
            print(f"ERROR\t{path}\t{exc}", file=sys.stderr)
            return 1
    return 0


def validate_manifest_dataset(
    dataset,
    configured_variables: set[str],
    expected_forecast_hours: set[int] | None = None,
    init_time: datetime | None = None,
) -> set[str]:
    """Reject incomplete variable, level, and geolocation layouts before publish."""
    available_variables = set(dataset.data_vars)
    if not available_variables:
        raise ValueError("manifest contains no data variables")
    missing_variables = configured_variables - available_variables
    if missing_variables:
        raise ValueError(
            "configured variables missing from manifest: "
            + ", ".join(sorted(missing_variables))
        )
    latitude = next((dataset[name] for name in ("latitude", "lat") if name in dataset), None)
    longitude = next((dataset[name] for name in ("longitude", "lon") if name in dataset), None)
    if latitude is None or longitude is None:
        raise ValueError("manifest has no geographic latitude/longitude coordinates")
    if latitude.ndim == longitude.ndim == 1:
        pass  # regular latitude/longitude axes
    elif latitude.ndim == longitude.ndim == 2 and latitude.shape == longitude.shape:
        pass  # projected or curvilinear geolocation arrays
    else:
        raise ValueError("latitude/longitude coordinates must be matching 1-D axes or 2-D arrays")
    for name in configured_variables:
        variable = dataset[name]
        ambiguous_dims = [
            dim for dim in variable.dims
            if dim not in {"valid_time", "time", "y", "x", "latitude", "longitude"}
            and dataset.sizes.get(dim, 1) > 1
        ]
        if ambiguous_dims:
            raise ValueError(
                f"variables.{name} has multiple selectable levels in dimensions "
                f"{', '.join(ambiguous_dims)}; static exports support one level per variable"
            )
        if expected_forecast_hours:
            if init_time is None:
                raise ValueError(
                    f"init_time is required to validate forecast hours for variables.{name}"
                )
            time_dim = next((dim for dim in ("valid_time", "time") if dim in variable.dims), None)
            if time_dim is None:
                hour = min(expected_forecast_hours)
                raise ValueError(
                    f"variables.{name} has no time coordinate to validate forecast hour {hour}"
                )
            try:
                times = np.asarray(dataset[time_dim].values).astype("datetime64[ns]")
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"variables.{name} has an invalid datetime coordinate {time_dim!r}"
                ) from exc
            for hour in sorted(expected_forecast_hours):
                expected_time = np.datetime64(init_time + timedelta(hours=hour), "ns")
                matching = np.flatnonzero(times == expected_time)
                if not matching.size:
                    raise ValueError(
                        f"variables.{name} is missing forecast hour {hour}"
                    )
                values = np.asarray(variable.isel({time_dim: matching}).values)
                if not np.isfinite(values).any():
                    raise ValueError(
                        f"variables.{name} has no valid data at forecast hour {hour}"
                    )
    return available_variables


def inspect_files(directory: Path, pattern: str) -> int:
    files = sorted(directory.glob(pattern))
    if not files:
        print(f"No files matched {pattern!r} in {directory}", file=sys.stderr)
        return 1
    try:
        import grib2io
    except ImportError as exc:
        print("grib2io is required; activate the forecastview environment", file=sys.stderr)
        raise SystemExit(2) from exc
    records = []
    for path in files:
        try:
            with grib2io.open(path) as grbs:
                for message in grbs:
                    records.append({
                        "file": str(path),
                        "date": f"{message.year:04d}{message.month:02d}{message.day:02d}",
                        "cycle": f"{message.hour:02d}",
                        "forecast_hour": int(message.leadTime.total_seconds() / 3600),
                        "short_name": getattr(message, "shortName", None),
                        "level": getattr(message, "level", None),
                        "surface_type": getattr(message, "typeOfFirstFixedSurface", None),
                        "surface_value": getattr(message, "valueOfFirstFixedSurface", None),
                        "units": getattr(message, "parameterUnits", None),
                        "parameter": {
                            "discipline": int(message.discipline),
                            "category": int(message.parameterCategory),
                            "number": int(message.parameterNumber),
                        },
                        "grid_template": int(message.gridDefinitionTemplateNumber),
                        "grid_dimensions": {
                            "nx": int(message.nx),
                            "ny": int(message.ny),
                        },
                    })
        except Exception as exc:
            print(f"Cannot inspect {path}: {exc}", file=sys.stderr)
            return 1
    print(json.dumps(records, indent=2, default=str))
    return 0


def ingest_local(config_path: Path) -> int:
    """Create manifests while holding an exclusive per-dataset writer lock."""
    raw, source = load_definition(config_path)
    store_value = Path(raw["ingest"]["store_path"])
    store = (ROOT / store_value).resolve() if not store_value.is_absolute() else store_value
    store.mkdir(parents=True, exist_ok=True)
    lock_path = store / ".ingest.lock"
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"another ingest is writing {store}; wait for it to finish and retry") from exc
        try:
            return _ingest_local(raw, source, store)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _ingest_local(raw: dict, source: Path, store: Path) -> int:
    """Create verified Kerchunk manifests from a dataset's local GRIB2 files."""
    ingest = raw["ingest"]
    pattern = ingest.get("file_glob", "**/*.grib2")
    files = sorted(source.glob(pattern))
    report = {
        "dataset": raw["product"]["id"],
        "source_dir": str(source),
        "file_glob": pattern,
        "files": [str(path) for path in files if path.is_file()],
        "runs": [],
        "status": "running",
        "startedAt": datetime.now(UTC).isoformat(),
    }
    report_path = store / "ingest-report.json"

    def save_report(status: str, error: str | None = None) -> None:
        report["status"] = status
        report["completedAt"] = datetime.now(UTC).isoformat()
        if error:
            report["error"] = error
        staged_report = store / f".ingest-report-{os.getpid()}.tmp"
        staged_report.write_text(json.dumps(report, indent=2, sort_keys=True))
        os.replace(staged_report, report_path)

    if not files:
        error = f"No files matched {pattern!r} in {source}"
        print(error, file=sys.stderr)
        save_report("failed", error)
        return 1
    import grib2io
    from grib2io.kerchunk import ReferenceGenerator
    import fsspec
    import xarray as xr

    groups: dict[tuple[str, str], list[Path]] = {}
    forecast_hours: dict[tuple[str, str], set[int]] = {}
    for path in files:
        try:
            with grib2io.open(path) as grbs:
                if len(grbs) == 0:
                    raise ValueError("file contains no GRIB messages")
                msg = grbs[0]
                date = f"{msg.year:04d}{msg.month:02d}{msg.day:02d}"
                cycle = f"{msg.hour:02d}"
                for other in grbs:
                    if (other.year, other.month, other.day, other.hour) != (msg.year, msg.month, msg.day, msg.hour):
                        raise ValueError("file contains messages from different initialization times")
                    lead_hours = other.leadTime.total_seconds() / 3600
                    if not lead_hours.is_integer() or lead_hours < 0:
                        raise ValueError(f"unsupported non-hourly or negative forecast lead: {lead_hours}")
                    forecast_hours.setdefault((date, cycle), set()).add(int(lead_hours))
            datetime.strptime(date + cycle, "%Y%m%d%H")
            groups.setdefault((date, cycle), []).append(path)
        except Exception as exc:
            error = f"Cannot identify a consistent initialization time in {path}: {exc}"
            print(error, file=sys.stderr)
            save_report("failed", error)
            return 1

    filters = ingest.get("filters") or None
    for (date, cycle), run_files in sorted(groups.items()):
        expected = set(ingest.get("expected_forecast_hours") or [])
        missing_hours = sorted(expected - forecast_hours.get((date, cycle), set()))
        if missing_hours:
            error = (
                f"Incomplete {date}/{cycle}; missing configured forecast hours: "
                + ", ".join(map(str, missing_hours))
            )
            print(
                error,
                file=sys.stderr,
            )
            report["runs"].append({"date": date, "cycle": cycle, "status": "incomplete", "missing_hours": missing_hours})
            save_report("failed", error)
            return 1
        target = store / date / cycle / "manifest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".manifest-", dir=target.parent))
        stage = stage_dir / "manifest.json"
        try:
            generator = ReferenceGenerator([str(p.resolve()) for p in run_files], filters=filters)
            stage.write_text(json.dumps(generator.generate()))
            ref_fs = fsspec.filesystem("reference", fo=str(stage), asynchronous=True,
                                       remote_options={"asynchronous": True})
            ds = xr.open_dataset(ref_fs.get_mapper(""), engine="zarr", consolidated=False)
            try:
                available_variables = validate_manifest_dataset(
                    ds,
                    set(raw["variables"]),
                    expected_forecast_hours=expected or None,
                    init_time=datetime.strptime(date + cycle, "%Y%m%d%H"),
                )
                print(f"Verified {date}/{cycle}: {len(run_files)} file(s), {len(available_variables)} variable(s)")
            finally:
                ds.close()
            os.replace(stage, target)
        except Exception as exc:
            error = f"Failed {date}/{cycle}; existing manifest preserved: {exc}"
            print(error, file=sys.stderr)
            report["runs"].append({"date": date, "cycle": cycle, "status": "failed", "error": str(exc)})
            save_report("failed", error)
            return 1
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)
        report["runs"].append({
            "date": date,
            "cycle": cycle,
            "status": "verified",
            "files": [str(path) for path in run_files],
            "forecast_hours": sorted(forecast_hours.get((date, cycle), set())),
        })
    save_report("success")
    return 0


def check_site(site: Path) -> int:
    """Check the core static catalog and referenced metadata files."""
    site = site.resolve()
    catalog_path = site / "data" / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid or missing catalog {catalog_path}: {exc}", file=sys.stderr)
        return 1
    errors = []
    for item in catalog.get("products", []):
        product = item.get("product")
        if not isinstance(product, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", product):
            errors.append(f"invalid product entry: {item}")
            continue
        dates_path = site / "data" / product / "dates.json"
        try:
            dates = json.loads(dates_path.read_text()).get("dates", [])
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{product}: missing or invalid dates.json ({exc})")
            continue
        for date in dates:
            runs_path = site / "data" / product / date / "runs.json"
            try:
                runs = json.loads(runs_path.read_text()).get("runs", [])
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"{product}/{date}: missing or invalid runs.json ({exc})")
                continue
            for run in runs:
                run_dir = site / "data" / product / date / run
                metadata = {}
                for name in ("variables.json", "levels.json", "times.json"):
                    try:
                        metadata[name] = json.loads((run_dir / name).read_text())
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"{product}/{date}/{run}: missing or invalid {name} ({exc})")
                if not metadata:
                    continue
                variables = metadata.get("variables.json", {}).get("variables", [])
                hours = metadata.get("times.json", {}).get("forecast_hours", [])
                grid_path = run_dir / "grid.json"
                has_field_export = (run_dir / "field").exists()
                expected_field_bytes = None
                if has_field_export or grid_path.exists():
                    try:
                        grid = json.loads(grid_path.read_text())
                        nx, ny = int(grid["nx"]), int(grid["ny"])
                        expected_field_bytes = nx * ny * 4
                        if grid.get("coordinates"):
                            coordinate_file = run_dir / grid["coordinates"]
                            if not coordinate_file.is_file() or coordinate_file.stat().st_size != nx * ny * 8:
                                errors.append(f"{product}/{date}/{run}: coordinate grid size mismatch")
                    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                        expected_field_bytes = None
                        errors.append(f"{product}/{date}/{run}: invalid or missing grid.json")
                for variable in variables:
                    var_name = variable.get("name")
                    for hour in hours:
                        fhr = int(hour["fhr"])
                        frame = f"f{fhr:03d}"
                        required = [run_dir / "fill" / var_name / f"{frame}.png"]
                        if (run_dir / "contours" / var_name).exists():
                            required.append(run_dir / "contours" / var_name / f"{frame}.json")
                        if (run_dir / "field" / var_name).exists():
                            required.append(run_dir / "field" / var_name / f"{frame}.bin")
                        for artifact in required:
                            if not artifact.is_file() or artifact.stat().st_size == 0:
                                errors.append(f"{product}/{date}/{run}: missing artifact {artifact.relative_to(site)}")
                            elif artifact.suffix == ".png":
                                try:
                                    from PIL import Image

                                    with Image.open(artifact) as image:
                                        image.verify()
                                except Exception as exc:
                                    errors.append(f"{product}/{date}/{run}: invalid image {artifact.relative_to(site)} ({exc})")
                            elif artifact.suffix == ".bin" and expected_field_bytes is not None:
                                if artifact.stat().st_size != expected_field_bytes:
                                    errors.append(f"{product}/{date}/{run}: field grid size mismatch for {artifact.relative_to(site)}")
                            elif artifact.suffix == ".json" and "contours" in artifact.parts:
                                try:
                                    contour = json.loads(artifact.read_text())
                                    if contour.get("type") != "FeatureCollection" or not isinstance(contour.get("features"), list):
                                        raise ValueError("expected FeatureCollection")
                                except (OSError, json.JSONDecodeError, AttributeError, ValueError) as exc:
                                    errors.append(f"{product}/{date}/{run}: invalid contours {artifact.relative_to(site)} ({exc})")
    if errors:
        print("Static site check failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"Static catalog valid: {len(catalog.get('products', []))} product(s)")
    return 0


def export_product(config_path: Path, output: Path) -> int:
    """Invoke the static exporter with one dataset definition."""
    raw, _ = load_definition(config_path)
    import subprocess

    command = [sys.executable, str(ROOT / "backend/scripts/export_static.py"),
               "--product", raw["product"]["id"], "--config", str(config_path.resolve()),
               "--output", str(output.resolve())]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def build_site(config_paths: list[Path], output: Path) -> int:
    """Build multiple datasets while serializing updates for this bundle."""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.with_name(f".{output.name}.lock")
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        _recover_bundle_swap(output)
        return _build_site_locked(config_paths, output)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _recover_bundle_swap(output: Path) -> None:
    """Restore an interrupted swap, or remove a backup after a committed swap."""
    backup = output.with_name(f".{output.name}.previous")
    if not backup.exists():
        return
    if not output.exists():
        os.replace(backup, output)
    else:
        _remove_path(backup)


def _build_site_locked(config_paths: list[Path], output: Path) -> int:
    candidate = Path(tempfile.mkdtemp(prefix=f".{output.name}.candidate-", dir=output.parent))
    backup = output.with_name(f".{output.name}.previous")
    try:
        if output.exists():
            shutil.rmtree(candidate)
            shutil.copytree(output, candidate)
        for config_path in config_paths:
            if export_product(config_path, candidate):
                print(f"Build failed for {config_path}; existing site directory left unchanged", file=sys.stderr)
                return 1
        if check_site(candidate):
            print("Candidate check failed; existing site directory left unchanged", file=sys.stderr)
            return 1
        for path in [candidate, *candidate.rglob("*")]:
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                path.chmod(0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644)
        catalog_path = candidate / "data" / "catalog.json"
        try:
            dataset_ids = [
                item["product"] for item in json.loads(catalog_path.read_text()).get("products", [])
                if isinstance(item.get("product"), str)
            ]
        except (OSError, json.JSONDecodeError, AttributeError):
            dataset_ids = [load_definition(path)[0]["product"]["id"] for path in config_paths]
        (candidate / "export-info.json").write_text(json.dumps({
            "exportedAt": datetime.now(UTC).isoformat(),
            "datasets": dataset_ids,
        }, sort_keys=True))
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(candidate, output)
        except OSError:
            if backup.exists() and not output.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            _remove_path(backup)
        print(f"Updated static site bundle: {output}")
        return 0
    except Exception as exc:
        print(f"Update failed; previous bundle preserved: {exc}", file=sys.stderr)
        return 1
    finally:
        if candidate.exists():
            shutil.rmtree(candidate, ignore_errors=True)


def update_site(config_path: Path, output: Path) -> int:
    """Ingest one dataset and atomically publish an updated local bundle."""
    return build_site([config_path], output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list configured dataset definitions")
    validate = sub.add_parser("validate", help="validate local dataset YAML")
    validate.add_argument("--config", required=True, type=Path)
    ingest = sub.add_parser("ingest", help="ingest local GRIB2 files to verified manifests")
    ingest.add_argument("--config", required=True, type=Path)
    inspect = sub.add_parser("inspect", help="inspect headers in local GRIB2 files")
    inspect.add_argument("--input", required=True, type=Path)
    inspect.add_argument("--glob", default="**/*.grib2")
    build = sub.add_parser("build", help="export one or more configured datasets into a static site")
    build.add_argument("--config", required=True, action="append", type=Path,
                       help="dataset YAML (repeat for each dataset to include)")
    build.add_argument("--output", required=True, type=Path)
    check = sub.add_parser("check", help="validate a generated static site")
    check.add_argument("--site", required=True, type=Path)
    update = sub.add_parser("update", help="ingest, build and check a static dataset site")
    update.add_argument("--config", required=True, type=Path)
    update.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "list":
        return list_definitions()
    if args.command == "inspect":
        return inspect_files(args.input.resolve(), args.glob)
    if args.command == "ingest":
        try:
            return ingest_local(args.config)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"Ingest failed: {exc}", file=sys.stderr)
            return 1
    if args.command == "check":
        return check_site(args.site)
    if args.command == "build":
        return build_site(args.config, args.output)
    if args.command == "update":
        status = ingest_local(args.config)
        if status:
            return status
        return update_site(args.config, args.output)
    try:
        raw, source = load_definition(args.config)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"Invalid dataset definition: {exc}", file=sys.stderr)
        return 1
    print(f"Valid: {raw['product']['id']} — {raw['product']['name']}\nSource: {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
