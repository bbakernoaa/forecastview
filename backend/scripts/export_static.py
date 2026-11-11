#!/usr/bin/env python
"""Export ForecastView as a fully static site for RZDM deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.app.config.loader import DomainConfig
from backend.app.contours.geojson import shift_grid_to_minus180

WEB_MERCATOR_MAX_LAT = 85.06
CRS_4326 = CRS.from_epsg(4326)
CRS_3857 = CRS.from_epsg(3857)
MX = 20037508.3427892


def export_fingerprint(config_data, store_path, product, no_fields, no_contours):
    """Hash render settings, exporter code, options, and run manifests."""
    manifests = {}
    for date_dir in sorted(Path(store_path).glob("[0-9]" * 8)):
        if not date_dir.is_dir():
            continue
        for run_dir in sorted(date_dir.iterdir()):
            manifest = run_dir / "manifest.json"
            if manifest.is_file():
                manifests[f"{date_dir.name}/{run_dir.name}"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    payload = {
        "schema": 1,
        "config": config_data,
        "store_manifests": manifests,
        "exporter": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "no_fields": no_fields,
        "no_contours": no_contours,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def render_fill_png(field, lons_1d, lats_1d, fill_levels, cmap_name):
    field = np.asarray(field, dtype=np.float32)
    lons = np.asarray(lons_1d, dtype=np.float64)
    lats = np.asarray(lats_1d, dtype=np.float64)
    if lons.ndim == 1 and lats.ndim == 1:
        sf, sl, _ = shift_grid_to_minus180(field, lons)
        if not np.array_equal(sl, lons):
            field, lons = sf, sl
        vm = (lats >= -WEB_MERCATOR_MAX_LAT) & (lats <= WEB_MERCATOR_MAX_LAT)
        vr = np.where(vm)[0]
        if not len(vr):
            raise ValueError("grid has no points inside Web Mercator latitude limits")
        field = field[vr[0] : vr[-1] + 1, :]
        cropped_lats = lats[vr[0] : vr[-1] + 1]
        src_transform = from_bounds(
            float(lons[0]),
            float(cropped_lats[-1]),
            float(lons[-1]) + (lons[1] - lons[0]),
            float(cropped_lats[0]),
            field.shape[1],
            field.shape[0],
        )
        geoloc = None
    elif lons.ndim == 2 and lats.ndim == 2 and lons.shape == lats.shape == field.shape:
        # GDAL's geolocation-array transformer maps every source cell from its
        # own geographic coordinate. This handles projected and curvilinear
        # grids without approximating them as separable axes.
        lons = np.where(lons > 180.0, lons - 360.0, lons)
        valid = np.isfinite(lons) & np.isfinite(lats) & (np.abs(lats) <= WEB_MERCATOR_MAX_LAT)
        field = np.where(valid, field, np.nan)
        lons = np.where(valid, lons, np.nan)
        lats = np.where(valid, lats, np.nan)
        src_transform = None
        geoloc = (lons, lats)
    else:
        raise ValueError("field and coordinate arrays must be matching 1-D axes or 2-D geolocation arrays")
    dt = from_bounds(-MX, -MX, MX, MX, 2048, 2048)
    dst = np.full((2048, 2048), np.nan, dtype=np.float32)
    reproject(
        source=field,
        destination=dst,
        src_transform=src_transform,
        src_geoloc_array=geoloc,
        src_crs=CRS_4326,
        dst_transform=dt,
        dst_crs=CRS_3857,
        resampling=Resampling.bilinear,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    nl = len(fill_levels)
    try:
        cmap = colormaps[cmap_name]
    except (KeyError, ValueError):
        cmap = colormaps["turbo"]
    rgba = np.zeros((nl + 1, 4), dtype=np.uint8)
    for i in range(nl):
        t = i / max(nl - 1, 1)
        r, g, b, _ = cmap(t)
        rgba[i + 1] = (int(r * 255), int(g * 255), int(b * 255), 255)
    bi = np.digitize(dst, fill_levels)
    bi[~np.isfinite(dst)] = 0
    img = Image.fromarray(rgba[bi].astype(np.uint8), mode="RGBA")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_contour_geojson(field, lons_1d, lats_1d, coords, projection, interval, major_interval):
    """Return a GeoJSON FeatureCollection dict for one field frame.

    Mirrors the /api/contours response shape (type, features, metadata) so
    the frontend's useContours hook consumes static files unchanged.
    """
    from backend.app.contours.generator import generate_isolines
    from backend.app.contours.geojson import contours_to_geojson
    from backend.app.data.field_selector import GridCoordinates
    from backend.app.projections.coordinates import CoordinateMapper
    from backend.app.projections.transform import CoordinateTransformer

    sf, sl, _ = shift_grid_to_minus180(field, lons_1d)
    coordinates = coords
    if not np.array_equal(sl, lons_1d):
        lons_2d, lats_2d = np.meshgrid(sl, lats_1d)
        coordinates = GridCoordinates(lats=lats_2d, lons=lons_2d, shape=coords.shape)
    result = generate_isolines(sf, interval=interval, major_interval=major_interval)
    transformer = CoordinateTransformer.from_projection(projection)
    mapper = CoordinateMapper(coordinates, projection)
    geojson = contours_to_geojson(result, mapper, transformer)
    valid = sf[np.isfinite(sf)]
    metadata = {
        "variable": None,
        "level": None,
        "fhr": None,
        "contourInterval": interval,
        "majorInterval": major_interval,
        "fieldMin": float(valid.min()) if valid.size else 0.0,
        "fieldMax": float(valid.max()) if valid.size else 0.0,
        "numLevels": len(result.levels),
        "numFeatures": len(geojson.get("features", [])),
    }
    return {
        "type": "FeatureCollection",
        "features": geojson.get("features", []),
        "metadata": metadata,
    }


def render_one(args):
    sp, date, run, var, fhr, fl, cm, op, want_fields, want_contours, interval = args
    from backend.app.data.field_selector import FieldSelector
    from backend.app.data.kerchunk_store import ManifestStore

    s = ManifestStore(sp)
    sel = FieldSelector(s)
    field = sel.select(date, run, var, fhr=fhr)
    c = sel.get_coordinates(date, run)
    lo, la = c.lons, c.lats
    png = render_fill_png(field, lo, la, fl, cm)
    p = Path(op)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(png)
    # Fill path is <run>/fill/<var>/f<NNN>.png -> run dir is 3 levels up.
    run_dir = p.parent.parent.parent
    if want_fields:
        if lo.ndim == 1 and la.ndim == 1:
            sf, sl, _ = shift_grid_to_minus180(field, lo)
            if not np.array_equal(sl, lo):
                lo, sf = sl, sf
            # Preserve the complete source grid so clicks and values share indices.
            lon2d, lat2d = np.meshgrid(lo, la)
        else:
            sf = np.asarray(field)
            lon2d = np.where(lo > 180.0, lo - 360.0, lo)
            lat2d = np.asarray(la)
        field_dir = run_dir / "field" / var
        field_dir.mkdir(parents=True, exist_ok=True)
        np.ascontiguousarray(sf, dtype="<f4").tofile(field_dir / f"{p.stem}.bin")
        coord_path = run_dir / "coordinates.bin"
        coords_out = np.stack((lon2d, lat2d), axis=-1).astype("<f4")
        _atomic_write(coord_path, np.ascontiguousarray(coords_out).tobytes())
        grid_path = run_dir / "grid.json"
        finite_lons = lon2d[np.isfinite(lon2d)]
        finite_lats = lat2d[np.isfinite(lat2d)]
        grid_metadata = {
            "ny": int(sf.shape[0]),
            "nx": int(sf.shape[1]),
            "lon_min": float(finite_lons.min()),
            "lon_max": float(finite_lons.max()),
            "lat_min": float(finite_lats.min()),
            "lat_max": float(finite_lats.max()),
            "order": "row-major",
            "dtype": "float32le",
            "coordinates": "coordinates.bin",
            "coordinate_order": "lon_lat_interleaved",
        }
        _atomic_write(grid_path, json.dumps(grid_metadata, sort_keys=True).encode())
    if want_contours:
        proj = sel.get_projection(date, run)
        iv = interval or 0.1
        gj = render_contour_geojson(field, lo, la, c, proj, iv, iv * 5)
        gj["metadata"]["variable"] = var
        gj["metadata"]["fhr"] = fhr
        cdir = run_dir / "contours" / var
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / f"{p.stem}.json").write_text(json.dumps(gj, sort_keys=True))
    return (var, fhr, len(png))


def _atomic_write(path: Path, content: bytes) -> None:
    """Replace one companion file atomically, even with parallel frame jobs."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def colors_for(cmap_name, n):
    try:
        cmap = colormaps[cmap_name]
    except (KeyError, ValueError):
        cmap = colormaps["turbo"]
    return [
        f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
        for i in range(n)
        for r, g, b, _ in [cmap(i / max(n - 1, 1))]
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="dist_static")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--product", default="air")
    ap.add_argument("--config", default=None, help="Dataset YAML for the selected product")
    ap.add_argument(
        "--no-fields",
        action="store_true",
        help="Skip Float32 field grid export (needed for static point queries)",
    )
    ap.add_argument(
        "--no-contours",
        action="store_true",
        help="Skip precomputed contour GeoJSON export",
    )
    ap.add_argument(
        "--frontend-dist",
        default=None,
        help="Path to a VITE_STATIC_MODE=true frontend build to copy in",
    )
    ap.add_argument(
        "--build-frontend",
        action="store_true",
        help="Run npm ci && npm run build in frontend/ before copying",
    )
    ap.add_argument(
        "--no-frontend",
        action="store_true",
        help="Emit data only; skip copying the HTML shell",
    )
    ap.add_argument(
        "--refresh-frontend",
        action="store_true",
        help="Refresh the static HTML shell and assets in an existing bundle",
    )
    a = ap.parse_args()
    if not isinstance(a.product, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", a.product):
        ap.error("--product must start with a letter and contain only letters, numbers, _ or -")
    project_root = Path(__file__).resolve().parent.parent.parent
    config_path = Path(a.config) if a.config else project_root / "config" / "domains" / f"{a.product}.yaml"
    try:
        import yaml
        config_data = yaml.safe_load(config_path.read_text()) or {}
    except Exception as exc:
        print(f"Cannot read dataset config {config_path}: {exc}")
        sys.exit(1)
    config_product_id = config_data.get("product", {}).get("id") if isinstance(config_data, dict) else None
    if config_product_id != a.product:
        ap.error(
            f"--product {a.product!r} does not match product.id {config_product_id!r} "
            f"in {config_path}"
        )
    try:
        dc = DomainConfig(**config_data)
    except Exception as exc:
        ap.error(f"invalid dataset config {config_path}: {exc}")

    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    frontend_dist = None
    if not a.no_frontend:
        if a.build_frontend:
            fe = Path(__file__).resolve().parent.parent.parent / "frontend"
            env = {**os.environ, "VITE_STATIC_MODE": "true", "VITE_BASE_PATH": "./"}
            subprocess.run(["npm", "ci"], cwd=fe, check=True)
            subprocess.run(["npm", "run", "build"], cwd=fe, check=True, env=env)
        frontend_dist = (
            Path(a.frontend_dist)
            if a.frontend_dist
            else Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
        ).resolve()
        try:
            index = (frontend_dist / "index.html").read_text()
            build_info = json.loads((frontend_dist / "data" / "build-info.json").read_text())
            if not build_info.get("staticMode"):
                raise ValueError("frontend was not built with VITE_STATIC_MODE=true")
            if not index.strip() or "<html" not in index.lower():
                raise ValueError("frontend index.html is empty or invalid")
            asset_refs = re.findall(r"(?:src|href)\s*=\s*['\"]([^'\"]+)['\"]", index, flags=re.IGNORECASE)
            nonlocal_refs = [ref for ref in asset_refs if ref.startswith(("/", "//", "http:", "https:"))]
            if nonlocal_refs:
                raise ValueError(
                    "frontend asset URLs must be relative for nested static deployment: "
                    + ", ".join(nonlocal_refs)
                )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"FATAL ERROR: invalid static frontend at {frontend_dist}: {exc}", file=sys.stderr)
            sys.exit(1)
    store_value = config_data.get("ingest", {}).get("store_path", "data/manifests/gefs")
    store_path = Path(store_value)
    if not store_path.is_absolute():
        store_path = project_root / store_path
    sp = str(store_path.resolve())
    from backend.app.data.field_selector import FieldSelector
    from backend.app.data.kerchunk_store import ManifestStore

    store = ManifestStore(sp)
    sel = FieldSelector(store)
    dates = sorted(store.discover_dates())[-a.days :]
    print(f"Exporting {a.product}: {dates}")
    product_dir = out / "data" / a.product
    provenance_path = product_dir / "render-provenance.json"
    provenance = export_fingerprint(config_data, store_path, a.product, a.no_fields, a.no_contours)
    try:
        previous_provenance = json.loads(provenance_path.read_text()).get("fingerprint")
    except (OSError, json.JSONDecodeError, AttributeError):
        previous_provenance = None
    force_render = previous_provenance != provenance
    # catalog
    catalog_path = out / "data" / "catalog.json"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {"products": []}
    except (json.JSONDecodeError, OSError):
        catalog = {"products": []}
    products = {item["product"]: item for item in catalog.get("products", []) if "product" in item}
    products[a.product] = {"product": a.product, "description": config_data.get("product", {}).get("name", a.product)}
    catalog_path.write_text(json.dumps({"products": list(products.values())}, sort_keys=True))
    dates_path = product_dir / "dates.json"
    dates_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if dates_path.exists():
        try:
            existing = json.loads(dates_path.read_text()).get("dates", [])
        except (json.JSONDecodeError, AttributeError):
            existing = []
    merged = sorted(set(existing) | set(dates))
    dates_path.write_text(json.dumps({"product": a.product, "dates": merged}, sort_keys=True))
    # Product bounds are regenerated on each export so a changed source grid
    # cannot leave stale geographic extents in an updated bundle.
    bounds_path = product_dir / "bounds.json"
    if dates:
        from backend.app.projections.coordinates import CoordinateMapper
        from backend.app.projections.transform import CoordinateTransformer

        first_run = next(iter(store.discover_runs(dates[0])), "00")
        coords = sel.get_coordinates(dates[0], first_run)
        proj = sel.get_projection(dates[0], first_run)
        transformer = CoordinateTransformer.from_projection(proj)
        mapper = CoordinateMapper(coords, proj)
        lon_n, lat_n = mapper.get_grid_meshgrid()
        if coords.lons.ndim == 2:
            # FieldSelector's 2D latitude/longitude arrays are geographic
            # geolocation, including for Lambert and other projected grids.
            lons_geo = np.where(lon_n > 180.0, lon_n - 360.0, lon_n)
            lats_geo = lat_n
        else:
            lons_geo, lats_geo = transformer.transform_grid(lon_n, lat_n)
        lo0, lo1 = float(lons_geo.min()), float(lons_geo.max())
        la0, la1 = float(lats_geo.min()), float(lats_geo.max())
        ring = [[lo0, la0], [lo1, la0], [lo1, la1], [lo0, la1], [lo0, la0]]
        bounds_path.parent.mkdir(parents=True, exist_ok=True)
        bounds_path.write_text(
            json.dumps(
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {
                        "grid_type": proj.grid_type,
                        "shape": list(coords.shape),
                        "lon_min": lo0,
                        "lon_max": lo1,
                        "lat_min": la0,
                        "lat_max": la1,
                    },
                },
                sort_keys=True,
            )
        )
    tf = 0
    failed = 0
    for date in dates:
        runs = store.discover_runs(date)
        (product_dir / date).mkdir(parents=True, exist_ok=True)
        (product_dir / date / "runs.json").write_text(
            json.dumps({"product": a.product, "date": date, "runs": list(runs)}, sort_keys=True)
        )
        for run in runs:
            rd = product_dir / date / run
            rd.mkdir(parents=True, exist_ok=True)
            rv = sel.get_variables(date, run)
            vout = []
            for v in rv:
                vc = dc.get_variable(v["name"])
                if not vc or not vc.rendering.fillLevels:
                    continue
                vout.append(
                    {
                        "name": v["name"],
                        "shortName": vc.shortName,
                        "fullName": vc.fullName,
                        "units": vc.units,
                        "category": vc.category,
                        "rendering": {
                            "colormap": vc.rendering.colormap,
                            "contourInterval": vc.rendering.contourInterval,
                            "fillLevels": vc.rendering.fillLevels,
                            "colors": colors_for(
                                vc.rendering.colormap, len(vc.rendering.fillLevels)
                            ),
                        },
                    }
                )
            (rd / "variables.json").write_text(
                json.dumps({"product": a.product, "date": date, "run": run, "variables": vout})
            )
            levels_out = {}
            for v in vout:
                get_levels = getattr(sel, "get_levels", None)
                lv = get_levels(date, run, v["name"]) if get_levels else None
                if lv:
                    levels_out[v["name"]] = [
                        {
                            "surfaceType": x.get("surfaceType"),
                            "value": float(x.get("value", 0.0)),
                            "label": x.get("label", str(x.get("value", "level"))),
                        }
                        for x in lv
                    ]
                else:
                    levels_out[v["name"]] = [{"surfaceType": 1, "value": 0.0, "label": "surface"}]
            (rd / "levels.json").write_text(
                json.dumps(
                    {"product": a.product, "date": date, "run": run, "byVariable": levels_out},
                    sort_keys=True,
                )
            )
            it = datetime.strptime(f"{date}{run}", "%Y%m%d%H").replace(tzinfo=UTC)
            fe = sel.get_forecast_hours(date, run)
            fhrs = [e["fhr"] if isinstance(e, dict) else e for e in fe]
            to = [{"fhr": f, "valid_time": (it + timedelta(hours=f)).isoformat()} for f in fhrs]
            (rd / "times.json").write_text(
                json.dumps(
                    {
                        "product": a.product,
                        "date": date,
                        "run": run,
                        "init_time": it.isoformat(),
                        "forecast_hours": to,
                    }
                )
            )
            jobs = []
            for v in vout:
                for fhr in fhrs:
                    pp = rd / "fill" / v["name"] / f"f{fhr:03d}.png"
                    contour_path = rd / "contours" / v["name"] / f"f{fhr:03d}.json"
                    field_path = rd / "field" / v["name"] / f"f{fhr:03d}.bin"
                    needs_frame = (
                        force_render
                        or
                        not pp.exists()
                        or (not a.no_contours and not contour_path.exists())
                        or (not a.no_fields and not field_path.exists())
                    )
                    if needs_frame:
                        jobs.append(
                            (
                                sp,
                                date,
                                run,
                                v["name"],
                                fhr,
                                v["rendering"]["fillLevels"],
                                v["rendering"]["colormap"],
                                str(pp),
                                not a.no_fields,
                                not a.no_contours,
                                v["rendering"].get("contourInterval"),
                            )
                        )
            if jobs:
                print(f"  [{date}/{run}] {len(jobs)} frames...")
                with ProcessPoolExecutor(max_workers=a.workers) as ex:
                    for f in as_completed({ex.submit(render_one, j): j for j in jobs}):
                        try:
                            f.result()
                            tf += 1
                        except Exception as e:
                            failed += 1
                            print(f"    ERR: {e}")

    # --- Frontend shell copy ---
    if frontend_dist is not None:
        index_source = frontend_dist / "index.html"
        for item in sorted(frontend_dist.iterdir()):
            if item.name == "data":
                continue  # never clobber exporter data
            dest = out / item.name
            if item.name == "index.html":
                continue  # shell is switched last, after all referenced assets
            if dest.exists() and not a.refresh_frontend:
                continue  # append mode: don't overwrite existing shell
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        # Preserve old content-hashed assets for already-open browsers; a new
        # document is visible only after its asset tree has been copied.
        if a.refresh_frontend or not (out / "index.html").exists():
            shutil.copy2(index_source, out / "index.html")

    print(f"Done: {tf} frames to {out}")
    if failed:
        print(f"FATAL ERROR: {failed} frame(s) failed")
        sys.exit(2)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(json.dumps({"fingerprint": provenance}, sort_keys=True))
    try:
        dataset_ids = [
            item["product"] for item in json.loads(catalog_path.read_text()).get("products", [])
            if isinstance(item.get("product"), str)
        ]
    except (OSError, json.JSONDecodeError, AttributeError):
        dataset_ids = [a.product]
    (out / "export-info.json").write_text(json.dumps({
        "exportedAt": datetime.now(UTC).isoformat(),
        "datasets": dataset_ids,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
