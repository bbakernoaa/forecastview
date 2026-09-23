"""ncv - NetCDF / Scientific Data Viewer and Difference CLI tool.

Supports computing differences between files/datasets:
  ncv --diff file1 file2
  ncv --diff first=files1* second=files2*
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import xarray as xr


def parse_diff_args(diff_args: list[str]) -> tuple[list[str], list[str]]:
    """Parse positional or keyword diff arguments.

    Supports:
      1) ['file1', 'file2']
      2) ['first=files1*', 'second=files2*'] or ['second=files2*', 'first=files1*']
      3) ['first=file1', 'file2', 'second=file3', 'file4']
    """
    if not diff_args:
        raise ValueError("No arguments provided to --diff.")

    has_kv = any(arg.startswith("first=") or arg.startswith("second=") for arg in diff_args)

    raw_first: list[str] = []
    raw_second: list[str] = []

    if has_kv:
        current_group: str | None = None
        for arg in diff_args:
            if arg.startswith("first="):
                current_group = "first"
                val = arg.split("=", 1)[1]
                if val:
                    raw_first.append(val)
            elif arg.startswith("second="):
                current_group = "second"
                val = arg.split("=", 1)[1]
                if val:
                    raw_second.append(val)
            elif current_group == "first":
                raw_first.append(arg)
            elif current_group == "second":
                raw_second.append(arg)
            else:
                raise ValueError(
                    f"Unexpected argument '{arg}' before 'first=' or 'second=' header."
                )
        if not raw_first or not raw_second:
            raise ValueError("Both 'first' and 'second' must be specified in --diff key=value format.")
    else:
        # Positional arguments
        if len(diff_args) != 2:
            raise ValueError(
                f"Expected exactly 2 positional arguments for --diff, got {len(diff_args)}: {diff_args}"
            )
        raw_first = [diff_args[0]]
        raw_second = [diff_args[1]]

    def expand_patterns(patterns: list[str]) -> list[str]:
        expanded = []
        for pat in patterns:
            matches = sorted(glob.glob(pat))
            if matches:
                expanded.extend(matches)
            else:
                expanded.append(pat)
        return expanded

    first_files = expand_patterns(raw_first)
    second_files = expand_patterns(raw_second)

    return first_files, second_files


def open_file_or_mfdataset(paths: list[str]) -> xr.Dataset:
    """Open a single file or multiple files as an xarray Dataset."""
    if len(paths) == 1:
        p = paths[0]
        if not Path(p).exists():
            raise FileNotFoundError(f"File not found: {p}")
        return xr.open_dataset(p)
    else:
        for p in paths:
            if not Path(p).exists():
                raise FileNotFoundError(f"File not found: {p}")
        return xr.open_mfdataset(paths)


def compute_difference(
    ds1: xr.Dataset,
    ds2: xr.Dataset,
    var_name: str | None = None,
    log_scale: bool = False,
    colormap: str | None = None,
) -> dict:
    """Compute difference between ds1 and ds2.

    If log_scale is True, computes absolute difference |ds1 - ds2|.
    Otherwise computes ds1 - ds2.
    Default colormap for diff is divergent ('coolwarm').
    When log_scale is True, absolute difference is used and colormap defaults to 'viridis' if not overridden.
    """
    if var_name is None:
        # Pick the first common data variable
        common_vars = [v for v in ds1.data_vars if v in ds2.data_vars]
        if not common_vars:
            raise ValueError(
                f"No common data variables found between datasets. "
                f"ds1 vars: {list(ds1.data_vars)}, ds2 vars: {list(ds2.data_vars)}"
            )
        var_name = common_vars[0]

    if var_name not in ds1.data_vars or var_name not in ds2.data_vars:
        raise ValueError(f"Variable '{var_name}' not found in both datasets.")

    da1 = ds1[var_name]
    da2 = ds2[var_name]

    diff_data = da1 - da2

    if log_scale:
        diff_data = np.abs(diff_data)
        chosen_colormap = colormap if colormap else "viridis"
    else:
        chosen_colormap = colormap if colormap else "coolwarm"

    min_val = float(np.nanmin(diff_data.values)) if hasattr(diff_data, "values") else float(np.nanmin(diff_data))
    max_val = float(np.nanmax(diff_data.values)) if hasattr(diff_data, "values") else float(np.nanmax(diff_data))
    mean_val = float(np.nanmean(diff_data.values)) if hasattr(diff_data, "values") else float(np.nanmean(diff_data))

    return {
        "variable": var_name,
        "diff": diff_data,
        "log_scale": log_scale,
        "colormap": chosen_colormap,
        "min": min_val,
        "max": max_val,
        "mean": mean_val,
    }


def main(args: Sequence[str] | None = None) -> int:
    """Main CLI entry point for ncv."""
    parser = argparse.ArgumentParser(
        prog="ncv",
        description="ForecastView NetCDF / GRIB Data Viewer & Difference CLI",
    )
    parser.add_argument(
        "--diff",
        nargs="+",
        help="Compute difference between two files or file patterns (e.g. --diff f1 f2 or --diff first=files1* second=files2*)",
    )
    parser.add_argument(
        "-v", "--variable",
        help="Variable name to diff or inspect",
    )
    parser.add_argument(
        "--log", "--log-scale",
        action="store_true",
        dest="log_scale",
        help="Use log scale for difference (applies absolute difference |A - B|)",
    )
    parser.add_argument(
        "--colormap",
        help="Override colormap (default for diff is divergent 'coolwarm')",
    )

    parsed = parser.parse_args(args)

    if parsed.diff:
        try:
            first_files, second_files = parse_diff_args(parsed.diff)
            print(f"Opening first dataset ({len(first_files)} files): {first_files}")
            ds1 = open_file_or_mfdataset(first_files)
            print(f"Opening second dataset ({len(second_files)} files): {second_files}")
            ds2 = open_file_or_mfdataset(second_files)

            res = compute_difference(
                ds1,
                ds2,
                var_name=parsed.variable,
                log_scale=parsed.log_scale,
                colormap=parsed.colormap,
            )

            print("=" * 60)
            print("DIFFERENCE SUMMARY")
            print("=" * 60)
            print(f"Variable:   {res['variable']}")
            print(f"Log Scale:  {res['log_scale']}")
            print(f"Colormap:   {res['colormap']}")
            print(f"Min Diff:   {res['min']:.6g}")
            print(f"Max Diff:   {res['max']:.6g}")
            print(f"Mean Diff:  {res['mean']:.6g}")
            print("=" * 60)
            return 0
        except Exception as exc:
            print(f"Error computing difference: {exc}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
