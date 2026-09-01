"""Tests for the static site export script (backend/scripts/export_static.py).

Verifies that running the exporter produces a self-contained static site
directory with catalog JSON, per-run metadata JSON, and rendered fill PNGs,
using mocked data stores so no real GRIB/kerchunk data is required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

from backend.scripts import export_static


def _tiny_png() -> bytes:
    """Return a minimal valid 1x1 PNG (avoids heavy rasterio reproject)."""
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class _Coords:
    lons: np.ndarray
    lats: np.ndarray
    shape: tuple[int, ...] = (24, 36)


@dataclass
class _FakeProjection:
    grid_type: str = "regular_ll"
    crs_params: dict | None = None
    scanning_mode: int = 0

    def __post_init__(self):
        if self.crs_params is None:
            self.crs_params = {}

    def to_crs_string(self) -> str:
        return "EPSG:4326"


class _FakeSelector:
    """Minimal stand-in for FieldSelector."""

    def __init__(self, store):
        pass

    def select(self, date, run, var, fhr=0):
        """Return a smooth synthetic 2D field (lat, lon)."""
        rng = np.random.default_rng(42)
        base = rng.random((24, 36)).astype(np.float32)
        return base * 2.0

    def get_variables(self, date, run):
        return [{"name": "totAOD550"}]

    def get_forecast_hours(self, date, run):
        return [{"fhr": 0}, {"fhr": 3}]

    def get_coordinates(self, date, run):
        return _Coords(
            lons=np.linspace(-180.0, 179.0, 36, dtype=np.float64),
            lats=np.linspace(-80.0, 80.0, 24, dtype=np.float64),
        )

    def get_projection(self, date, run):
        return _FakeProjection()


class _FakeStore:
    """Minimal stand-in for ManifestStore."""

    def __init__(self, store_path):
        pass

    def discover_dates(self):
        return ["20260821"]

    def discover_runs(self, date):
        return ["00"]


@pytest.fixture
def domain_config():
    """Load the real 'air' domain config so rendering metadata is realistic."""
    from backend.app.config.loader import get_domain_config_safe

    dc = get_domain_config_safe("air")
    assert dc is not None, "air domain config must be loadable for export tests"
    return dc


def _run_export(tmp_path: Path, monkeypatch, domain_config, extra_args=()) -> Path:
    """Invoke export_static.main() with mocked stores and inline rendering."""
    out = tmp_path / "dist_static"

    class _InlineExecutor:
        """Run submitted jobs synchronously in-process."""

        def __init__(self, max_workers=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def submit(self, fn, *args):
            result = MagicMock()
            fn(*args)
            result.result.return_value = None
            return result

        def as_completed(self, futures):
            return list(futures)

    # ManifestStore/FieldSelector are imported inside functions, so patch
    # them at their source modules.
    monkeypatch.setattr("backend.app.data.kerchunk_store.ManifestStore", _FakeStore)
    monkeypatch.setattr("backend.app.data.field_selector.FieldSelector", _FakeSelector)
    monkeypatch.setattr(export_static, "ProcessPoolExecutor", _InlineExecutor)
    # export_static calls the module-level as_completed(); the real one blocks
    # forever on our mock futures, so replace it with an identity iterator.
    monkeypatch.setattr(export_static, "as_completed", lambda fs: list(fs))
    # Avoid the expensive 2048x2048 rasterio reproject in render_fill_png;
    # return a minimal valid PNG so we test the export pipeline, not rendering.
    monkeypatch.setattr(
        export_static,
        "render_fill_png",
        lambda *a, **k: _tiny_png(),
    )
    monkeypatch.setattr(export_static, "get_domain_config_safe", lambda product: domain_config)

    monkeypatch.setattr(
        "sys.argv",
        ["export_static.py", "--output", str(out), "--product", "air"] + list(extra_args),
    )
    export_static.main()
    return out


def test_export_creates_static_site(tmp_path: Path, monkeypatch, domain_config):
    """Export produces catalog, dates, per-run metadata, and PNG frames."""
    out = _run_export(tmp_path, monkeypatch, domain_config)

    assert out.is_dir()

    catalog = json.loads((out / "data" / "catalog.json").read_text())
    assert catalog["products"][0]["product"] == "air"

    dates = json.loads((out / "data" / "air" / "dates.json").read_text())
    assert dates["dates"] == ["20260821"]

    run_dir = out / "data" / "air" / "20260821" / "00"
    variables = json.loads((run_dir / "variables.json").read_text())
    assert variables["variables"], "at least one renderable variable expected"
    var = variables["variables"][0]
    assert var["name"] == "totAOD550"
    assert var["rendering"]["colors"], "colors list must match fill levels"
    assert len(var["rendering"]["colors"]) == len(var["rendering"]["fillLevels"])

    times = json.loads((run_dir / "times.json").read_text())
    assert [t["fhr"] for t in times["forecast_hours"]] == [0, 3]
    assert times["init_time"].endswith("+00:00")


def test_export_renders_png_frames(tmp_path: Path, monkeypatch, domain_config):
    """Each variable/forecast-hour combination gets a rendered PNG frame."""
    out = _run_export(tmp_path, monkeypatch, domain_config)
    run_dir = out / "data" / "air" / "20260821" / "00"

    for fhr in (0, 3):
        png = run_dir / "fill" / "totAOD550" / f"f{fhr:03d}.png"
        assert png.is_file(), f"missing frame {png}"
        # PNG magic bytes
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_export_static_site_has_no_html(tmp_path: Path, monkeypatch, domain_config):
    """Documents current behavior: exporter writes data only, no HTML shell.

    The static site currently relies on the frontend being deployed
    separately; if an index.html is ever emitted by the exporter, update
    this test to assert its presence instead.
    """
    out = _run_export(tmp_path, monkeypatch, domain_config)
    assert not (out / "index.html").exists()


def test_export_writes_index_jsons(tmp_path, monkeypatch, domain_config):
    out = _run_export(tmp_path, monkeypatch, domain_config)
    prod = out / "data" / "air"

    runs = json.loads((prod / "20260821" / "runs.json").read_text())
    assert runs == {"product": "air", "date": "20260821", "runs": ["00"]}

    levels = json.loads((prod / "20260821" / "00" / "levels.json").read_text())
    assert levels["product"] == "air"
    # air domain variables are surface (level-less) -> single surface entry per variable
    assert "totAOD550" in levels["byVariable"]
    assert levels["byVariable"]["totAOD550"][0]["label"] == "surface"

    bounds = json.loads((prod / "bounds.json").read_text())
    assert bounds["type"] == "Feature"
    assert bounds["geometry"]["type"] == "Polygon"
    ring = bounds["geometry"]["coordinates"][0]
    assert len(ring) == 5 and ring[0] == ring[-1]


def test_dates_json_is_union_on_rerun(tmp_path, monkeypatch, domain_config):
    out = tmp_path / "dist_static"
    out.mkdir(parents=True)
    prod = out / "data" / "air"
    prod.mkdir(parents=True)
    (prod / "dates.json").write_text(json.dumps({"product": "air", "dates": ["20200101"]}))
    _run_export(tmp_path, monkeypatch, domain_config)
    dates = json.loads((prod / "dates.json").read_text())["dates"]
    assert dates == ["20200101", "20260821"]


def test_export_writes_field_bins(tmp_path, monkeypatch, domain_config):
    """Float32 field grids and grid.json are emitted for point queries."""
    out = _run_export(tmp_path, monkeypatch, domain_config)
    rd = out / "data" / "air" / "20260821" / "00"
    grid = json.loads((rd / "grid.json").read_text())
    assert grid["ny"] == 24 and grid["nx"] == 36
    assert grid["dtype"] == "float32le" and grid["order"] == "row-major"
    assert grid["lon_min"] == -180.0 and grid["lon_max"] == 179.0
    assert grid["lat_min"] == -80.0 and grid["lat_max"] == 80.0

    raw = (rd / "field" / "totAOD550" / "f000.bin").read_bytes()
    arr = np.frombuffer(raw, dtype="<f4")
    assert arr.size == grid["ny"] * grid["nx"]
    # Deterministic fake field: values in [0, 2)
    assert arr.min() >= 0.0 and arr.max() < 2.0


def test_export_no_fields_skips_bins(tmp_path, monkeypatch, domain_config):
    """--no-fields skips field/grid emission but keeps fills."""
    out = _run_export(tmp_path, monkeypatch, domain_config, extra_args=("--no-fields",))
    rd = out / "data" / "air" / "20260821" / "00"
    assert not (rd / "grid.json").exists()
    assert not (rd / "field").exists()
    assert (rd / "fill" / "totAOD550" / "f000.png").is_file()


def test_export_writes_contour_geojson(tmp_path, monkeypatch, domain_config):
    """Precomputed contour GeoJSON is emitted per frame, matching /api/contours."""
    out = _run_export(tmp_path, monkeypatch, domain_config)
    f = out / "data" / "air" / "20260821" / "00" / "contours" / "totAOD550" / "f000.json"
    assert f.is_file()
    gj = json.loads(f.read_text())
    assert gj["type"] == "FeatureCollection"
    assert "metadata" in gj
    assert gj["metadata"]["variable"] == "totAOD550"
    assert gj["metadata"]["fhr"] == 0
    assert gj["metadata"]["contourInterval"] > 0
    assert gj["features"], "synthetic field must produce contour features"
    assert all(
        feat["type"] == "Feature" and feat["geometry"]["type"] == "MultiLineString"
        for feat in gj["features"]
    )


def test_export_no_contours_skips_geojson(tmp_path, monkeypatch, domain_config):
    """--no-contours skips contour emission but keeps fills."""
    out = _run_export(tmp_path, monkeypatch, domain_config, extra_args=("--no-contours",))
    rd = out / "data" / "air" / "20260821" / "00"
    assert not (rd / "contours").exists()
    assert (rd / "fill" / "totAOD550" / "f000.png").is_file()
