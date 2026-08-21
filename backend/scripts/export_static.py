#!/usr/bin/env python
"""Export ForecastView as a fully static site for RZDM deployment."""

from __future__ import annotations

import argparse
import json
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


def render_one(args):
    sp, date, run, var, fhr, fl, cm, op = args
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
    (out / "data" / a.product / "dates.json").parent.mkdir(parents=True, exist_ok=True)
    (out / "data" / a.product / "dates.json").write_text(
        json.dumps({"product": a.product, "dates": dates})
    )
    tf = 0
    for date in dates:
        for run in store.discover_runs(date):
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
                            print(f"    ERR: {e}")
    print(f"Done: {tf} frames to {out}")


if __name__ == "__main__":
    main()
