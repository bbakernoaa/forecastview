"""Tests for static dataset bundle validation."""

from __future__ import annotations

import json
import fcntl
import sys
import threading
import types
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import pytest
import numpy as np
import xarray as xr
import yaml

from backend.scripts import datasets
from backend.scripts.datasets import check_site, load_definition


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    run = site / "data" / "GCAVSv1" / "20250901" / "00"
    (run / "fill" / "TMP").mkdir(parents=True)
    (run / "field" / "TMP").mkdir(parents=True)
    (site / "data").mkdir(parents=True, exist_ok=True)
    (site / "data" / "catalog.json").write_text(json.dumps({"products": [{"product": "GCAVSv1", "description": "Sample"}]}))
    (site / "data" / "GCAVSv1" / "dates.json").write_text(json.dumps({"dates": ["20250901"]}))
    (site / "data" / "GCAVSv1" / "20250901" / "runs.json").write_text(json.dumps({"runs": ["00"]}))
    (run / "variables.json").write_text(json.dumps({"variables": [{"name": "TMP"}]}))
    (run / "levels.json").write_text(json.dumps({"byVariable": {"TMP": []}}))
    (run / "times.json").write_text(json.dumps({"forecast_hours": [{"fhr": 1}]}))
    (run / "grid.json").write_text(json.dumps({"nx": 2, "ny": 2, "coordinates": "coordinates.bin"}))
    (run / "coordinates.bin").write_bytes(bytes(2 * 2 * 2 * 4))
    (run / "field" / "TMP" / "f001.bin").write_bytes(bytes(2 * 2 * 4))
    from PIL import Image
    Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(run / "fill" / "TMP" / "f001.png")
    return site


def test_check_site_accepts_complete_curvilinear_grid(tmp_path):
    assert check_site(_site(tmp_path)) == 0


def test_check_site_rejects_truncated_coordinate_grid(tmp_path):
    site = _site(tmp_path)
    (site / "data/GCAVSv1/20250901/00/coordinates.bin").write_bytes(b"short")
    assert check_site(site) == 1


def test_check_site_rejects_unreadable_fill_image(tmp_path):
    site = _site(tmp_path)
    (site / "data/GCAVSv1/20250901/00/fill/TMP/f001.png").write_bytes(b"bad")
    assert check_site(site) == 1


def test_check_site_accepts_map_only_export_without_point_grid(tmp_path):
    site = _site(tmp_path)
    run = site / "data/GCAVSv1/20250901/00"
    (run / "grid.json").unlink()
    (run / "coordinates.bin").unlink()
    import shutil
    shutil.rmtree(run / "field")
    assert check_site(site) == 0


def test_build_site_includes_multiple_configs_and_replaces_output_only_after_check(tmp_path, monkeypatch):
    output = tmp_path / "published-copy"
    output.mkdir()
    (output / "old-bundle-marker").write_text("old")
    calls = []

    def export(config, candidate):
        calls.append(config)
        (candidate / f"{config.stem}.asset").write_text("ok")
        return 0

    monkeypatch.setattr(datasets, "export_product", export)
    monkeypatch.setattr(datasets, "check_site", lambda site: 0)
    monkeypatch.setattr(datasets, "load_definition", lambda path: ({"product": {"id": path.stem}}, Path("/tmp")))

    assert datasets.build_site([Path("one.yaml"), Path("two.yaml")], output) == 0
    assert calls == [Path("one.yaml"), Path("two.yaml")]
    assert (output / "old-bundle-marker").read_text() == "old"
    assert (output / "one.asset").read_text() == "ok"
    assert (output / "two.asset").read_text() == "ok"
    assert (output / "export-info.json").is_file()


def test_build_site_export_info_tracks_preserved_catalog_products(tmp_path, monkeypatch):
    output = tmp_path / "published"
    data = output / "data"
    data.mkdir(parents=True)
    (data / "catalog.json").write_text(json.dumps({
        "products": [{"product": "GCAVSv1", "description": "Existing"}],
    }))

    def export(config, candidate):
        catalog_path = candidate / "data" / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        catalog["products"].append({"product": "AQMv8", "description": "Added"})
        catalog_path.write_text(json.dumps(catalog))
        return 0

    monkeypatch.setattr(datasets, "export_product", export)
    monkeypatch.setattr(datasets, "check_site", lambda site: 0)
    monkeypatch.setattr(
        datasets,
        "load_definition",
        lambda path: ({"product": {"id": path.stem}}, Path("/tmp")),
    )
    assert datasets.build_site([Path("AQMv8.yaml")], output) == 0
    info = json.loads((output / "export-info.json").read_text())
    assert info["datasets"] == ["GCAVSv1", "AQMv8"]


def test_build_site_serializes_concurrent_dataset_updates(tmp_path, monkeypatch):
    output = tmp_path / "published"
    data = output / "data"
    data.mkdir(parents=True)
    (data / "catalog.json").write_text(json.dumps({"products": [{"product": "existing"}]}))
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    results = []

    def export(config, candidate):
        if config.stem == "first":
            first_entered.set()
            assert release_first.wait(timeout=5)
        else:
            second_entered.set()
        catalog_path = candidate / "data" / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        catalog["products"].append({"product": config.stem})
        catalog_path.write_text(json.dumps(catalog))
        return 0

    monkeypatch.setattr(datasets, "export_product", export)
    monkeypatch.setattr(datasets, "check_site", lambda site: 0)
    monkeypatch.setattr(
        datasets,
        "load_definition",
        lambda path: ({"product": {"id": path.stem}}, Path("/tmp")),
    )

    first = threading.Thread(
        target=lambda: results.append(datasets.build_site([Path("first.yaml")], output))
    )
    second = threading.Thread(
        target=lambda: results.append(datasets.build_site([Path("second.yaml")], output))
    )
    first.start()
    assert first_entered.wait(timeout=2)
    second.start()
    second_entered_during_first = second_entered.wait(timeout=0.2)
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not second_entered_during_first
    assert not first.is_alive() and not second.is_alive()
    assert results == [0, 0]
    products = json.loads((output / "data" / "catalog.json").read_text())["products"]
    assert {item["product"] for item in products} == {"existing", "first", "second"}


def test_build_site_recovers_previous_bundle_after_interrupted_swap(tmp_path, monkeypatch):
    output = tmp_path / "published"
    backup = output.with_name(".published.previous")
    data = backup / "data"
    data.mkdir(parents=True)
    (data / "catalog.json").write_text(json.dumps({"products": [{"product": "preserved"}]}))

    def export(config, candidate):
        catalog_path = candidate / "data" / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        catalog["products"].append({"product": "new"})
        catalog_path.write_text(json.dumps(catalog))
        return 0

    monkeypatch.setattr(datasets, "export_product", export)
    monkeypatch.setattr(datasets, "check_site", lambda site: 0)
    monkeypatch.setattr(
        datasets,
        "load_definition",
        lambda path: ({"product": {"id": path.stem}}, Path("/tmp")),
    )

    assert datasets.build_site([Path("new.yaml")], output) == 0
    products = json.loads((output / "data" / "catalog.json").read_text())["products"]
    assert {item["product"] for item in products} == {"preserved", "new"}


def _dataset_config(tmp_path: Path, source: Path, variable: str = "TMP") -> Path:
    config = tmp_path / "GCAVSv1.yaml"
    config.write_text(f"""
product:
  id: GCAVSv1
  name: Test dataset
ingest:
  source_dir: {source}
  store_path: manifests/GCAVSv1
  file_glob: '**/*.grib2'
variables:
  {variable}:
    shortName: {variable}
    fullName: Test field
    rendering:
      contourInterval: 1
      fillLevels: [0, 1, 2]
""")
    return config


def test_dataset_validation_accepts_case_sensitive_ids_and_local_grib(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.grib2").write_bytes(b"grib")
    raw, resolved_source = load_definition(_dataset_config(tmp_path, source))
    assert raw["product"]["id"] == "GCAVSv1"
    assert resolved_source == source.resolve()


def test_dataset_validation_rejects_empty_source_glob(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    try:
        load_definition(_dataset_config(tmp_path, source))
    except ValueError as exc:
        assert "matched no files" in str(exc)
    else:
        raise AssertionError("empty local source unexpectedly validated")


def test_dataset_validation_rejects_variable_path_traversal(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.grib2").write_bytes(b"grib")
    try:
        load_definition(_dataset_config(tmp_path, source, "../TMP"))
    except ValueError as exc:
        assert "variable" in str(exc)
    else:
        raise AssertionError("unsafe variable path unexpectedly validated")


def test_dataset_validation_rejects_duplicate_or_negative_expected_hours(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.grib2").write_bytes(b"grib")
    config = _dataset_config(tmp_path, source)
    contents = config.read_text().replace(
        "  file_glob: '**/*.grib2'",
        "  file_glob: '**/*.grib2'\n  expected_forecast_hours: [0, -1, 0]",
    )
    config.write_text(contents)
    try:
        load_definition(config)
    except ValueError as exc:
        assert "expected_forecast_hours" in str(exc)
    else:
        raise AssertionError("invalid expected forecast hours unexpectedly validated")


def test_ingest_refuses_a_concurrent_writer(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.grib2").write_bytes(b"grib")
    config = _dataset_config(tmp_path, source)
    store = tmp_path / "manifests"
    store.mkdir()
    config.write_text(config.read_text().replace("manifests/GCAVSv1", str(store)))
    with (store / ".ingest.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="another ingest is writing"):
            datasets.ingest_local(config)


def _manifest_dataset(levels: int = 1) -> xr.Dataset:
    return xr.Dataset(
        {"TMP": (("valid_time", "height", "y", "x"), np.zeros((1, levels, 2, 3)))},
        coords={
            "valid_time": [0],
            "height": np.arange(levels),
            "latitude": (("y", "x"), np.zeros((2, 3))),
            "longitude": (("y", "x"), np.zeros((2, 3))),
        },
    )


def test_manifest_validation_accepts_2d_curvilinear_coordinates():
    available = datasets.validate_manifest_dataset(_manifest_dataset(), {"TMP"})
    assert available == {"TMP"}


def test_manifest_validation_rejects_a_missing_lead_for_one_variable():
    valid_times = np.array(["2025-09-01T00:00", "2025-09-01T03:00"], dtype="datetime64[ns]")
    dataset = xr.Dataset(
        {
            "TMP": (("valid_time", "y", "x"), np.ones((2, 2, 3))),
            "RH": (("valid_time", "y", "x"), np.array([np.ones((2, 3)), np.full((2, 3), np.nan)])),
        },
        coords={
            "valid_time": valid_times,
            "latitude": (("y", "x"), np.zeros((2, 3))),
            "longitude": (("y", "x"), np.zeros((2, 3))),
        },
    )

    with pytest.raises(ValueError, match=r"RH.*forecast hour 3"):
        datasets.validate_manifest_dataset(
            dataset,
            {"TMP", "RH"},
            expected_forecast_hours={0, 3},
            init_time=datetime(2025, 9, 1),
        )


def test_manifest_validation_rejects_variable_without_time_axis_when_hours_are_required():
    dataset = xr.Dataset(
        {"TMP": (("y", "x"), np.ones((2, 3)))},
        coords={
            "latitude": (("y", "x"), np.zeros((2, 3))),
            "longitude": (("y", "x"), np.zeros((2, 3))),
        },
    )

    with pytest.raises(ValueError, match=r"TMP.*no time coordinate.*forecast hour 0"):
        datasets.validate_manifest_dataset(
            dataset,
            {"TMP"},
            expected_forecast_hours={0},
            init_time=datetime(2025, 9, 1),
        )


def test_ingest_preserves_manifest_when_one_variable_is_missing_a_required_lead(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.grib2").write_bytes(b"sample")
    config = _dataset_config(tmp_path, source)
    store = tmp_path / "manifests"
    store.mkdir()
    raw = yaml.safe_load(config.read_text())
    raw["ingest"]["store_path"] = str(store)
    raw["ingest"]["expected_forecast_hours"] = [0, 3]
    raw["variables"]["RH"] = {
        "shortName": "RH",
        "fullName": "Relative humidity",
        "rendering": {"fillLevels": [0, 50, 100]},
    }
    config.write_text(yaml.safe_dump(raw))
    target = store / "20250901" / "00" / "manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text("previous-valid-manifest")

    class Message:
        def __init__(self, lead):
            self.year, self.month, self.day, self.hour = 2025, 9, 1, 0
            self.leadTime = timedelta(hours=lead)

    class Messages:
        items = [Message(0), Message(3)]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            return self.items[index]

        def __iter__(self):
            return iter(self.items)

    grib2io = types.ModuleType("grib2io")
    grib2io.open = lambda path: Messages()
    kerchunk = types.ModuleType("grib2io.kerchunk")
    kerchunk.ReferenceGenerator = lambda *args, **kwargs: types.SimpleNamespace(
        generate=lambda: {"version": 1, "refs": {}}
    )
    grib2io.kerchunk = kerchunk
    monkeypatch.setitem(sys.modules, "grib2io", grib2io)
    monkeypatch.setitem(sys.modules, "grib2io.kerchunk", kerchunk)

    class FakeReferenceFS:
        def get_mapper(self, path):
            return {}

    monkeypatch.setattr("fsspec.filesystem", lambda *args, **kwargs: FakeReferenceFS())
    dataset = xr.Dataset(
        {
            "TMP": (("valid_time", "y", "x"), np.ones((2, 2, 3))),
            "RH": (("valid_time", "y", "x"), np.array([np.ones((2, 3)), np.full((2, 3), np.nan)])),
        },
        coords={
            "valid_time": np.array(["2025-09-01T00:00", "2025-09-01T03:00"], dtype="datetime64[ns]"),
            "latitude": (("y", "x"), np.zeros((2, 3))),
            "longitude": (("y", "x"), np.zeros((2, 3))),
        },
    )
    monkeypatch.setattr(xr, "open_dataset", lambda *args, **kwargs: dataset)

    assert datasets.ingest_local(config) == 1
    assert target.read_text() == "previous-valid-manifest"
    report = json.loads((store / "ingest-report.json").read_text())
    assert report["status"] == "failed"
    assert "RH" in report["error"]


def test_manifest_validation_rejects_ambiguous_multiple_levels():
    with pytest.raises(ValueError, match="multiple selectable levels"):
        datasets.validate_manifest_dataset(_manifest_dataset(levels=2), {"TMP"})


def test_manifest_validation_rejects_missing_geolocation():
    ds = _manifest_dataset().drop_vars(["latitude", "longitude"])
    with pytest.raises(ValueError, match="no geographic latitude/longitude"):
        datasets.validate_manifest_dataset(ds, {"TMP"})
