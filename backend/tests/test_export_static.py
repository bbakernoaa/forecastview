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
            # North-first (descending) like real GEFS: row 0 is lat_max.
            lats=np.linspace(80.0, -80.0, 24, dtype=np.float64),
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


def _run_export(
    tmp_path,
    monkeypatch,
    domain_config,
    extra_args=(),
    frontend_dist=None,
    selector_cls=_FakeSelector,
    product="air",
) -> Path:
    """Invoke export_static.main() with mocked stores and inline rendering.

    Defaults to --no-frontend so data-only tests don't depend on the repo's
    real frontend/dist being present or static-marked.
    """
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
    monkeypatch.setattr("backend.app.data.field_selector.FieldSelector", selector_cls)
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
    argv = ["export_static.py", "--output", str(out), "--product", product] + list(extra_args)
    if frontend_dist is not None:
        argv += ["--frontend-dist", str(frontend_dist)]
    elif "--no-frontend" not in extra_args:
        argv += ["--no-frontend"]
    monkeypatch.setattr("sys.argv", argv)
    export_static.main()
    return out


def _write_domain_yaml(path: Path, product_id: str, name: str, fill_levels: list[int]) -> Path:
    import yaml

    path.write_text(yaml.safe_dump({
        "product": {"id": product_id, "name": name},
        "variables": {
            "totAOD550": {
                "shortName": "Custom AOD",
                "fullName": "Custom aerosol optical depth",
                "units": "1",
                "category": "Aerosol",
                "rendering": {
                    "colormap": "viridis",
                    "contourInterval": 1,
                    "fillLevels": fill_levels,
                },
            },
        },
    }))
    return path


def test_export_uses_render_metadata_from_explicit_config(tmp_path, monkeypatch, domain_config):
    config = _write_domain_yaml(tmp_path / "custom.yaml", "air", "Custom air", [10, 20, 40])

    out = _run_export(
        tmp_path,
        monkeypatch,
        domain_config,
        extra_args=("--config", str(config)),
    )

    run_dir = out / "data" / "air" / "20260821" / "00"
    variable = json.loads((run_dir / "variables.json").read_text())["variables"][0]
    assert variable["shortName"] == "Custom AOD"
    assert variable["rendering"]["fillLevels"] == [10, 20, 40]
    assert json.loads((out / "data" / "catalog.json").read_text())["products"][0]["description"] == "Custom air"


def test_export_rejects_product_config_mismatch_before_creating_output(tmp_path, monkeypatch, domain_config):
    config = _write_domain_yaml(tmp_path / "other.yaml", "other", "Other product", [10, 20])

    with pytest.raises(SystemExit):
        _run_export(
            tmp_path,
            monkeypatch,
            domain_config,
            extra_args=("--config", str(config)),
            product="air",
        )

    assert not (tmp_path / "dist_static").exists()


def test_export_rejects_path_like_product_id_before_writing_outside_bundle(tmp_path, monkeypatch, domain_config):
    config = _write_domain_yaml(tmp_path / "unsafe.yaml", "../../escaped", "Unsafe", [10, 20])

    with pytest.raises(SystemExit):
        _run_export(
            tmp_path,
            monkeypatch,
            domain_config,
            extra_args=("--config", str(config)),
            product="../../escaped",
        )

    assert not (tmp_path / "escaped").exists()


def test_export_uses_actual_single_non_surface_level(tmp_path, monkeypatch, domain_config):
    class TwoMeterSelector(_FakeSelector):
        def get_levels(self, date, run, variable):
            return [{"surfaceType": 103, "value": 2.0, "label": "Height Above Ground=2"}]

    out = _run_export(
        tmp_path,
        monkeypatch,
        domain_config,
        selector_cls=TwoMeterSelector,
    )

    levels = json.loads(
        (out / "data" / "air" / "20260821" / "00" / "levels.json").read_text()
    )
    assert levels["byVariable"]["totAOD550"] == [
        {"surfaceType": 103, "value": 2.0, "label": "Height Above Ground=2"}
    ]


def _projected_geographic_selector(lon_min: float, lon_max: float):
    class LambertProjection(_FakeProjection):
        grid_type = "lambert"

        def to_crs_string(self) -> str:
            return (
                "+proj=lcc +lat_1=25 +lat_2=25 +lat_0=25 +lon_0=-95 "
                "+datum=WGS84 +units=m +no_defs"
            )

    class ProjectedSelector(_FakeSelector):
        def get_coordinates(self, date, run):
            lon_axis = np.linspace(lon_min, lon_max, 36)
            lat_axis = np.linspace(37.0, 35.0, 24)
            lons, lats = np.meshgrid(lon_axis, lat_axis)
            return _Coords(lons=lons, lats=lats)

        def get_projection(self, date, run):
            return LambertProjection()

    return ProjectedSelector


def test_export_bounds_use_geographic_2d_coordinates_for_projected_grid(
    tmp_path, monkeypatch, domain_config
):
    out = _run_export(
        tmp_path,
        monkeypatch,
        domain_config,
        selector_cls=_projected_geographic_selector(-100.0, -98.0),
    )

    bounds = json.loads((out / "data" / "air" / "bounds.json").read_text())
    assert bounds["properties"]["lon_min"] == pytest.approx(-100.0)
    assert bounds["properties"]["lon_max"] == pytest.approx(-98.0)
    assert bounds["properties"]["lat_min"] == pytest.approx(35.0)
    assert bounds["properties"]["lat_max"] == pytest.approx(37.0)


def test_export_refreshes_bounds_after_product_grid_changes(tmp_path, monkeypatch, domain_config):
    _run_export(
        tmp_path,
        monkeypatch,
        domain_config,
        selector_cls=_projected_geographic_selector(-100.0, -98.0),
    )
    out = _run_export(
        tmp_path,
        monkeypatch,
        domain_config,
        selector_cls=_projected_geographic_selector(-99.0, -97.0),
    )

    bounds = json.loads((out / "data" / "air" / "bounds.json").read_text())
    assert bounds["properties"]["lon_min"] == pytest.approx(-99.0)
    assert bounds["properties"]["lon_max"] == pytest.approx(-97.0)


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
    # BoundsLayer.tsx expects these properties in the static file
    for key in ("grid_type", "shape", "lon_min", "lon_max", "lat_min", "lat_max"):
        assert key in bounds["properties"], f"bounds.properties missing {key}"


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


def test_render_fill_accepts_curvilinear_geolocation_arrays():
    """Projected grid coordinates can be warped into the static map image."""
    from rasterio.crs import CRS
    from pyproj import Transformer

    x, y = np.meshgrid(np.linspace(-3_000_000, 3_000_000, 40), np.linspace(3_000_000, -3_000_000, 40))
    transformer = Transformer.from_crs(
        "+proj=lcc +lat_1=25 +lat_2=25 +lat_0=25 +lon_0=-95 +R=6371200 +units=m +no_defs",
        "EPSG:4326",
        always_xy=True,
    )
    lon, lat = transformer.transform(x, y)
    field = np.tile(np.linspace(0, 4, 40, dtype=np.float32), (40, 1))
    png = export_static.render_fill_png(field, lon, lat, [0, 1, 2, 3, 4], "viridis")
    image = np.asarray(Image.open(BytesIO(png)))
    assert image.shape == (2048, 2048, 4)
    assert np.any(image[:, :, 3] > 0)


def test_render_contours_follow_curvilinear_coordinates():
    """Contour vertices use both dimensions of 2D geolocation arrays."""
    from backend.app.data.field_selector import GridCoordinates

    coords = GridCoordinates(
        lons=np.array([[0.0, 2.0], [1.0, 3.0]]),
        lats=np.array([[0.0, 1.0], [2.0, 3.0]]),
        shape=(2, 2),
    )
    field = np.array([[0.0, 1.0], [0.0, 1.0]])

    geojson = export_static.render_contour_geojson(
        field, coords.lons, coords.lats, coords, _FakeProjection(), 0.5, 2.5
    )

    contour = next(feature for feature in geojson["features"] if feature["properties"]["value"] == 0.5)
    np.testing.assert_allclose(
        contour["geometry"]["coordinates"][0],
        [[2.0, 2.5], [1.0, 0.5]],
    )


def test_render_projected_grid_contours_do_not_reproject_geographic_arrays():
    """2D latitude/longitude arrays stay geographic for projected GRIB grids."""
    from backend.app.data.field_selector import GridCoordinates

    class LambertProjection(_FakeProjection):
        grid_type = "lambert"

        def to_crs_string(self) -> str:
            return (
                "+proj=lcc +lat_1=25 +lat_2=25 +lat_0=25 +lon_0=-95 "
                "+datum=WGS84 +units=m +no_defs"
            )

    coords = GridCoordinates(
        lons=np.array([[-100.0, -98.0], [-99.0, -97.0]]),
        lats=np.array([[35.0, 36.0], [37.0, 38.0]]),
        shape=(2, 2),
    )
    field = np.array([[0.0, 1.0], [0.0, 1.0]])

    geojson = export_static.render_contour_geojson(
        field, coords.lons, coords.lats, coords, LambertProjection(), 0.5, 2.5
    )

    contour = next(feature for feature in geojson["features"] if feature["properties"]["value"] == 0.5)
    np.testing.assert_allclose(
        contour["geometry"]["coordinates"][0],
        [[-98.0, 37.5], [-99.0, 35.5]],
    )


def test_render_projected_grid_contours_unwrap_antimeridian_longitudes():
    """Projected-grid geographic arrays interpolate across the short dateline arc."""
    from backend.app.data.field_selector import GridCoordinates

    class LambertProjection(_FakeProjection):
        grid_type = "lambert"

        def to_crs_string(self) -> str:
            return (
                "+proj=lcc +lat_1=25 +lat_2=25 +lat_0=25 +lon_0=-95 "
                "+datum=WGS84 +units=m +no_defs"
            )

    coords = GridCoordinates(
        lons=np.array([[179.0, -179.0], [179.0, -179.0]]),
        lats=np.array([[0.0, 0.0], [2.0, 2.0]]),
        shape=(2, 2),
    )
    field = np.array([[0.0, 1.0], [0.0, 1.0]])

    geojson = export_static.render_contour_geojson(
        field, coords.lons, coords.lats, coords, LambertProjection(), 0.5, 2.5
    )

    contour = next(feature for feature in geojson["features"] if feature["properties"]["value"] == 0.5)
    np.testing.assert_allclose(
        contour["geometry"]["coordinates"][0],
        [[-180.0, 2.0], [-180.0, 0.0]],
    )


def test_render_one_replaces_point_grid_metadata_when_coordinates_change(tmp_path, monkeypatch):
    """Re-exporting a run replaces stale coordinates.bin and grid.json."""
    from backend.app.data.field_selector import GridCoordinates

    coordinates = [
        GridCoordinates(
            lons=np.array([[10.0, 11.0], [10.0, 11.0]]),
            lats=np.array([[40.0, 40.0], [39.0, 39.0]]),
            shape=(2, 2),
        ),
        GridCoordinates(
            lons=np.array([[20.0, 21.0], [20.0, 21.0]]),
            lats=np.array([[50.0, 50.0], [49.0, 49.0]]),
            shape=(2, 2),
        ),
    ]

    class Selector:
        def __init__(self, store):
            pass

        def select(self, *args, **kwargs):
            return np.ones((2, 2), dtype=np.float32)

        def get_coordinates(self, *args):
            return coordinates.pop(0)

    monkeypatch.setattr("backend.app.data.kerchunk_store.ManifestStore", lambda path: object())
    monkeypatch.setattr("backend.app.data.field_selector.FieldSelector", Selector)
    monkeypatch.setattr(export_static, "render_fill_png", lambda *args: _tiny_png())
    run_dir = tmp_path / "20260821" / "00"
    output_path = run_dir / "fill" / "TMP" / "f000.png"
    args = (
        "store", "20260821", "00", "TMP", 0, [0, 1], "viridis",
        str(output_path), True, False, None,
    )

    export_static.render_one(args)
    coordinate_path = run_dir / "coordinates.bin"
    grid_path = run_dir / "grid.json"
    first_coordinates = np.fromfile(coordinate_path, dtype="<f4").copy()

    export_static.render_one(args)

    second_coordinates = np.fromfile(coordinate_path, dtype="<f4")
    second_grid = json.loads(grid_path.read_text())
    assert not np.array_equal(first_coordinates, second_coordinates)
    assert second_grid["lon_min"] == 20.0
    assert second_grid["lat_max"] == 50.0


def test_export_no_fields_skips_bins(tmp_path, monkeypatch, domain_config):
    """--no-fields skips field/grid emission but keeps fills."""
    out = _run_export(tmp_path, monkeypatch, domain_config, extra_args=("--no-fields",))
    rd = out / "data" / "air" / "20260821" / "00"
    assert not (rd / "grid.json").exists()
    assert not (rd / "field").exists()
    assert (rd / "fill" / "totAOD550" / "f000.png").is_file()


def test_export_fingerprint_changes_with_render_settings(tmp_path):
    base = {"product": {"id": "sample"}, "variables": {"TMP": {"rendering": {"fillLevels": [0, 1]}}}}
    first = export_static.export_fingerprint(base, tmp_path, "sample", False, False)
    changed = {**base, "variables": {"TMP": {"rendering": {"fillLevels": [0, 2]}}}}
    second = export_static.export_fingerprint(changed, tmp_path, "sample", False, False)
    assert first != second


def test_export_persists_render_provenance(tmp_path, monkeypatch, domain_config):
    out = _run_export(tmp_path, monkeypatch, domain_config)
    provenance = out / "data" / "air" / "render-provenance.json"
    assert json.loads(provenance.read_text())["fingerprint"]


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


def test_export_copies_frontend_shell(tmp_path, monkeypatch, domain_config):
    """A valid static frontend dist is copied in without clobbering data/."""
    dist = tmp_path / "fakedist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>static</html>")
    (dist / "assets" / "app.js").write_text("// bundle")
    (dist / "data").mkdir()
    (dist / "data" / "build-info.json").write_text(json.dumps({"staticMode": True}))
    out = _run_export(tmp_path, monkeypatch, domain_config, frontend_dist=dist)
    assert (out / "index.html").read_text() == "<html>static</html>"
    assert (out / "assets" / "app.js").is_file()
    # exporter data must survive; the dist's data/ must NOT be copied in
    assert (out / "data" / "catalog.json").is_file()
    assert not (out / "data" / "build-info.json").exists()


def test_export_fails_without_static_marker(tmp_path, monkeypatch, domain_config):
    """A frontend dist lacking the static-mode marker aborts the export."""
    dist = tmp_path / "bad"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>")
    with pytest.raises(SystemExit):
        _run_export(tmp_path, monkeypatch, domain_config, frontend_dist=dist)


def test_export_no_frontend_skips_shell(tmp_path, monkeypatch, domain_config):
    """--no-frontend produces a data-only export with no HTML shell."""
    out = _run_export(tmp_path, monkeypatch, domain_config, extra_args=("--no-frontend",))
    assert not (out / "index.html").exists()
    assert (out / "data" / "catalog.json").is_file()


def test_refresh_frontend_replaces_index_last_and_keeps_old_assets(tmp_path, monkeypatch, domain_config):
    dist = tmp_path / "new-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<html><script src="./assets/new.js"></script></html>')
    (dist / "assets" / "new.js").write_text("new bundle")
    (dist / "data").mkdir()
    (dist / "data" / "build-info.json").write_text(json.dumps({"staticMode": True}))
    out = tmp_path / "dist_static"
    (out / "assets").mkdir(parents=True)
    (out / "index.html").write_text('<html><script src="./assets/old.js"></script></html>')
    (out / "assets" / "old.js").write_text("cached old bundle")
    (out / "data" / "air").mkdir(parents=True)
    (out / "data" / "air" / "preserved.bin").write_bytes(b"forecast")

    _run_export(tmp_path, monkeypatch, domain_config,
                extra_args=("--refresh-frontend",), frontend_dist=dist)

    assert "new.js" in (out / "index.html").read_text()
    assert (out / "assets" / "new.js").read_text() == "new bundle"
    assert (out / "assets" / "old.js").read_text() == "cached old bundle"
    assert (out / "data" / "air" / "preserved.bin").read_bytes() == b"forecast"
    assert json.loads((out / "export-info.json").read_text())["datasets"] == ["air"]


def test_invalid_frontend_is_rejected_before_existing_html_changes(tmp_path, monkeypatch, domain_config):
    dist = tmp_path / "invalid-dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>not static</html>")
    (dist / "data").mkdir()
    (dist / "data" / "build-info.json").write_text(json.dumps({"staticMode": False}))
    out = tmp_path / "dist_static"
    out.mkdir()
    (out / "index.html").write_text("old html")

    with pytest.raises(SystemExit):
        _run_export(tmp_path, monkeypatch, domain_config,
                    extra_args=("--refresh-frontend",), frontend_dist=dist)
    assert (out / "index.html").read_text() == "old html"


def test_frontend_with_root_relative_assets_is_rejected(tmp_path, monkeypatch, domain_config):
    dist = tmp_path / "root-relative-dist"
    (dist / "data").mkdir(parents=True)
    (dist / "index.html").write_text('<html><script src="/assets/app.js"></script></html>')
    (dist / "data" / "build-info.json").write_text(json.dumps({"staticMode": True}))

    with pytest.raises(SystemExit):
        _run_export(tmp_path, monkeypatch, domain_config, frontend_dist=dist)
