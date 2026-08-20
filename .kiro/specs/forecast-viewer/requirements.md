# Air Composition Forecast Viewer — Requirements

Reference: #[[file:docs/Air Composition Forecast Viewer — Revised Design Document.md]]

---

## Functional Requirements

### FR-1: Geographic Map Display

The application shall display forecast data over a real geographic basemap using MapLibre GL JS with Web Mercator (EPSG:3857) projection.

**Acceptance Criteria:**
- A MapLibre map loads with continents, coastlines, oceans, national borders, state/province boundaries, major lakes, and major cities visible.
- At least two map styles are available: Dark Forecast and Light Forecast.
- The map remains the dominant visual element in the layout.
- Administrative boundaries remain visible over forecast shading.

---

### FR-2: Forecast Date Selection

The application shall provide a date selector that shows available forecast dates.

**Acceptance Criteria:**
- Only dates with available forecast output are enabled.
- Previous/Next date controls allow quick navigation.
- Changing the date triggers discovery of available runs for that date.

---

### FR-3: Forecast Run Selection

The application shall allow selection of forecast initialization runs (e.g., 00Z, 06Z, 12Z, 18Z).

**Acceptance Criteria:**
- Only actually available runs appear in the selector.
- Changing the run updates forecast hours, valid times, variables, levels, and product availability.

---

### FR-4: Variable / Species Selection

The application shall provide a metadata-driven variable selector grouped by category.

**Acceptance Criteria:**
- Variables are grouped logically (Particulate Matter, Gases, Aerosols, Tracers/Diagnostics).
- The actual variable list is derived from the dataset and domain configuration, not hardcoded.
- Changing the variable updates the legend, rendering configuration, and displayed field.

---

### FR-5: Vertical Level Selection

The application shall provide level selection when the selected variable has multiple levels.

**Acceptance Criteria:**
- Level selector appears only when the variable has multiple levels.
- For surface-only fields, the level selector is hidden or disabled.
- Available levels are derived from the dataset metadata.

---

### FR-6: Filled Contour Visualization

The application shall render filled contour maps with discrete color ranges.

**Acceptance Criteria:**
- Fields display as discrete filled ranges (not continuous heatmaps).
- Color ranges and intervals are driven by variable rendering configuration.
- Filled contours align correctly with the geographic basemap.

---

### FR-7: Isoline Visualization

The application shall generate and display contour isolines over the map.

**Acceptance Criteria:**
- Isolines are generated from the native scientific field (not reprojected data).
- Variable contour intervals, major/minor contours are supported.
- Contour positions match an independent reference computation.

---

### FR-8: Contour Labels

The application shall display labels on contour lines showing field values.

**Acceptance Criteria:**
- Labels display the contour value.
- Labels are readable over shaded backgrounds.
- Major contours receive labeling priority.
- Label density adjusts with zoom level.
- Labels can be toggled on/off.

---

### FR-9: Rendering Mode Selection

The application shall support multiple rendering modes.

**Acceptance Criteria:**
- Three modes are available: Filled + Contours, Contours only, Filled only.
- Air-composition fields default to Filled + Contours.
- Mode can be changed without reloading the page.

---

### FR-10: Forecast Time Display

The application shall explicitly display initialization time, forecast hour, and valid time.

**Acceptance Criteria:**
- Initialization time (e.g., "2026-08-19 18Z") is always visible.
- Current forecast hour (e.g., "F012") is always visible.
- Valid time (e.g., "2026-08-20 06Z") is always visible and correctly computed.
- The user never needs to calculate valid time manually.

---

### FR-11: Forecast Timeline Navigation

The application shall provide persistent timeline controls for stepping through forecast hours.

**Acceptance Criteria:**
- Controls include: First, Previous, Play/Pause, Next, Last.
- A forecast-hour slider is available.
- Only available forecast hours are selectable.
- Controls are always visible on desktop.

---

### FR-12: Animation Playback

The application shall animate through forecast hours smoothly.

**Acceptance Criteria:**
- Playback steps through available forecast fields sequentially.
- Neighboring frames are prefetched during playback.
- The current map remains visible until the next frame is ready (no flicker).
- Stale requests do not overwrite newer selections.
- Playback pauses immediately on user request.

---

### FR-13: Point Inspection

The application shall allow clicking the map to retrieve the forecast value at that location.

**Acceptance Criteria:**
- Clicking displays: latitude, longitude, variable name, value, units, level, and valid time.
- The value is retrieved via nearest-gridpoint lookup.
- The retrieved value matches the source field at the selected location.

---

### FR-14: URL State Persistence

The application shall encode meaningful viewer state in the URL.

**Acceptance Criteria:**
- URL encodes: product, date, run, variable, level, forecast hour, rendering mode.
- Reloading the URL recreates the same view (when data is still available).
- Sharing the URL with another user produces the same view.

---

### FR-15: Legend Display

The application shall display a persistent, visible legend.

**Acceptance Criteria:**
- Legend shows: variable name, units, filled contour ranges, major thresholds, contour interval.
- Legend updates immediately when the selected variable changes.
- Legend remains visible on desktop without requiring interaction to reveal.

---

### FR-16: Product Selector

The application shall include a top-level product selector.

**Acceptance Criteria:**
- "Air Composition" is available as the initial product.
- The selector is present from the beginning to support future domain additions (Meteorology).

---

### FR-17: Layer Controls

The application shall provide controls to toggle geographic overlay layers.

**Acceptance Criteria:**
- Users can toggle state/province boundaries, county boundaries, cities, roads, terrain, and other optional layers.
- Forecast layer remains correctly composited with toggled layers.

---

### FR-18: Kerchunk Data Access

The backend shall access GRIB2 forecast data through the existing Kerchunk implementation.

**Acceptance Criteria:**
- GRIB2 remains the authoritative storage format — no permanent format conversion required.
- Lazy/chunked reading is preserved; the backend does not load complete model runs for single-field requests.
- The existing Kerchunk code is reused, not rewritten.

---

### FR-19: Metadata API

The backend shall expose metadata endpoints for frontend discovery.

**Acceptance Criteria:**
- Endpoints exist for: health, catalog, dates, runs, variables, levels, and forecast times.
- Responses reflect actual data availability.
- Frontend selectors populate from these endpoints.

---

### FR-20: Contour API

The backend shall expose an endpoint that returns contour geometry for a specified field.

**Acceptance Criteria:**
- Accepts parameters: date, run, variable, level, forecast hour, contour interval.
- Returns GeoJSON geometry (initial implementation).
- Contours are generated from the native scientific grid, then coordinates are transformed to geographic (lon/lat).

---

### FR-21: Point Query API

The backend shall expose a point-query endpoint.

**Acceptance Criteria:**
- Accepts: lat, lon, date, run, variable, level, forecast hour.
- Returns: latitude, longitude, value, units, forecast hour, valid time.
- Nearest-gridpoint lookup is used.

---

### FR-22: Filled Field / Tile API

The backend shall expose an endpoint for filled-field rendering data.

**Acceptance Criteria:**
- Supports either a whole-field overlay or tile-based rendering ({z}/{x}/{y}).
- The initial implementation may use a simpler whole-field approach.
- Tile-based rendering is introduced only when performance measurements require it.

---

## Non-Functional Requirements

### NFR-1: Performance — Application Shell

The application shell (UI chrome, map initialization) shall load near-immediately.

---

### NFR-2: Performance — Metadata Queries

Metadata queries shall return in < 500 ms when cached.

---

### NFR-3: Performance — First Forecast Field

The first forecast field shall render in < 2 seconds (target).

---

### NFR-4: Performance — Cached Frame Change

Changing to a cached forecast frame shall complete in < 250 ms (target).

---

### NFR-5: Performance — Map Interaction

Map pan and zoom shall not trigger unnecessary scientific data re-reads.

---

### NFR-6: Performance — Animation

Animation shall appear smooth once neighboring frames are prepared.

---

### NFR-7: Scientific Correctness

All scientific data processing (values, thresholds, statistics, interpolation, contour determination) shall operate on the native model grid and projection. Web Mercator is used only for the presentation layer.

---

### NFR-8: Desktop-First Design

The interface shall be optimized for desktop displays (1440×900 through 4K) with persistent controls, large map area, visible legends, and minimal hidden menus. Mobile/tablet optimization is not a primary goal.

---

### NFR-9: Error Resilience

The application shall handle missing files, incomplete runs, unavailable fields, corrupt data, and network errors gracefully — the map shall never silently go blank. Useful error messages shall appear in the interface.

---

### NFR-10: Extensibility

The architecture shall support adding new domains (Meteorology) and new variables without rewriting core components. Domain-specific behavior shall reside in metadata and configuration.

---

### NFR-11: Backend Instrumentation

The backend shall record structured timing for: dataset open, Kerchunk lookup, field selection, data read, coordinate transformation, contour generation, reprojection, serialization, and total request time.

---

### NFR-12: Caching Strategy

The system shall support multiple cache layers (browser, frontend frame cache, HTTP cache, backend dataset cache, contour geometry cache, rendered tile cache) without requiring external cache infrastructure initially.

---

### NFR-13: Scientific Validation

The development process shall validate latitude orientation, longitude convention, grid orientation, scanning order, native model projection, map extent, contour placement, and point-query values against independent reference computations.
