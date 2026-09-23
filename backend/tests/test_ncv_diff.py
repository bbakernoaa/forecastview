"""Tests for the ncv CLI difference utility."""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr

from backend.scripts.ncv import compute_difference, main, parse_diff_args


def test_parse_diff_args_positional(tmp_path):
    f1 = tmp_path / "f1.nc"
    f2 = tmp_path / "f2.nc"
    f1.touch()
    f2.touch()

    first, second = parse_diff_args([str(f1), str(f2)])
    assert first == [str(f1)]
    assert second == [str(f2)]


def test_parse_diff_args_keyword_patterns(tmp_path):
    d1 = tmp_path / "run1"
    d2 = tmp_path / "run2"
    d1.mkdir()
    d2.mkdir()

    f1 = d1 / "fileA.nc"
    f2 = d2 / "fileB.nc"
    f1.touch()
    f2.touch()

    first, second = parse_diff_args([f"first={d1}/*.nc", f"second={d2}/*.nc"])
    assert first == [str(f1)]
    assert second == [str(f2)]


def test_compute_difference_linear():
    ds1 = xr.Dataset({"temp": (("y", "x"), np.array([[10.0, 20.0], [30.0, 40.0]]))})
    ds2 = xr.Dataset({"temp": (("y", "x"), np.array([[12.0, 15.0], [30.0, 50.0]]))})

    res = compute_difference(ds1, ds2, var_name="temp", log_scale=False)
    assert res["variable"] == "temp"
    assert res["log_scale"] is False
    assert res["colormap"] == "coolwarm"
    assert res["min"] == -10.0
    assert res["max"] == 5.0
    assert np.allclose(res["diff"].values, [[-2.0, 5.0], [0.0, -10.0]])


def test_compute_difference_log_scale_absolute():
    ds1 = xr.Dataset({"temp": (("y", "x"), np.array([[10.0, 20.0], [30.0, 40.0]]))})
    ds2 = xr.Dataset({"temp": (("y", "x"), np.array([[12.0, 15.0], [30.0, 50.0]]))})

    res = compute_difference(ds1, ds2, var_name="temp", log_scale=True)
    assert res["variable"] == "temp"
    assert res["log_scale"] is True
    assert res["colormap"] == "viridis"
    assert res["min"] == 0.0
    assert res["max"] == 10.0
    assert np.allclose(res["diff"].values, [[2.0, 5.0], [0.0, 10.0]])


def test_ncv_cli_main_diff(tmp_path, capsys):
    f1 = tmp_path / "test1.nc"
    f2 = tmp_path / "test2.nc"

    ds1 = xr.Dataset({"air": (("y", "x"), np.array([[1.0, 2.0]]))})
    ds2 = xr.Dataset({"air": (("y", "x"), np.array([[3.0, 1.0]]))})
    ds1.to_netcdf(f1)
    ds2.to_netcdf(f2)

    ret = main(["--diff", str(f1), str(f2)])
    assert ret == 0

    captured = capsys.readouterr().out
    assert "DIFFERENCE SUMMARY" in captured
    assert "Variable:   air" in captured
    assert "Colormap:   coolwarm" in captured

    ret_log = main(["--diff", f"first={f1}", f"second={f2}", "--log"])
    assert ret_log == 0

    captured_log = capsys.readouterr().out
    assert "Log Scale:  True" in captured_log
    assert "Colormap:   viridis" in captured_log
