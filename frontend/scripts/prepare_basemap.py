#!/usr/bin/env python3
"""Download and trim Natural Earth GeoJSON for the offline basemap.

The static site (RZDM / air-gapped) cannot fetch remote vector tiles, so a
small set of Natural Earth layers is bundled under ``frontend/public/basemap``
and drawn as plain GeoJSON sources. Raw Natural Earth files carry hundreds of
unused attributes; this script keeps only the whitelisted properties and
rounds coordinates so the committed bundle stays a few hundred KB.

Run from the repository root (needs network access to raw.githubusercontent.com):

    python frontend/scripts/prepare_basemap.py

Output (committed to the repo, regenerated only when the basemap changes):

    frontend/public/basemap/countries.geojson
    frontend/public/basemap/states.geojson
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"

# Destination name -> (source file, property whitelist, coordinate precision).
# Cities are additionally filtered by rank/population to keep the file small.
# ``countries`` doubles as the land fill (its polygons are the coastlines), so a
# separate land layer would be redundant weight. ``states`` is scoped to the US
# (adm0_a3 == USA) since that is the only sub-country detail we render.
# Cities are intentionally excluded: offline text labels would need a glyph
# endpoint, and unlabeled dots add clutter without information.
LAYERS: dict[str, dict] = {
    "countries": {
        "src": "ne_50m_admin_0_countries.geojson",
        "keep": ["NAME", "ISO_A2", "CONTINENT", "POP_EST", "LABELRANK", "MIN_ZOOM"],
        "precision": 3,
    },
    "states": {
        "src": "ne_50m_admin_1_states_provinces.geojson",
        "keep": ["name", "adm0_a3", "iso_3166_2", "min_zoom", "scalerank"],
        "precision": 3,
        "filter": lambda props: props.get("adm0_a3") == "USA",
    },
}


def _round_coords(obj, precision: int):
    """Round every number inside a GeoJSON geometry to ``precision`` decimals."""
    if isinstance(obj, list):
        return [_round_coords(v, precision) for v in obj]
    if isinstance(obj, int | float):
        return round(float(obj), precision)
    return obj


def trim_layer(spec: dict, raw: dict) -> dict:
    keep = set(spec["keep"])
    precision = spec["precision"]
    filt = spec.get("filter")
    features = []
    for feat in raw.get("features", []):
        props = feat.get("properties", {})
        if filt and not filt(props):
            continue
        trimmed = {k: props.get(k) for k in keep}
        geometry = _round_coords(feat.get("geometry"), precision)
        features.append({"type": "Feature", "properties": trimmed, "geometry": geometry})
    return {"type": "FeatureCollection", "name": raw.get("name", ""), "features": features}


def download(src: str) -> dict:
    url = f"{BASE_URL}/{src}"
    print(f"fetch {url}")
    with urllib.request.urlopen(url, timeout=120) as resp:
        return json.load(resp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "public" / "basemap",
        help="Output directory (default: frontend/public/basemap)",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for name, spec in LAYERS.items():
        raw = download(spec["src"])
        trimmed = trim_layer(spec, raw)
        dest = args.out / f"{name}.geojson"
        dest.write_text(json.dumps(trimmed, separators=(",", ":")))
        n = len(trimmed["features"])
        print(f"wrote {dest} ({dest.stat().st_size // 1024} KB, {n} features)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
