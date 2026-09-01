#!/usr/bin/env python
"""Export ForecastView as a fully static site for RZDM deployment."""

from __future__ import annotations

import argparse
import json
import os
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
from backend.app.config.loader import get_domain_config_safe
from backend.app.contours.geojson import shift_grid_to_minus180

WEB_MERCATOR_MAX_LAT = 85.06
CRS_4326 = CRS.from_epsg(4326)
CRS_3857 = CRS.from_epsg(3857)
MX = 20037508.3427892


def render_fill_png(field, lons_1d, lats_1d, fill_levels, cmap_name):
    sf, sl, _ = shift_grid_to_minus180(field, lons_1d)
    if not np.array_equal(sl, lons_1d):
        field, lons_1d = sf, sl
    vm = (lats_1d >= -WEB_MERCATOR_MAX_LAT) & (lats_1d <= WEB_MERCATOR_MAX_LAT)
    vr = np.where(vm)[0]
    field = field[vr[0] : vr[-1] + 1, :]
    lc = lats_1d[vr[0] : vr[-1] + 1]
    sh, sw = field.shape
    st = from_bounds(
        float(lons_1d[0]),
        float(lc[-1]),
        float(lons_1d[-1]) + (lons_1d[1] - lons_1d[0]),
        float(lc[0]),
        sw,
        sh,
    )
    dt = from_bounds(-MX, -MX, MX, MX, 2048, 2048)
    dst = np.zeros((2048, 2048), dtype=np.float32)
    reproject(
        source=field.astype(np.float32),
        destination=dst,
        src_transform=st,
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
    lo = c.lons[0, :] if c.lons.ndim == 2 else c.lons
    la = c.lats[:, 0] if c.lats.ndim == 2 else c.lats
    png = render_fill_png(field, lo, la, fl, cm)
    p = Path(op)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(png)
    # Fill path is <run>/fill/<var>/f<NNN>.png -> run dir is 3 levels up.
    run_dir = p.parent.parent.parent
    if want_fields:
        sf, sl, _ = shift_grid_to_minus180(field, lo)
        vm = (la >= -WEB_MERCATOR_MAX_LAT) & (la <= WEB_MERCATOR_MAX_LAT)
        vr = np.where(vm)[0]
        sf = sf[vr[0] : vr[-1] + 1, :]
        lc = la[vr[0] : vr[-1] + 1]
        field_dir = run_dir / "field" / var
        field_dir.mkdir(parents=True, exist_ok=True)
        np.ascontiguousarray(sf, dtype="<f4").tofile(field_dir / f"{p.stem}.bin")
        grid_path = run_dir / "grid.json"
        if not grid_path.exists():
            grid_path.write_text(
                json.dumps(
                    {
                        "ny": int(sf.shape[0]),
                        "nx": int(sf.shape[1]),
                        "lon_min": float(sl[0]),
                        "lon_max": float(sl[-1]),
                        "lat_min": float(lc[0]),
                        "lat_max": float(lc[-1]),
                        "order": "row-major",
                        "dtype": "float32le",
                    },
                    sort_keys=True,
                )
            )
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
    a = ap.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    sp = str(Path(__file__).resolve().parent.parent.parent / "data" / "manifests" / "gefs")
    from backend.app.data.field_selector import FieldSelector
    from backend.app.data.kerchunk_store import ManifestStore

    store = ManifestStore(sp)
    sel = FieldSelector(store)
    dc = get_domain_config_safe(a.product)
    if not dc:
        print("No config")
        sys.exit(1)
    dates = sorted(store.discover_dates())[-a.days :]
    print(f"Exporting {a.product}: {dates}")
    # catalog
    (out / "data" / "catalog.json").parent.mkdir(parents=True, exist_ok=True)
    (out / "data" / "catalog.json").write_text(
        json.dumps({"products": [{"product": "air", "description": "GEFS-Aerosol"}]})
    )
    dates_path = out / "data" / a.product / "dates.json"
    dates_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if dates_path.exists():
        try:
            existing = json.loads(dates_path.read_text()).get("dates", [])
        except (json.JSONDecodeError, AttributeError):
            existing = []
    merged = sorted(set(existing) | set(dates))
    dates_path.write_text(json.dumps({"product": a.product, "dates": merged}, sort_keys=True))
    # bounds.json (per product, written once)
    bounds_path = out / "data" / a.product / "bounds.json"
    if not bounds_path.exists() and dates:
        from backend.app.projections.coordinates import CoordinateMapper
        from backend.app.projections.transform import CoordinateTransformer

        first_run = next(iter(store.discover_runs(dates[0])), "00")
        coords = sel.get_coordinates(dates[0], first_run)
        proj = sel.get_projection(dates[0], first_run)
        transformer = CoordinateTransformer.from_projection(proj)
        mapper = CoordinateMapper(coords, proj)
        lon_n, lat_n = mapper.get_grid_meshgrid()
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
                    "properties": {"grid_type": proj.grid_type, "shape": list(coords.shape)},
                },
                sort_keys=True,
            )
        )
    tf = 0
    failed = 0
    for date in dates:
        runs = store.discover_runs(date)
        (out / "data" / a.product / date).mkdir(parents=True, exist_ok=True)
        (out / "data" / a.product / date / "runs.json").write_text(
            json.dumps({"product": a.product, "date": date, "runs": list(runs)}, sort_keys=True)
        )
        for run in runs:
            rd = out / "data" / a.product / date / run
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
                vc = dc.get_variable(v["name"])
                lv = getattr(vc, "levels", None) if vc else None
                if lv:
                    levels_out[v["name"]] = [
                        {
                            "surfaceType": getattr(x, "surfaceType", None),
                            "value": float(getattr(x, "value", x)),
                            "label": getattr(x, "label", str(x)),
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
                    if not pp.exists():
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
    if not a.no_frontend:
        if a.build_frontend:
            fe = Path(__file__).resolve().parent.parent.parent / "frontend"
            env = {**os.environ, "VITE_STATIC_MODE": "true", "VITE_BASE_PATH": "./"}
            subprocess.run(["npm", "ci"], cwd=fe, check=True)
            subprocess.run(["npm", "run", "build"], cwd=fe, check=True, env=env)
        dist = (
            Path(a.frontend_dist)
            if a.frontend_dist
            else Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
        )
        if not (dist / "index.html").exists():
            print(
                f"FATAL ERROR: frontend dist not found at {dist} "
                "(run with --build-frontend or build the frontend first)"
            )
            sys.exit(1)
        bi = dist / "data" / "build-info.json"
        if not bi.exists() or not json.loads(bi.read_text()).get("staticMode"):
            print("FATAL ERROR: frontend dist was not built with VITE_STATIC_MODE=true")
            sys.exit(1)
        for item in sorted(dist.iterdir()):
            if item.name == "data":
                continue  # never clobber exporter data
            dest = out / item.name
            if dest.exists():
                continue  # append mode: don't overwrite existing shell
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    print(f"Done: {tf} frames to {out}")
    if failed:
        print(f"FATAL ERROR: {failed} frame(s) failed")
        sys.exit(2)


if __name__ == "__main__":
    main()
