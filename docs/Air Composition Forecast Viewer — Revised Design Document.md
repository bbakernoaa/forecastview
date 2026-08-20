# Air Composition Forecast Viewer

## 1. Overview

The Air Composition Forecast Viewer is a desktop-first web application for visualizing gridded air-composition forecast output stored in GRIB2.

The application will provide a DESI-like operational forecasting experience centered on:

- real geographic basemaps;
- filled contour maps;
- isolines and contour labels;
- forecast-date and run selection;
- forecast-hour navigation;
- animation;
- point inspection;
- efficient access to native forecast data through the existing Kerchunk backend.

Air composition is the first application domain.

Meteorological visualization will be added afterward using the same core viewer, data-access architecture, map framework, and timeline controls.

The application should therefore be built as a **generic gridded forecast visualization platform**, with Air Composition implemented as the first domain configuration.

---

# 2. Primary Design Goals

The viewer should be optimized for operational forecast analysis on desktop displays.

Primary goals:

1. Fast access to forecast fields.
2. High-quality DESI-like contour visualization.
3. Real geographic context.
4. Minimal preprocessing.
5. Direct use of existing GRIB2 through Kerchunk.
6. Clear initialization, forecast-hour, and valid-time handling.
7. Easy addition of new species and fields.
8. Reusable architecture for future meteorological products.
9. Smooth forecast-hour stepping and animation.
10. Shareable URL state.
11. Correct scientific handling of native model grids and projections.
12. A dense but usable forecasting-workstation interface.

---

# 3. Target Usage

The application is primarily intended for desktop forecasting workflows.

Target display environments include:

```text
1440 × 900
1920 × 1080
2560 × 1440
4K workstations
multi-monitor forecasting setups
```

The application should remain usable in narrower desktop browser windows, but mobile and tablet optimization are not primary project goals.

Design principle:

> Desktop responsive, not mobile-first.

The interface should favor:

- persistent controls;
- large map area;
- visible legends;
- persistent timeline controls;
- minimal hidden menus;
- fast switching between forecast products.

---

# 4. Initial Domain: Air Composition

Version 1 focuses on atmospheric composition.

Likely field categories include:

## Particulate Matter

- PM2.5
- PM10

## Gases

- Ozone
- NO₂
- CO
- SO₂

## Aerosols

- Aerosol optical depth
- Smoke
- Dust
- Aerosol species

## Tracers and Diagnostics

- Chemical tracers
- Column-integrated fields
- Model-specific diagnostics
- Emissions-related products

The frontend must not assume these exact fields exist.

Available fields should be derived from the actual dataset and domain configuration.

---

# 5. Future Domain: Meteorology

Meteorology will be added after the air-composition viewer is operational.

Possible future fields include:

- 2 m temperature
- 2 m dewpoint
- relative humidity
- surface pressure
- mean sea-level pressure
- wind speed and direction
- precipitation
- geopotential height
- vertical velocity
- cloud fields
- precipitable water
- CAPE and other diagnostics

Meteorology should use the same:

- date selector;
- run selector;
- valid-time model;
- timeline;
- MapLibre map;
- contour engine;
- point-query framework;
- URL state;
- caching system.

The meteorology phase should be an extension of the platform, not a rewrite.

---

# 6. Core Architectural Principle

The viewer should understand generic gridded fields.

The core application should work with:

```text
dataset
initialization time
valid time
forecast hour
variable
vertical level
units
grid geometry
rendering configuration
```

It should not fundamentally care whether the displayed field represents:

```text
PM2.5
ozone
dust
temperature
geopotential height
wind
smoke
```

Domain-specific behavior belongs in metadata and configuration.

---

# 7. Source Data

Forecast output remains in its original **GRIB2** format.

GRIB2 is authoritative storage.

The system should not require permanent conversion to:

- GeoTIFF;
- Zarr;
- NetCDF;
- PNG forecast archives;
- pre-generated raster products.

The existing Kerchunk backend will provide efficient virtual access to the GRIB2 content.

---

# 8. Kerchunk Integration

The existing Kerchunk implementation should be treated as the primary forecast-data access layer.

Conceptually:

```text
Forecast model
      |
      v
   GRIB2 files
      |
      v
Kerchunk references
      |
      v
Virtual dataset
      |
      v
xarray-compatible field access
```

The application should preserve lazy or chunked reading whenever practical.

The backend should avoid loading complete model runs when only one field or region is required.

---

# 9. Projection Strategy

## 9.1 Scientific Projection

All scientific data remains in its native model grid and projection for:

- field values;
- numerical calculations;
- thresholds;
- statistics;
- interpolation;
- verification;
- contour-value determination.

The application must not use Web Mercator as the scientific computational grid.

---

## 9.2 Presentation Projection

The canonical web-map presentation projection will be:

```text
EPSG:3857
Web Mercator
```

This applies to the visualization layer only.

Design rule:

> Scientific data remains in its native model projection. EPSG:3857 is the canonical presentation projection for the web application.

---

## 9.3 Projection Pipeline

Conceptually:

```text
Native GRIB2/model grid
          |
          v
Kerchunk-backed field
          |
          v
Scientific field processing
          |
          +-------------------+
          |                   |
          v                   v
      isolines          filled field
          |                   |
          v                   v
native-grid geometry      rendering
          |                   |
          v                   v
 geographic coordinates / reprojection
          |
          v
     Web Mercator
       EPSG:3857
          |
          v
       MapLibre
```

The original data is never permanently rewritten solely to satisfy the web map.

---

# 10. Contour Projection Strategy

For isolines:

1. Read the field in its native model grid.
2. Generate contour lines based on the native numerical field.
3. Associate contour vertices with model-grid coordinates.
4. transform those coordinates into geographic longitude/latitude.
5. expose the resulting geometry to MapLibre.
6. MapLibre renders the geometry in the Web Mercator map.

This preserves numerical contour correctness while aligning the result with standard web mapping.

---

# 11. Raster and Filled-Contour Projection Strategy

Filled shading may initially use either:

- filled contour polygons;
- image/raster overlay;
- map tiles.

The selected field should be transformed only at the visualization boundary.

For high-performance production rendering, a Web Mercator tile representation may be generated dynamically.

Conceptually:

```text
native field
    |
    v
field selection
    |
    v
rendering / reprojection
    |
    v
EPSG:3857 tile
    |
    v
MapLibre raster layer
```

No persistent duplicate forecast archive is required.

---

# 12. High-Level System Architecture

```text
                       +--------------------+
                       | Forecast System    |
                       +---------+----------+
                                 |
                                 v
                            GRIB2 files
                                 |
                                 v
                    +------------------------+
                    | Existing Kerchunk      |
                    | backend / references   |
                    +-----------+------------+
                                |
                                v
                    +------------------------+
                    | Forecast Data Layer    |
                    | native model grid      |
                    +-----------+------------+
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
     Contour Service      Render Service       Point Query
             |                  |                  |
          GeoJSON /          raster /             JSON
             MVT             tile
             |                  |                  |
             +------------------+------------------+
                                |
                                v
                    +------------------------+
                    | React + MapLibre GL    |
                    | Web Mercator display   |
                    +------------------------+
```

---

# 13. Frontend Technology

Recommended frontend stack:

```text
React
TypeScript
MapLibre GL JS
Vite
```

A large application-state framework should not be introduced initially unless needed.

React context, hooks, and URL state should be sufficient for the first version.

---

# 14. Backend Technology

Recommended backend:

```text
Python
existing Kerchunk implementation
xarray-compatible access
FastAPI or equivalent lightweight API framework
```

The existing working data-access code should be reused rather than rewritten.

Backend concerns should be separated into:

```text
data access
metadata
projection
contours
rendering
point queries
caching
API
```

---

# 15. Desktop Interface

The desktop application should resemble an operational forecasting workstation.

Primary layout:

```text
+--------------------------------------------------------------------+
| Air Composition Forecast Viewer                                    |
+--------------------------------------------------------------------+
| Date | Run | Species | Level | Render | Interval | Map | Layers   |
+--------------------------------------------------------------------+
| Init: 2026-08-19 18Z    F012             Valid: 2026-08-20 06Z    |
+--------------------------------------------------------------------+
|           |                                            |           |
| Layers    |                                            | Inspector |
| Legend    |                 MAP                        |           |
|           |                                            |           |
|           |                                            |           |
|           |                                            |           |
+-----------+--------------------------------------------+-----------+
| |<   <   Play/Pause   >   >|   F00 ----- F12 ----- F48            |
+--------------------------------------------------------------------+
```

The map should remain the dominant visual element.

---

# 16. Geographic Basemap

The viewer should use a real geographic basemap.

The forecast layer should never appear over an abstract or schematic geographic surface in the production application.

Default geographic context should include:

- continents;
- coastlines;
- oceans;
- national borders;
- state/province boundaries;
- major lakes;
- major cities.

Optional layers may include:

- county boundaries;
- roads;
- terrain;
- monitoring stations.

---

# 17. Map Style

Initial map styles should include at least:

```text
Dark Forecast
Light Forecast
```

The dark style should be optimized for colorful forecast fields and operational use.

The light style can be useful for printing, screenshots, and certain contour products.

Forecast styling must remain independent of the basemap provider.

---

# 18. Map Layer Stack

Recommended default layer order:

```text
base land/ocean
roads/background features
state/province boundaries
major lakes
filled forecast contours
forecast isolines
contour labels
administrative boundaries emphasized above shading
major cities
point-selection marker
optional observation layers
```

Exact ordering may vary by field.

Administrative boundaries must remain visible over forecast shading.

---

# 19. Product Selector

A top-level product selector should exist from the beginning.

Initial state:

```text
Product:
Air Composition
```

Future state:

```text
Product:
Air Composition
Meteorology
```

Meteorology may initially appear disabled or simply be absent until implemented.

---

# 20. Date Selection

The interface should provide a forecast-date selector.

Only dates with available forecast output should ideally be enabled.

Convenient neighboring-date controls should also exist:

```text
< Previous Date

Next Date >
```

Changing the date should trigger discovery of available runs.

---

# 21. Run Selection

Examples:

```text
00Z
06Z
12Z
18Z
```

Only actual available runs should appear.

Changing the run should update:

- forecast hours;
- valid times;
- variables;
- levels;
- product availability.

---

# 22. Variable / Species Selection

Variables should be metadata-driven and grouped logically.

Example:

```text
Particulate Matter
    PM2.5
    PM10

Gases
    Ozone
    NO2
    CO
    SO2

Aerosols
    AOD
    Smoke
    Dust
```

The actual list is determined by the forecast dataset.

---

# 23. Vertical Level Selection

Level selection should only appear when relevant.

Examples:

```text
Surface
1000 mb
925 mb
850 mb
700 mb
500 mb
Model Level 5
```

For surface-only fields, the level selector may be disabled or hidden.

---

# 24. Rendering Modes

The primary rendering modes are:

```text
Filled + Contours
Contours
Filled
```

Air-composition fields should typically default to:

```text
Filled + Contours
```

Meteorological fields may define different defaults.

---

# 25. Contour Maps

DESI-like contour visualization is a central requirement.

Contour behavior must support:

- variable contour intervals;
- major contours;
- minor contours;
- contour labels;
- optional filled shading;
- dynamically selected variables;
- dynamically selected levels.

Contour generation should operate on the native scientific field.

---

# 26. Isoline Geometry

GeoJSON is acceptable for initial development.

Possible production progression:

```text
native field
   |
contour generation
   |
GeoJSON
   |
MapLibre line layer
```

If geometry becomes too large:

```text
native field
   |
contour generation
   |
vector tile generation
   |
MVT
   |
MapLibre vector layer
```

Do not introduce vector tiles before measuring whether GeoJSON is insufficient.

---

# 27. Filled Contours

Air-composition fields should normally use discrete filled ranges rather than generic continuous heatmaps.

Example PM2.5-style bins:

```text
0–5
5–10
10–20
20–35
35–50
50+
```

These are illustrative only.

Actual levels should be field configuration.

---

# 28. Variable Rendering Configuration

Field visualization should be metadata-driven.

Example:

```yaml
id: PM25
label: PM2.5
category: Particulate Matter
units: ug m-3

rendering:
  default_mode: both
  contour_interval: 5
  major_contour_interval: 20
  labels: true

display:
  decimals: 1
```

Future meteorological example:

```yaml
id: HGT500
label: 500 mb Geopotential Height
units: m

rendering:
  default_mode: contours
  contour_interval: 60
  major_contour_interval: 120
  labels: true
```

React components should not contain field-specific scientific logic.

---

# 29. Contour Labels

Contour labels should:

- display the contour value;
- follow contour lines when practical;
- remain readable over shaded backgrounds;
- avoid excessive repetition;
- adjust density with zoom;
- optionally be disabled.

Major contours should receive labeling priority.

---

# 30. Legend

The legend should remain visible on desktop.

It should display:

- variable name;
- units;
- filled contour ranges;
- major thresholds if relevant;
- contour interval when appropriate.

The legend should update immediately when the selected variable changes.

---

# 31. Forecast Time Model

The application must explicitly distinguish:

```text
Initialization time
Forecast hour
Valid time
```

Example:

```text
Initialized:
2026-08-19 18Z

Forecast Hour:
F012

Valid:
2026-08-20 06Z
```

The user should never need to calculate valid time manually.

---

# 32. Forecast Timeline

Timeline controls should be persistent on desktop.

Desired controls:

```text
First
Previous
Play/Pause
Next
Last
Forecast-hour slider
```

Example:

```text
|<   <   ▶   >   >|

F00 ------ F06 ------ F12 ------ F24 ------ F48
                      ^
```

Only available forecast hours should be selectable.

---

# 33. Animation

Animation should step through available forecast fields.

The frontend should prefetch neighboring frames.

Example:

```text
Current:
F12

Prepared:
F10
F11
F12
F13
F14
```

During playback:

- the current map should remain visible until the next frame is ready;
- stale requests must not overwrite newer selections;
- playback should pause immediately on request;
- rendering should avoid flicker where practical.

---

# 34. Point Inspection

Clicking a location should retrieve the field value at that point.

Display:

```text
Latitude
Longitude
Variable
Value
Units
Level
Valid time
```

Example:

```text
Columbus, OH

39.96°N, 83.00°W

PM2.5
42.6 ug m-3

Surface

Valid:
2026-08-20 06Z
```

Nearest-gridpoint lookup is sufficient initially.

Interpolation may be added later.

---

# 35. Future Point Time Series

A future inspector panel may display a full forecast time series for the selected point.

Example:

```text
PM2.5

F00     8.2
F03    10.7
F06    14.9
F09    21.3
F12    28.4
F18    34.1
```

This should be built on a generic API usable by future meteorological fields.

---

# 36. Future Vertical Profiles

For vertically resolved air-composition fields:

```text
concentration
versus
altitude / pressure / model level
```

may be displayed in the inspector.

The same framework can later support meteorological profiles and sounding-like views.

---

# 37. Metadata API

The frontend needs metadata endpoints for discovery.

Suggested endpoints:

```http
GET /api/health
GET /api/catalog
GET /api/dates
GET /api/runs
GET /api/variables
GET /api/levels
GET /api/times
```

---

# 38. Contour API

Conceptually:

```http
GET /api/contours
    ?date=2026-08-19
    &run=18Z
    &variable=PM25
    &level=surface
    &forecastHour=12
    &interval=5
```

Initial output may be GeoJSON.

---

# 39. Filled-Field API

Possible interface:

```http
GET /api/tiles/{z}/{x}/{y}
    ?date=2026-08-19
    &run=18Z
    &variable=PM25
    &level=surface
    &forecastHour=12
```

The backend may initially use a simpler whole-field overlay if performance is acceptable.

Tile rendering should be introduced based on measured needs.

---

# 40. Point API

```http
GET /api/point
    ?lat=39.96
    &lon=-83.00
    &date=2026-08-19
    &run=18Z
    &variable=PM25
    &level=surface
    &forecastHour=12
```

Example:

```json
{
  "latitude": 39.96,
  "longitude": -83.00,
  "value": 42.6,
  "units": "ug m-3",
  "forecastHour": 12,
  "validTime": "2026-08-20T06:00:00Z"
}
```

---

# 41. URL State

Meaningful viewer state should be reflected in the URL.

Example:

```text
/view
?product=air
&date=2026-08-19
&run=18
&variable=PM25
&level=surface
&fhr=12
&render=both
```

Reloading or sharing this URL should recreate the same view whenever the referenced forecast remains available.

---

# 42. Caching

Several levels of caching can improve performance.

Potential cache layers:

```text
browser cache
frontend neighboring-frame cache
HTTP cache
backend dataset cache
contour geometry cache
rendered tile cache
```

Contour cache key:

```text
dataset
initialization
variable
level
forecast hour
contour interval
major interval
```

Avoid external cache infrastructure initially unless measurements justify it.

---

# 43. Performance Targets

Initial engineering targets:

```text
application shell:
near immediate

metadata queries:
< 500 ms when cached

first forecast field:
target < 2 seconds

cached frame change:
target < 250 ms

map pan/zoom:
no unnecessary scientific-data rereads

animation:
smooth after nearby frames are prepared
```

These are targets, not contractual requirements.

Performance should be measured rather than assumed.

---

# 44. Backend Performance Instrumentation

Record timing for:

```text
dataset open
Kerchunk lookup
field selection
data read
coordinate transformation
contour generation
reprojection
serialization
total request time
```

Structured logging should make bottlenecks obvious.

---

# 45. Repository Structure

Suggested structure:

```text
forecast-viewer/
|
+-- frontend/
|   +-- src/
|       +-- components/
|       +-- controls/
|       +-- map/
|       +-- api/
|       +-- hooks/
|       +-- config/
|       +-- types/
|
+-- backend/
|   +-- app/
|       +-- api/
|       +-- data/
|       +-- projections/
|       +-- contours/
|       +-- rendering/
|       +-- point_query/
|       +-- cache/
|       +-- config/
|
+-- tests/
|
+-- docs/
|
+-- README.md
```

Existing repository organization should be preserved where practical.

---

# 46. Backend Modules

Conceptual backend modules:

```text
catalog
dataset
field_selector
coordinates
projection
contours
tiles
point_query
cache
configuration
```

Scientific data access should remain separate from presentation rendering.

---

# 47. Frontend Components

Potential React components:

```text
ForecastViewer
ForecastMap
ForecastLayer
ContourLayer

ProductSelector
DateSelector
RunSelector
VariableSelector
LevelSelector
RenderingSelector
ContourIntervalSelector

ForecastTimeline
PlaybackControls

Legend
LayerPanel
MapInspector
MapStyleSelector
```

Components should remain small and composable.

---

# 48. Viewer State

Example:

```typescript
interface ViewerState {
  product: 'air' | 'meteorology';

  date: string;
  run: string;

  variable: string;
  level?: string;

  forecastHour: number;

  rendering: {
    mode: 'filled' | 'contours' | 'both';
    contourInterval?: number;
    contourLabels: boolean;
    majorContours: boolean;
  };

  map: {
    style: 'dark' | 'light';
    showStates: boolean;
    showCounties: boolean;
    showCities: boolean;
  };
}
```

The meaningful subset of this state should synchronize with the URL.

---

# 49. Error Handling

The application must handle:

- missing forecast files;
- incomplete runs;
- unavailable forecast hours;
- unavailable variables;
- unavailable levels;
- corrupt GRIB2;
- invalid Kerchunk references;
- failed field reads;
- coordinate-transform failures;
- contour-generation failures;
- reprojection failures;
- tile-generation failures;
- network errors.

The map should not silently become blank.

Useful errors should appear in the interface.

---

# 50. Scientific Validation

Projection and orientation errors are a significant risk.

The development process should explicitly validate:

- latitude orientation;
- longitude convention;
- grid orientation;
- scanning order;
- native model projection;
- map extent;
- contour placement;
- point-query values.

A known field should be rendered independently in Python and compared against the web application during early development.

---

# 51. Verification Utilities

Create small development utilities to display:

```text
field dimensions
minimum
maximum
mean
coordinate extents
projection metadata
selected grid-point values
```

The project should also provide a simple reference plot outside MapLibre.

This helps detect incorrect:

- orientation;
- reprojection;
- indexing;
- contour values.

---

# 52. Testing Strategy

## Backend

Test:

- dataset opening;
- metadata discovery;
- date/run discovery;
- variable discovery;
- level discovery;
- forecast-hour discovery;
- valid-time calculation;
- native-grid field extraction;
- coordinate conversion;
- contour generation;
- point lookup.

## Frontend

Test:

- dependent selectors;
- date/run changes;
- variable/level changes;
- timeline changes;
- playback;
- URL state.

## Integration

Given a known test forecast:

1. Open the GRIB2 through Kerchunk.
2. Select a real air-composition field.
3. Validate the native field.
4. Generate contours.
5. convert geometry correctly.
6. return it through the API.
7. render it over a real basemap.
8. query a known point.
9. confirm the web value matches the source field.

---

# 53. Development Milestones

## Milestone 1 — Application Skeleton

Deliver:

- React;
- TypeScript;
- MapLibre;
- real basemap;
- Python API;
- `/api/health`;
- documented development startup.

Success:

The map loads and frontend/backend communication works.

---

## Milestone 2 — Existing Kerchunk Integration

Inspect and integrate the existing Kerchunk backend.

Expose:

- dates;
- runs;
- variables;
- levels;
- forecast hours;
- valid times.

Success:

Frontend selectors populate from real forecast metadata.

---

## Milestone 3 — One Real Air-Composition Field

Select one real field.

Read it through Kerchunk.

Verify:

- shape;
- min/max;
- coordinates;
- projection;
- orientation.

Success:

A numerically verified field can be accessed reliably.

---

## Milestone 4 — Geographic Alignment

Transform the model grid correctly for presentation.

Success:

Known model features and coordinate points line up correctly with the Web Mercator basemap.

Do not proceed with extensive styling until this is verified.

---

## Milestone 5 — Contour Lines

Generate real isolines.

Return GeoJSON.

Display using MapLibre line layers.

Success:

Contour positions and values match an independent reference plot.

---

## Milestone 6 — Filled Contours

Add filled visualization.

Support:

```text
Contours
Filled
Filled + Contours
```

Success:

A DESI-like air-composition product is displayed over the real basemap.

---

## Milestone 7 — Forecast Navigation

Implement:

- date;
- run;
- forecast hour;
- valid time;
- previous/next;
- first/last.

Success:

A forecaster can navigate a full model run.

---

## Milestone 8 — Animation

Add:

- play;
- pause;
- neighboring-frame prefetch;
- stale-request protection.

Success:

Forecast evolution can be viewed smoothly.

---

## Milestone 9 — Point Inspection

Clicking the map returns the correct field value.

Success:

The retrieved value matches the source field at the selected location.

---

## Milestone 10 — URL State

Persist:

- date;
- run;
- variable;
- level;
- forecast hour;
- rendering mode.

Success:

A copied URL recreates the same forecast view.

---

## Milestone 11 — Desktop UI Polish

Make the application visually comparable to the approved concept:

- dark forecast basemap;
- real geographic context;
- persistent legend;
- layer controls;
- point inspector;
- compact top toolbar;
- bottom timeline;
- DESI-like contours.

---

## Milestone 12 — Performance Optimization

Only after measuring:

- field-read latency;
- contour complexity;
- rendering time;
- animation behavior.

Potential improvements:

- geometry simplification;
- vector tiles;
- dynamic raster tiles;
- field caching;
- contour caching;
- request cancellation;
- HTTP caching;
- forecast-frame prefetch.

---

# 54. MVP Definition

Version 1 is complete when a user can:

1. Open the application.
2. See a real geographic MapLibre basemap.
3. Select an available forecast date.
4. Select a forecast run.
5. Select an air-composition species.
6. Select a level when applicable.
7. Select a forecast hour.
8. See initialization time.
9. See valid time.
10. Display the field as filled contours.
11. Display isolines.
12. Display contour labels.
13. Zoom and pan geographically.
14. Toggle major geographic overlays.
15. Animate forecast hours.
16. Click a location and retrieve its forecast value.
17. Copy a URL that reproduces the view.

---

# 55. Non-Goals for Version 1

Do not prioritize:

- ensembles;
- ensemble statistics;
- full observation verification;
- forecasting model execution;
- user accounts;
- collaborative workspaces;
- mobile-specific UI;
- tablet-specific UI;
- Kubernetes;
- distributed job queues;
- external database infrastructure unless required;
- comprehensive meteorological products.

---

# 56. Key Technical Decisions

The project should begin with these decisions considered fixed unless testing demonstrates a reason to change them.

### Data

```text
GRIB2 remains authoritative storage.
```

### Data access

```text
Use the existing Kerchunk backend.
```

### Scientific processing

```text
Operate on the native model grid/projection.
```

### Web-map presentation

```text
Use EPSG:3857 / Web Mercator.
```

### Map

```text
MapLibre GL JS.
```

### Frontend

```text
React + TypeScript.
```

### Initial contour transport

```text
GeoJSON.
```

### Production contour optimization

```text
Consider MVT only when necessary.
```

### Primary UX

```text
Desktop forecasting workstation.
```

### Initial domain

```text
Air Composition.
```

### Second domain

```text
Meteorology.
```

---

# 57. Final Architectural Rule

The most important boundary in the system is:

```text
Scientific world                     Presentation world

Native GRIB2/model grid              Web Mercator
Kerchunk                             MapLibre
native projection          --->      EPSG:3857
scientific values                    visualization
field calculations                   map styling
contour determination                geographic display
```

Do not blur this boundary.

The web application may display everything in Web Mercator, but the underlying forecast science should remain tied to the native model data and projection.

That separation gives the application the combination we want:

**scientifically correct forecast handling underneath and a fast, familiar, DESI-like web-map experience on top.**
