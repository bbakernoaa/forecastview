"""Tests for local (offline) ingest functionality for GEFS and AQM products.

Verifies that local ingest options generate valid manifests and read data
without attempting to connect to AWS S3.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.data.aqm_store import AQMStore
from backend.scripts.ingest import build_urls, ingest_date
from backend.scripts.ingest_aqm import (
    build_manifest_local,
    discover_dates_local,
    discover_runs_local,
    list_grib_files_local,
)


def test_build_urls_local_path():
    """build_urls generates local file paths when local_path_pattern is provided."""
    pattern = "/tmp/data/gefs.{date}/{cycle}/gefs.chem.t{cycle}z.f{fhr:03d}.grib2"
    urls = build_urls(
        date="20260821",
        cycle="00",
        forecast_hours=[0, 3],
        local_path_pattern=pattern,
    )

    assert len(urls) == 2
    assert urls[0] == "/tmp/data/gefs.20260821/00/gefs.chem.t00z.f000.grib2"
    assert urls[1] == "/tmp/data/gefs.20260821/00/gefs.chem.t00z.f003.grib2"
    assert not any(u.startswith("s3://") for u in urls)


def test_ingest_date_local_mode(tmp_path: Path):
    """ingest_date uses storage_options=None and passes local_path_pattern to ReferenceGenerator."""
    # Create fake local GRIB file
    grib_dir = tmp_path / "gefs.20260821" / "00"
    grib_dir.mkdir(parents=True)
    grib_file = grib_dir / "file_f000.grib2"
    grib_file.write_bytes(b"dummy_grib_bytes")

    pattern = str(tmp_path / "gefs.{date}" / "{cycle}" / "file_f{fhr:03d}.grib2")
    store_dir = tmp_path / "manifests"

    mock_gen = MagicMock()
    mock_gen.generate.return_value = {"version": 1, "refs": {}}

    with (
        patch("grib2io.kerchunk.ReferenceGenerator", return_value=mock_gen) as mock_class,
        patch("xarray.open_dataset") as mock_open_ds,
    ):
        mock_ds = MagicMock()
        mock_ds.sizes = {"time": 1}
        mock_ds.data_vars = ["aod"]
        mock_open_ds.return_value = mock_ds

        success = ingest_date(
            date="20260821",
            cycle="00",
            store_path=store_dir,
            forecast_hours=[0],
            local_path_pattern=pattern,
        )

        assert success is True
        mock_class.assert_called_once()
        _, kwargs = mock_class.call_args
        assert kwargs["storage_options"] is None

    manifest_file = store_dir / "20260821" / "00" / "manifest.json"
    assert manifest_file.exists()


def test_aqm_local_discovery(tmp_path: Path):
    """AQM local discovery correctly finds dates, runs, and GRIB2 files."""
    aqm_dir = tmp_path / "CS" / "20260821" / "06"
    aqm_dir.mkdir(parents=True)
    grib1 = aqm_dir / "aqm.t06z.ave_1hr_pm25.20260821.grib2"
    grib1.write_bytes(b"dummy")

    base = tmp_path / "CS"
    dates = discover_dates_local(base)
    assert dates == ["20260821"]

    runs = discover_runs_local(base, "20260821")
    assert runs == ["06"]

    files = list_grib_files_local(base, "20260821", "06")
    assert len(files) == 1
    assert files[0].name == "aqm.t06z.ave_1hr_pm25.20260821.grib2"


def test_aqm_build_manifest_local(tmp_path: Path):
    """build_manifest_local creates a manifest containing absolute local paths."""
    aqm_dir = tmp_path / "data" / "20260821" / "12"
    aqm_dir.mkdir(parents=True)
    grib1 = aqm_dir / "aqm.t12z.ave_1hr_pm25.20260821.grib2"
    grib1.write_bytes(b"dummy")

    store_dir = tmp_path / "manifests"
    ok = build_manifest_local(
        domain="CS",
        date="20260821",
        run="12",
        files=[grib1],
        store_path=store_dir,
    )

    assert ok is True
    manifest_path = store_dir / "aqm_CS" / "20260821" / "12" / "manifest.json"
    assert manifest_path.exists()

    with open(manifest_path) as f:
        data = json.load(f)

    assert data["product"] == "aqm"
    assert data["bucket"] == "local"
    assert "ave_1hr_pm25" in data["variables"]
    var_info = data["variables"]["ave_1hr_pm25"]
    assert var_info["local_path"] == str(grib1.resolve())


def test_aqm_store_reads_local_file(tmp_path: Path):
    """AQMStore reads GRIB bytes from local disk when local_path is specified."""
    store_dir = tmp_path / "manifests"
    run_dir = store_dir / "aqm_CS" / "20260821" / "00"
    run_dir.mkdir(parents=True)

    fake_grib = tmp_path / "fake.grib2"
    fake_grib.write_bytes(b"grib_data_content")

    manifest = {
        "product": "aqm",
        "domain": "CS",
        "date": "20260821",
        "run": "00",
        "bucket": "local",
        "variables": {
            "test_var": {
                "s3_key": str(fake_grib.resolve()),
                "local_path": str(fake_grib.resolve()),
                "filename": "fake.grib2",
            }
        },
    }

    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    store = AQMStore(store_path=str(store_dir), domain="CS")
    assert store.available_dates() == ["20260821"]
    assert store.available_runs("20260821") == ["00"]
    assert store.available_variables("20260821", "00") == ["test_var"]

    bytes_read = store._read_file_bytes(manifest["variables"]["test_var"])
    assert bytes_read == b"grib_data_content"
