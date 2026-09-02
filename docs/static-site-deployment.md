# Static Site Export & Deployment

This guide covers building and deploying ForecastView as a **self-contained
static site** — a directory of HTML/JS/CSS plus precomputed data that runs in a
browser with **no backend server**. It is designed for air-gapped or restricted
environments (e.g. RZDM) where only static file hosting is available.

The key operational property: **adding new dates/cycles never requires
rebuilding the frontend.** Re-running the exporter appends data and updates a
few small index JSON files; the already-built HTML/JS picks them up on next
load.

---

## 1. Prerequisites

- Conda environment `forecastview` (Python 3.12) with the backend deps
  (`matplotlib`, `rasterio`, `kerchunk`, `fsspec`, `s3fs`, …).
- Node.js (v22 tested) for the frontend build.
- Network access to the source data during export. GEFS-Aerosol fields are read
  via kerchunk manifests that point at `s3://noaa-gefs-pds/…` (anonymous
  access). The manifest tree itself lives in `data/manifests/gefs/`.

---

## 2. Build the frontend (once per code change)

The frontend must be built in **static mode** so it fetches relative data paths
instead of `/api/…` endpoints.

```bash
cd frontend
npm ci
VITE_STATIC_MODE=true VITE_BASE_PATH=./ npm run build
```

This produces `frontend/dist/` with:

- relative asset URLs (`base: './'`), and
- a marker file `frontend/dist/data/build-info.json` containing
  `{"staticMode": true, …}`.

The exporter **gates on that marker** and refuses to copy a dist that was not
built in static mode, so you cannot accidentally ship a dynamic bundle into the
static site. (The marker itself lives under `dist/data/`, which the exporter
never copies — `data/` is reserved for exporter output — so it is a build-time
check only and does not appear in `dist_static/`.)

You can skip this manual step by passing `--build-frontend` to the exporter
(see below), which runs `npm ci && npm run build` for you.

---

## 3. Export the static site

```bash
python backend/scripts/export_static.py --product air --days 1 --output /tmp/fv_static
```

Common flags:

| Flag | Meaning |
| --- | --- |
| `--product` | Domain/product to export (`air`, `aqm`, …). |
| `--days N` | Export the most recent `N` discovered dates (default 3). |
| `--workers N` | Parallel frame-render processes (default 4). |
| `--output DIR` | Destination site directory (default `dist_static`). |
| `--no-fields` | Skip Float32 field grids (disables client point queries). |
| `--no-contours` | Skip precomputed contour GeoJSON. |
| `--frontend-dist DIR` | Path to a prebuilt static-mode dist (default `frontend/dist`). |
| `--build-frontend` | Run `npm ci && npm run build` before copying the shell. |
| `--no-frontend` | Emit data only; do not copy the HTML shell. |

The run:

1. Writes `data/catalog.json` and the per-product `dates.json` (the **sorted
   union** of any existing dates and the newly exported ones).
2. Writes `data/<product>/bounds.json` once (grid bounds + georeferencing).
3. For each date/run writes `runs.json`, `variables.json`, `levels.json`,
   `times.json`, and `grid.json`.
4. Renders each frame: `fill/<var>/f<NNN>.png`, `contours/<var>/f<NNN>.json`,
   and `field/<var>/f<NNN>.bin` — **skipping files that already exist**
   (idempotent / append-safe).
5. Copies the static-mode frontend shell into the output (never clobbering the
   exporter's own `data/` directory or files already present).

If any frame fails to render, the exporter exits with code `2` and prints a
`FATAL ERROR: N frame(s) failed` line.

---

## 4. Output directory layout

```
dist_static/                      # deployable directory (rsync/scp to web server)
├── index.html                    # copied from frontend/dist
├── assets/                       # hashed JS/CSS bundle (static-mode build)
├── favicon.svg, icons.svg, …     # other Vite outputs
└── data/                         # emitted by export_static.py (append-only)
    ├── catalog.json
    └── <product>/                # e.g. "air"
        ├── dates.json            # union of all exported dates (rewritten each run)
        ├── bounds.json           # grid bounds for the product (written once)
        └── <YYYYMMDD>/
            ├── runs.json         # list of runs for this date
            └── <run>/            # e.g. 00
                ├── levels.json       # pressure levels per variable
                ├── variables.json    # renderable variables + colors
                ├── times.json        # forecast hours + valid times
                ├── grid.json         # grid shape/georeferencing for point query
                ├── fill/<var>/f<NNN>.png          # animated fill imagery
                ├── contours/<var>/f<NNN>.json     # GeoJSON isolines
                └── field/<var>/f<NNN>.bin         # Float32 grid for point query
```

The layout is dictated by `frontend/src/api/staticMode.ts::buildUrl`, which maps
each logical endpoint to a relative file path. The exporter must produce exactly
this tree.

### Field grid files (point-query parity)

Point queries cannot be precomputed for every possible click, so the raw grid
ships to the browser as `field/<var>/f<NNN>.bin`: little-endian `float32`,
shape `(lat, lon)`, row-major, C-order, after the same `-180°` longitude shift
used for the imagery. Shape and georeferencing live once per run in `grid.json`.
On click, the client fetches (and caches) the `.bin`, does a nearest-neighbor
index lookup mirroring `backend/app/point_query/nearest.py`, and displays the
value (NaN cells render "no data"). Use `--no-fields` if you only need imagery.

---

## 5. Serve / verify locally

```bash
python -m http.server -d /tmp/fv_static 8099
```

Open <http://localhost:8099/> and check:

- date / run / variable selectors populate from `data/…`;
- animation advances through forecast hours (fill imagery);
- contours render on top of the fill;
- clicking the map returns a point value (reads the `.bin` grid);
- the legend matches the variable's color ramp.

> Serve over HTTP — do not open `index.html` via `file://`. The browser blocks
> `fetch()` of the local `.json`/`.bin`/`.png` data under the `file://` origin.

---

## 6. Appending new dates/cycles

Re-run the exporter against the **same** `--output`. `dates.json` is rewritten
as a union, and existing frames are skipped, so only new work is done:

```bash
python backend/scripts/export_static.py --product air --days 3 --output /tmp/fv_static
```

Because the frontend bundle is date-agnostic (it reads `dates.json` at load
time), you do **not** rebuild the frontend. Re-deploy just the changed `data/`
tree (or the whole directory).

> **When the frontend code *does* change:** the shell copy is append-safe — it
> never overwrites files already in `--output`. Rebuilding `frontend/dist` alone
> will not update a previously exported site. Delete the old shell first
> (`rm -rf <output>/assets <output>/index.html …`, keeping `data/`), or export
> to a fresh directory and swap it in.

### Cron example

To append the latest cycle every 6 hours:

```cron
0 */6 * * * cd /path/to/forecastview && \
  /path/to/conda/envs/forecastview/bin/python \
  backend/scripts/export_static.py --product air --days 2 \
  --output /srv/fv_static --no-frontend >> /var/log/fv_export.log 2>&1
```

`--no-frontend` is used here because the shell was copied once during the
initial build; subsequent appends only touch `data/`.

---

## 7. Deploy to RZDM

Deploy is a plain file copy of the site directory to the static web host:

```bash
rsync -av --delete /tmp/fv_static/ user@rzdm-host:/var/www/fv_static/
```

Notes:

- `--delete` keeps the host in sync with the source tree; omit it if the host
  accumulates content you must preserve.
- Ensure the web server sends correct MIME types for `.json`, `.png`, and
  `.bin`, and enables gzip (`Accept-Encoding`) — the `.bin` grids and contour
  GeoJSON compress roughly in half.
- There is no server-side component: no Python, no API, no database on the
  target host.

---

## 8. Offline basemap

The map uses remote vector tiles when the browser has internet access. If the
tile style fails to load (air-gapped / Wi-Fi off), `ForecastMap` automatically
falls back to a bundled **tile-free background style**
(`frontend/src/config/localStyle.ts`) — a plain ocean-colored canvas with no
sources. The forecast layers (fill, contours, labels) are independent of the
basemap and still render normally, so the site remains fully usable offline;
only the reference geography is absent.
