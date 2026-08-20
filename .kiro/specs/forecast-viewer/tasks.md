# Air Composition Forecast Viewer — Implementation Tasks

Reference: #[[file:docs/Air Composition Forecast Viewer — Revised Design Document.md]]

---

## Milestone 1 — Application Skeleton

### Task 1.1: Initialize Frontend Project
- [x] Create `frontend/` directory with Vite + React + TypeScript scaffold
- [x] Install dependencies: react, react-dom, maplibre-gl, typescript
- [x] Configure Vite with proxy to backend API (dev server)
- [x] Create basic `App.tsx` entry point
- [x] Verify `npm run dev` starts successfully

**Requirements:** FR-1
**Design ref:** Section 5 (Frontend Architecture)

---

### Task 1.2: Initialize Backend Project
- [x] Create `backend/app/` directory structure per design
- [x] Create `backend/app/main.py` with FastAPI app instance
- [x] Add CORS middleware for frontend dev server
- [x] Implement `GET /api/health` returning `{ "status": "ok" }`
- [x] Create `backend/run.py` or uvicorn config for local dev
- [x] Verify `uvicorn` starts and health endpoint responds

**Requirements:** FR-19
**Design ref:** Section 4 (Backend Architecture)

---

### Task 1.3: MapLibre Basemap
- [x] Add MapLibre GL JS to frontend
- [x] Create `ForecastMap` component wrapping MapLibre instance
- [x] Load a free basemap style (e.g., MapTiler or self-hosted style)
- [x] Configure initial center and zoom for CONUS
- [x] Verify map renders with geographic features (coastlines, borders)

**Requirements:** FR-1
**Design ref:** Section 5.6 (Map Layer Stack)

---

### Task 1.4: Dark and Light Map Styles
- [x] Create or source a Dark Forecast style optimized for colorful overlays
- [x] Create or source a Light Forecast style for printing/screenshots
- [x] Add `MapStyleSelector` component to toggle between styles
- [x] Persist style choice in viewer state

**Requirements:** FR-1
**Design ref:** Section 5.1 (Component Hierarchy)

---

### Task 1.5: Basic Desktop Layout Shell
- [x] Implement top toolbar container
- [x] Implement time display bar (placeholder content)
- [x] Implement left panel (legend placeholder)
- [x] Implement center map area (ForecastMap)
- [x] Implement right panel (inspector placeholder)
- [x] Implement bottom timeline bar (placeholder)
- [x] Verify layout matches design wireframe at 1920×1080

**Requirements:** NFR-8
**Design ref:** Section 8 (Desktop Layout Design)

---

### Task 1.6: Frontend ↔ Backend Communication
- [x] Create `frontend/src/api/client.ts` with base fetch wrapper
- [x] Call `/api/health` on app mount and display status
- [x] Verify end-to-end communication through Vite proxy

**Requirements:** FR-19
**Design ref:** Section 5.3 (Data Fetching)

---

## Milestone 2 — Kerchunk Integration & Metadata

### Task 2.1: Kerchunk Store Module
- [x] Create `backend/app/data/kerchunk_store.py`
- [x] Implement dataset discovery: find available Kerchunk references
- [x] Implement `open_dataset(date, run)` → xarray.Dataset (lazy)
- [x] Add LRU cache for open dataset handles
- [x] Add structured logging for dataset open timing

**Requirements:** FR-18
**Design ref:** Section 4.2 (Data Access Flow)

---

### Task 2.2: Metadata Discovery
- [x] Create `backend/app/data/field_selector.py`
- [x] Implement date discovery from available Kerchunk references
- [x] Implement run discovery for a given date
- [x] Implement variable discovery from dataset dimensions/variables
- [x] Implement level discovery for a given variable
- [x] Implement forecast-hour discovery and valid-time calculation

**Requirements:** FR-19, FR-2, FR-3, FR-4, FR-5
**Design ref:** Section 4.2, Section 7.1

---

### Task 2.3: Metadata API Endpoints
- [x] Implement `GET /api/catalog` — available products
- [x] Implement `GET /api/dates?product=air` — available dates
- [x] Implement `GET /api/runs?product=air&date=...` — available runs
- [x] Implement `GET /api/variables?product=air&date=...&run=...` — grouped variables
- [x] Implement `GET /api/levels?...&variable=...` — available levels
- [x] Implement `GET /api/times?...` — forecast hours and valid times
- [x] Add request validation via Pydantic models

**Requirements:** FR-19
**Design ref:** Section 7.1 (Metadata Endpoints)

---

### Task 2.4: Domain Configuration
- [x] Create `config/domains/air.yaml` with variable definitions
- [x] Implement config loader in `backend/app/config/`
- [x] Wire variable metadata (categories, labels, units, rendering) into API responses
- [x] Verify `/api/variables` returns grouped, labeled variables from config

**Requirements:** FR-4, NFR-10
**Design ref:** Section 6 (Domain Configuration)

---

### Task 2.5: Frontend Metadata Hooks
- [x] Create `useMetadata` hook to fetch dates/runs/variables/levels/times
- [x] Implement `DateSelector` component populated from API
- [x] Implement `RunSelector` component (dependent on date)
- [x] Implement `VariableSelector` component with category grouping
- [x] Implement `LevelSelector` component (conditional visibility)
- [x] Wire selectors to ViewerState context

**Requirements:** FR-2, FR-3, FR-4, FR-5
**Design ref:** Section 5.1, 5.3

---

## Milestone 3 — One Real Air-Composition Field

### Task 3.1: Field Extraction
- [x] Implement `field_selector.select(date, run, variable, level, fhr)` → numpy array
- [x] Extract coordinate arrays (lat, lon) from dataset
- [x] Extract projection/CRS metadata from GRIB2 attributes
- [x] Log field shape, min, max, mean on extraction

**Requirements:** FR-18, NFR-7
**Design ref:** Section 4.2

---

### Task 3.2: Verification Utilities
- [x] Create `backend/app/utils/field_stats.py` — print field diagnostics
- [x] Create `backend/app/utils/reference_plot.py` — matplotlib/cartopy plot
- [x] Create `backend/app/utils/grid_inspector.py` — coordinate extent/projection info
- [x] Verify one real field: correct shape, reasonable min/max, expected coordinate range

**Requirements:** NFR-13
**Design ref:** Section 10 (Verification & Validation Plan)

---

### Task 3.3: Coordinate System Module
- [x] Create `backend/app/projections/coordinates.py`
- [x] Implement grid-index → native CRS coordinate mapping
- [x] Create `backend/app/projections/transform.py`
- [x] Implement native CRS → geographic (lon/lat) transform via pyproj
- [x] Verify coordinate transforms against known reference points

**Requirements:** NFR-7
**Design ref:** Section 3 (Projection Pipeline)

---

## Milestone 4 — Geographic Alignment

### Task 4.1: Field-to-Map Alignment
- [x] Transform a known field's coordinate grid to lon/lat
- [x] Render as a simple GeoJSON bounding polygon on MapLibre
- [x] Verify geographic extent aligns with expected region
- [x] Check latitude orientation (N→S vs S→N) and longitude convention

**Requirements:** NFR-7, NFR-13
**Design ref:** Section 3 (Projection Pipeline)

---

### Task 4.2: Orientation Validation
- [x] Select a field with known spatial features (e.g., high values over a specific region)
- [x] Render a coarse representation on the map
- [x] Compare against reference matplotlib plot
- [x] Confirm no mirroring, rotation, or offset errors
- [x] Document validated scanning order and grid orientation

**Requirements:** NFR-13
**Design ref:** Section 10

---

## Milestone 5 — Contour Lines

### Task 5.1: Contour Generator
- [x] Create `backend/app/contours/generator.py`
- [x] Implement isoline generation using contourpy on the native grid
- [x] Support configurable contour interval and major interval
- [x] Return contour vertices with associated values

**Requirements:** FR-7
**Design ref:** Section 4.3 (Contour Generation Flow)

---

### Task 5.2: GeoJSON Serialization
- [x] Create `backend/app/contours/geojson.py`
- [x] Transform contour vertices from native grid → geographic coordinates
- [x] Serialize as GeoJSON FeatureCollection with `value` and `major` properties
- [x] Optimize serialization with orjson

**Requirements:** FR-7, FR-20
**Design ref:** Section 7.2, 7.3

---

### Task 5.3: Contour API Endpoint
- [x] Implement `GET /api/contours` with query parameters
- [x] Wire to contour generator and GeoJSON serializer
- [x] Add contour geometry cache (keyed on date/run/var/level/fhr/interval)
- [x] Add timing instrumentation
- [x] Add HTTP cache headers

**Requirements:** FR-20, NFR-11, NFR-12
**Design ref:** Section 7.2

---

### Task 5.4: Frontend Isoline Layer
- [x] Create `useContours` hook to fetch GeoJSON from `/api/contours`
- [x] Create `IsolineLayer` component using MapLibre line layer
- [x] Style major contours differently from minor contours
- [x] Verify contour placement matches reference plot

**Requirements:** FR-7
**Design ref:** Section 5.1, 5.6

---

### Task 5.5: Contour Labels
- [x] Create `ContourLabelLayer` component using MapLibre symbol layer
- [x] Place labels along contour lines with value text
- [x] Prioritize major contour labels
- [x] Adjust label density based on zoom level
- [x] Ensure readability over shaded backgrounds (halo/background)

**Requirements:** FR-8
**Design ref:** Section 5.1

---

## Milestone 6 — Filled Contours

### Task 6.1: Filled Contour Generator
- [x] Extend `generator.py` to produce filled contour polygons via contourpy
- [x] Use configured fill levels from domain config
- [x] Return polygons with value-range properties

**Requirements:** FR-6
**Design ref:** Section 3.2

---

### Task 6.2: Filled Contour API
- [x] Implement `GET /api/filled` endpoint
- [x] Return GeoJSON FeatureCollection of fill polygons with level ranges
- [x] Add caching and instrumentation

**Requirements:** FR-22, FR-6
**Design ref:** Section 7.2

---

### Task 6.3: Frontend Filled Layer
- [x] Create `FilledContourLayer` component using MapLibre fill layer
- [x] Apply color ramp from domain config / variable rendering settings
- [x] Support discrete color ranges (not continuous gradient)
- [x] Ensure correct layer ordering (filled below isolines)

**Requirements:** FR-6, FR-9
**Design ref:** Section 5.6

---

### Task 6.4: Rendering Mode Selector
- [x] Implement `RenderingSelector` component with three modes
- [x] Toggle visibility of IsolineLayer and FilledContourLayer based on mode
- [x] Default air-composition fields to "Filled + Contours"
- [x] Wire to ViewerState

**Requirements:** FR-9
**Design ref:** Section 5.1

---

### Task 6.5: Legend Component
- [x] Implement `Legend` component showing color ramp + value labels
- [x] Display variable name, units, fill ranges, contour interval
- [x] Update immediately on variable change
- [x] Position in left panel, always visible on desktop

**Requirements:** FR-15
**Design ref:** Section 8

---

## Milestone 7 — Forecast Navigation

### Task 7.1: ViewerState Context & Reducer
- [x] Create `ViewerContext` with full state interface
- [x] Implement reducer actions: setDate, setRun, setVariable, setLevel, setForecastHour, setRendering, setMap
- [x] Cascading updates: date change → refetch runs → reset run; run change → refetch variables, etc.

**Requirements:** FR-2, FR-3, FR-4, FR-5
**Design ref:** Section 5.2

---

### Task 7.2: Forecast Time Display
- [x] Implement `TimeDisplay` component
- [x] Show initialization time (date + run)
- [x] Show current forecast hour
- [x] Compute and show valid time
- [x] Update on any selection change

**Requirements:** FR-10
**Design ref:** Section 8

---

### Task 7.3: Timeline Controls
- [x] Implement `ForecastSlider` with available forecast hours
- [x] Implement `PlaybackControls` (First, Previous, Play/Pause, Next, Last buttons)
- [x] Only enable selectable forecast hours
- [x] Wire to ViewerState forecastHour

**Requirements:** FR-11
**Design ref:** Section 5.1

---

### Task 7.4: Product Selector
- [x] Implement `ProductSelector` component
- [x] Show "Air Composition" as available product
- [x] Placeholder for future "Meteorology" (disabled or hidden)

**Requirements:** FR-16
**Design ref:** Section 5.1

---

## Milestone 8 — Animation

### Task 8.1: Animation Controller
- [x] Implement animation engine (frame buffer, interval timer, sequence tagging)
- [x] Prefetch neighboring frames (fhr ± N)
- [x] Stale-request protection: ignore out-of-order responses
- [x] Play/pause toggling
- [x] Configurable playback speed

**Requirements:** FR-12
**Design ref:** Section 5.5 (Animation Engine)

---

### Task 8.2: Frame Transition
- [x] Keep current map visible until next frame is ready
- [x] Swap layers atomically to avoid flicker
- [x] Cancel in-flight requests on pause or manual navigation
- [x] Handle missing frames gracefully (skip, don't stall)

**Requirements:** FR-12, NFR-6
**Design ref:** Section 5.5

---

## Milestone 9 — Point Inspection

### Task 9.1: Point Query Backend
- [x] Create `backend/app/point_query/nearest.py`
- [x] Implement nearest-gridpoint lookup given (lat, lon) and field coordinates
- [x] Extract value at nearest grid point
- [x] Implement `GET /api/point` endpoint with full response

**Requirements:** FR-13, FR-21
**Design ref:** Section 4.4, Section 7.2

---

### Task 9.2: Frontend Point Inspector
- [x] Create `MapInspector` component in right panel
- [x] Add click handler on map to capture lat/lon
- [x] Call `/api/point` with current viewer state + clicked coordinates
- [x] Display: lat, lon, variable, value, units, level, valid time
- [x] Show point marker on map at clicked location

**Requirements:** FR-13
**Design ref:** Section 5.1, Section 8

---

## Milestone 10 — URL State

### Task 10.1: URL Synchronization Hook
- [x] Create `useUrlState` hook
- [x] On mount: parse URL query params → initialize ViewerState
- [x] On state change: update URL params via `replaceState`
- [x] Encode: product, date, run, variable, level, fhr, render mode
- [x] Do not encode transient state (map viewport, inspector)

**Requirements:** FR-14
**Design ref:** Section 5.4

---

### Task 10.2: Deep Link Validation
- [x] On load with URL params: validate against available data
- [x] If referenced data no longer available: fall back to defaults, show notice
- [x] Verify sharing a URL produces the same view in another browser

**Requirements:** FR-14
**Design ref:** Section 5.4

---

## Milestone 11 — Desktop UI Polish

### Task 11.1: Layer Controls Panel
- [x] Implement `LayerPanel` component
- [x] Toggle: state boundaries, county boundaries, cities, roads, terrain
- [x] Wire toggles to map layer visibility
- [x] Persist in ViewerState

**Requirements:** FR-17
**Design ref:** Section 5.1

---

### Task 11.2: Contour Interval Selector
- [x] Implement `ContourIntervalSelector` component
- [x] Allow user to override default contour interval for current variable
- [x] Trigger contour refetch on change

**Requirements:** FR-7, FR-9
**Design ref:** Section 5.1

---

### Task 11.3: Visual Polish
- [x] Refine toolbar spacing and alignment
- [x] Ensure legend is readable at all supported resolutions
- [x] Verify layout at 1440×900, 1920×1080, 2560×1440
- [x] Dark theme consistency across all panels
- [x] Ensure forecast contours have DESI-like visual quality

**Requirements:** NFR-8
**Design ref:** Section 8

---

### Task 11.4: Error UI
- [x] Add non-blocking notification area for API errors
- [x] Show "data unavailable" state in selectors when data is missing
- [x] Show connection status indicator
- [x] Never silently blank the map

**Requirements:** NFR-9
**Design ref:** Section 9 (Error Handling Strategy)

---

## Milestone 12 — Performance Optimization

### Task 12.1: Measure Baseline Performance
- [x] Instrument and record: field-read latency, contour generation time, serialization time
- [x] Measure frontend render time for contour GeoJSON
- [x] Measure animation smoothness (frame intervals)
- [x] Document baseline against performance targets (NFR-1 through NFR-6)

**Requirements:** NFR-1, NFR-2, NFR-3, NFR-4, NFR-5, NFR-6, NFR-11
**Design ref:** Section 4.6

---

### Task 12.2: Optimize Based on Measurements
- [x] If GeoJSON too large: implement geometry simplification or switch to MVT
- [x] If contour generation slow: add/tune contour cache
- [x] If field reads slow: optimize Kerchunk reference caching
- [x] If animation janky: increase prefetch buffer, optimize layer swaps
- [x] Add HTTP cache headers for immutable forecast data
- [x] Implement request cancellation for superseded requests

**Requirements:** NFR-12, NFR-6
**Design ref:** Section 4.5 (Caching Strategy)

---

### Task 12.3: Frontend Prefetch Optimization
- [x] Implement `usePrefetch` hook for neighboring forecast hours
- [x] Cache fetched GeoJSON in memory for quick frame switching
- [x] Evict distant frames from cache to manage memory

**Requirements:** NFR-4, NFR-6, FR-12
**Design ref:** Section 5.3, 5.5
