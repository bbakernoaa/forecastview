# Orientation Validation

## Purpose

Validate that forecast fields are geographically oriented correctly when rendered on the map — no mirroring, rotation, or offset errors exist between the backend data pipeline and the frontend display.

## Validation Variable

| Property | Value |
|----------|-------|
| Variable | `duAOD550` |
| Full name | Dust Aerosol Optical Depth at 550nm |
| Fallback | `totAOD550` (Total AOD) if dust AOD unavailable |
| Forecast hour | 0 (analysis time) |
| Source | NOAA GEFS-Aerosols (noaa-gefs-pds S3 bucket) |

## Why duAOD550?

Dust AOD at 550nm is chosen because it produces a **visually distinctive and geographically recognizable spatial pattern**:

1. **Saharan dust plume** — Consistently high values over North Africa and the Sahara Desert. This is the most reliable geographic marker because the Sahara is the world's largest dust source and produces high AOD values year-round.

2. **Clear geographic anchor** — The dust plume occupies a well-known geographic region that is easy to verify visually on any world map.

3. **Asymmetric pattern** — The dust signal is concentrated in the Northern Hemisphere and western portion of the Eastern Hemisphere, making mirroring or rotation errors immediately obvious.

## Expected Spatial Features

| Feature | Approximate Location | AOD Range |
|---------|---------------------|-----------|
| Saharan dust plume | 15–30°N, 345–030°E | High (0.3–2.0+) |
| Arabian Peninsula dust | 18–30°N, 035–060°E | Moderate-High (0.2–1.0) |
| East Asian dust (Taklamakan/Gobi) | 35–45°N, 075–110°E | Moderate (0.1–0.5) |
| Clean ocean background | All oceans | Low (< 0.05) |
| Polar regions | Above 60°N/below 60°S | Very low (< 0.02) |

## Orientation Checks

When viewing the reference plot, verify:

1. **North is up** — The Saharan dust plume should appear in the upper portion of a global plot (Northern Hemisphere).
2. **No east-west flip** — Africa should appear left of the Arabian Peninsula; the Atlantic Ocean should be to the west (left) of Africa.
3. **Correct latitude band** — High dust values should be concentrated between approximately 15°N and 30°N, not at the equator or in the Southern Hemisphere.
4. **Correct longitude** — The Saharan signal peaks near 0–20°E (central North Africa), not at 180°E or in the Western Hemisphere.

## How to Run

```bash
conda run -n forecastview python backend/scripts/validate_orientation.py
```

### Output

- **Reference plot**: `output/validation/dust_aod_reference.png`
- **Console output**: Field statistics, grid info, orientation summary

### Requirements

- Active `forecastview` conda environment
- Network access to the `noaa-gefs-pds` S3 bucket (anonymous, no credentials needed)
- matplotlib and cartopy installed

### Graceful Failure

If S3 is unreachable, the script exits with code 0 (not an error) and prints a message indicating that network access is required. This allows the script to be included in CI without failing when offline.

## Comparison Procedure

After generating the reference plot:

1. Run the web viewer and navigate to the same date/run/variable/forecast hour
2. Visually compare the spatial pattern on the MapLibre map against `dust_aod_reference.png`
3. Confirm that high-value regions (warm colors) appear in the same geographic locations
4. If patterns match: orientation is validated — no mirroring or rotation
5. If patterns are mirrored or rotated: investigate scanning order, latitude flip, or longitude offset in the data pipeline

## Related Files

- Script: `backend/scripts/validate_orientation.py`
- Field stats utility: `backend/app/utils/field_stats.py`
- Reference plot utility: `backend/app/utils/reference_plot.py`
- Grid inspector: `backend/app/utils/grid_inspector.py`
- Full verification script: `backend/scripts/verify_field.py`
