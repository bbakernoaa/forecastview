"""Field diagnostics utility for debugging and validation.

Provides functions to print and collect comprehensive statistics
about 2D numpy arrays returned by FieldSelector.select().
"""

from __future__ import annotations

from typing import Any

import numpy as np


def summarize_field(
    field: np.ndarray,
    variable_name: str | None = None,
    units: str | None = None,
) -> dict[str, Any]:
    """Compute comprehensive statistics for a 2D field array.

    Parameters
    ----------
    field : np.ndarray
        2D numpy array of field values (may contain NaN or masked values).
    variable_name : str, optional
        Name of the variable for labeling.
    units : str, optional
        Units string for labeling.

    Returns
    -------
    dict[str, Any]
        Dictionary containing all computed diagnostics:
        - variable: variable name (or "unknown")
        - units: units string (or "")
        - shape: (rows, cols) tuple
        - dtype: string representation of numpy dtype
        - min, max, mean, std, median: float (NaN-safe)
        - nan_count: number of NaN/masked values
        - total_count: total number of elements
        - valid_count: total - nan_count
        - percentiles: dict mapping percentile labels to values
        - unique_count: number of unique values (capped at 10000)
        - unique_capped: whether unique count was capped
        - has_negative: whether any valid value is negative
        - histogram: dict with bin_edges and counts arrays
    """
    summary: dict[str, Any] = {}

    summary["variable"] = variable_name or "unknown"
    summary["units"] = units or ""
    summary["shape"] = field.shape
    summary["dtype"] = str(field.dtype)

    # Handle masked arrays by converting to regular array with NaN
    if isinstance(field, np.ma.MaskedArray):
        data = field.filled(np.nan).astype(float)
    else:
        data = field.astype(float) if not np.issubdtype(field.dtype, np.floating) else field

    flat = data.ravel()
    total_count = flat.size
    nan_count = int(np.count_nonzero(np.isnan(flat)))
    valid_count = total_count - nan_count

    summary["total_count"] = total_count
    summary["nan_count"] = nan_count
    summary["valid_count"] = valid_count

    if valid_count == 0:
        # All NaN — fill stats with NaN
        summary["min"] = float("nan")
        summary["max"] = float("nan")
        summary["mean"] = float("nan")
        summary["std"] = float("nan")
        summary["median"] = float("nan")
        summary["percentiles"] = {p: float("nan") for p in ["1", "5", "25", "50", "75", "95", "99"]}
        summary["unique_count"] = 0
        summary["unique_capped"] = False
        summary["has_negative"] = False
        summary["histogram"] = {"bin_edges": [], "counts": []}
        return summary

    # Core statistics (NaN-safe)
    summary["min"] = float(np.nanmin(data))
    summary["max"] = float(np.nanmax(data))
    summary["mean"] = float(np.nanmean(data))
    summary["std"] = float(np.nanstd(data))
    summary["median"] = float(np.nanmedian(data))

    # Percentiles
    pct_keys = [1, 5, 25, 50, 75, 95, 99]
    pct_values = np.nanpercentile(data, pct_keys)
    summary["percentiles"] = {str(p): float(v) for p, v in zip(pct_keys, pct_values, strict=False)}

    # Unique values (cap computation for large arrays)
    _UNIQUE_CAP = 10000
    valid_values = flat[~np.isnan(flat)]
    if valid_values.size <= _UNIQUE_CAP:
        unique_count = int(np.unique(valid_values).size)
        summary["unique_capped"] = False
    else:
        # Sample to estimate uniqueness without excessive memory
        sample = valid_values[:_UNIQUE_CAP]
        unique_count = int(np.unique(sample).size)
        summary["unique_capped"] = True
    summary["unique_count"] = unique_count

    # Negative values
    summary["has_negative"] = bool(np.any(valid_values < 0))

    # Histogram (10 bins across value range)
    num_bins = 10
    counts, bin_edges = np.histogram(valid_values, bins=num_bins)
    summary["histogram"] = {
        "bin_edges": [float(e) for e in bin_edges],
        "counts": [int(c) for c in counts],
    }

    return summary


def print_field_stats(
    field: np.ndarray,
    variable_name: str | None = None,
    units: str | None = None,
) -> None:
    """Print comprehensive field diagnostics to stdout.

    Useful during development and validation to inspect extracted fields.

    Parameters
    ----------
    field : np.ndarray
        2D numpy array of field values.
    variable_name : str, optional
        Name of the variable for display.
    units : str, optional
        Units string for display.
    """
    stats = summarize_field(field, variable_name=variable_name, units=units)

    header = f"Field Diagnostics: {stats['variable']}"
    if stats["units"]:
        header += f" [{stats['units']}]"
    print(f"\n{'=' * 60}")
    print(header)
    print("=" * 60)

    # Shape and dtype
    rows, cols = stats["shape"]
    print(f"  Shape:          {rows} rows x {cols} cols ({stats['total_count']} points)")
    print(f"  Data type:      {stats['dtype']}")
    print(
        f"  NaN/masked:     {stats['nan_count']} / {stats['total_count']} ({_pct(stats['nan_count'], stats['total_count'])})"
    )
    print(f"  Valid values:   {stats['valid_count']}")

    if stats["valid_count"] == 0:
        print("  ** All values are NaN/masked — no statistics available **")
        print("=" * 60)
        return

    # Core stats
    print()
    print(f"  Min:            {stats['min']:.6g}")
    print(f"  Max:            {stats['max']:.6g}")
    print(f"  Mean:           {stats['mean']:.6g}")
    print(f"  Std Dev:        {stats['std']:.6g}")
    print(f"  Median:         {stats['median']:.6g}")

    # Percentiles
    print()
    print("  Percentiles:")
    pcts = stats["percentiles"]
    print(f"    1st:   {pcts['1']:.6g}")
    print(f"    5th:   {pcts['5']:.6g}")
    print(f"    25th:  {pcts['25']:.6g}")
    print(f"    50th:  {pcts['50']:.6g}")
    print(f"    75th:  {pcts['75']:.6g}")
    print(f"    95th:  {pcts['95']:.6g}")
    print(f"    99th:  {pcts['99']:.6g}")

    # Unique values
    print()
    unique_label = f"{stats['unique_count']}"
    if stats["unique_capped"]:
        unique_label += " (estimated from first 10000 values)"
    print(f"  Unique values:  {unique_label}")
    print(f"  Has negatives:  {'Yes' if stats['has_negative'] else 'No'}")

    # Text histogram
    print()
    print("  Value Distribution:")
    _print_histogram(stats["histogram"])

    print("=" * 60)


def _pct(part: int, total: int) -> str:
    """Format a percentage string."""
    if total == 0:
        return "0.0%"
    return f"{100.0 * part / total:.1f}%"


def _print_histogram(histogram: dict[str, list]) -> None:
    """Print a simple text histogram."""
    bin_edges = histogram["bin_edges"]
    counts = histogram["counts"]

    if not counts:
        print("    (no data)")
        return

    max_count = max(counts) if counts else 1
    bar_width = 30

    for i, count in enumerate(counts):
        lo = bin_edges[i]
        hi = bin_edges[i + 1]
        bar_len = int(bar_width * count / max_count) if max_count > 0 else 0
        bar = "\u2588" * bar_len
        print(f"    [{lo:>10.4g}, {hi:>10.4g}) | {bar:<{bar_width}} {count}")
