# Performance Targets

This document defines the performance targets for the Air Composition Forecast Viewer, based on the non-functional requirements (NFR-1 through NFR-6).

---

## Targets

| ID | Metric | Target | Notes |
|----|--------|--------|-------|
| NFR-1 | Application shell load | Near-immediate | UI chrome, map init, basemap tiles |
| NFR-2 | Metadata queries (cached) | < 500 ms | /api/dates, /api/variables, etc. |
| NFR-3 | First forecast field render | < 2 s | End-to-end: field read + contour gen + serialize + network + render |
| NFR-4 | Cached frame change | < 250 ms | Switching to a prefetched/cached frame |
| NFR-5 | Map interaction latency | No re-read | Pan/zoom must not trigger scientific data re-reads |
| NFR-6 | Animation smoothness | Smooth playback | No flicker; current frame visible until next is ready |

---

## Backend Timing Instrumentation

The backend already records structured timing for each request stage via `structlog`:

- `timing_field_ms` — Kerchunk field read and extraction
- `timing_contour_ms` — contourpy isoline/fill generation
- `timing_transform_ms` — coordinate transform (native → lon/lat)
- `timing_serialize_ms` — GeoJSON assembly and metadata
- `timing_total_ms` — end-to-end request time

These metrics are logged for every `/api/contours` and `/api/filled` request.

---

## Optimizations Already in Place

| Optimization | Location | Status |
|---|---|---|
| Backend contour geometry cache (LRU, keyed on field+interval) | `backend/app/api/contours.py` | Done |
| Backend filled geometry cache | `backend/app/api/filled.py` | Done |
| HTTP Cache-Control headers (`public, max-age=3600, immutable`) | Both contour and filled endpoints | Done |
| Request cancellation via AbortController | `useContours.ts`, `useFilled.ts` | Done |
| Dataset handle LRU cache | `backend/app/data/kerchunk_store.py` | Done |
| Animation stale-request protection (sequence tagging) | `useAnimation.ts` | Done |
| Frame prefetch for neighboring fhr (±1) | `usePrefetch.ts` | Done |
| In-memory GeoJSON LRU cache (10 entries) | `useGeoJsonCache.ts` | Done |
| Prefetch cache eviction (±3 distance) | `usePrefetch.ts` | Done |

---

## Frontend Performance Marks

The frontend uses the following performance instrumentation:

- **Prefetch hit/miss**: The `usePrefetch` hook caches neighboring frames. A cache hit bypasses the network entirely, targeting NFR-4 (< 250 ms frame change).
- **Animation frame interval**: The `useAnimation` hook uses configurable intervals (500–2000 ms). Frame timing is managed via `setInterval` with sequence tagging to prevent stale updates.
- **AbortController cancellation**: Superseded requests are cancelled immediately when the user navigates, preventing wasted bandwidth and stale renders.

---

## Measurement Notes

Actual performance measurement against these targets requires real forecast data loaded through the Kerchunk pipeline. Key measurement scenarios:

1. **Cold start**: First request for a variable with no cache — measures full pipeline latency.
2. **Warm start**: Subsequent requests with backend cache populated — should be significantly faster.
3. **Animation cycle**: Playing through 10+ frames — measures prefetch effectiveness and frame-to-frame timing.
4. **Variable switch**: Changing from PM2.5 to Ozone — measures cache invalidation and fresh data load.

Tools for measurement:
- Backend: `structlog` timing fields in response logs
- Frontend: Browser DevTools Performance tab, Network timing
- Animation: Compare `setInterval` target vs actual frame display timestamps

---

## Future Optimizations (If Needed)

These optimizations are documented for reference but not yet implemented. They would be triggered by measurements showing specific bottlenecks:

| Bottleneck | Optimization |
|---|---|
| GeoJSON payload too large (> 1 MB) | Geometry simplification (Douglas-Peucker) or switch to MVT tiles |
| Contour generation > 1 s | Increase cache maxsize, consider pre-generation for common intervals |
| Animation jank at fast speeds | Increase prefetch window from ±1 to ±2, prioritize contour prefetch over filled |
| Memory pressure from cache | Reduce LRU sizes, implement WeakRef-based caching |
