# ForecastView

A web-based scientific forecast viewer for NOAA Forecast data. ForecastView displays contour lines and filled contour maps of aerosol composition forecasts on an interactive MapLibre map, with data sourced directly from NOAA's public S3 bucket (`noaa-gefs-pds`).

## Tech Stack

| Layer    | Technology                                     |
|----------|------------------------------------------------|
| Backend  | Python 3.12, FastAPI, xarray, Kerchunk, contourpy, pyproj |
| Frontend | React 19, TypeScript, MapLibre GL JS, Vite     |
| Data     | GRIB2 via Kerchunk references to NOAA S3       |
| Env      | Conda (environment.yml)                        |

---

## Getting Started

### Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Mamba](https://mamba.readthedocs.io/)
- Node.js 18+ and npm
- Git

### Installation

```bash
git clone <repo-url> forecastview
cd forecastview

# Create and activate the conda environment (Python + scientific deps)
conda env create -f environment.yml
conda activate forecastview

# Install frontend dependencies
cd frontend && npm install
cd ..
```

### Running in Development

Start the backend and frontend in separate terminals:

```bash
# Terminal 1 — Backend (port 8000, auto-reload)
cd backend
python run.py

# Terminal 2 — Frontend (port 5173, proxied to backend)
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

The Vite dev server proxies `/api/*` requests to the backend on port 8000, so both servers must be running.

---

## Using the Application

1. **Select a product** — Choose from the available forecast products (e.g., Air Composition).
2. **Pick a date and run** — The viewer discovers available dates and model initialization cycles automatically from S3.
3. **Choose a variable** — Variables are grouped by category (Optical Depth, Column Mass Density, etc.).
4. **Browse forecast hours** — Step through forecast times to see how fields evolve.
5. **Interact with the map** — Pan, zoom, and click on the map to query point values at any location.

The map renders contour isolines and filled contour polygons as GeoJSON layers on top of a standard basemap.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FORECASTVIEW_BUCKET` | S3 bucket name | `noaa-gefs-pds` |
| `FORECASTVIEW_PATH_PATTERN` | GRIB2 file path pattern in bucket (supports `{date}`, `{cycle}`, `{fhr}` placeholders) | — |
| `FORECASTVIEW_MAX_WORKERS` | Thread count for manifest generation | `16` |
| `FORECASTVIEW_CACHE_SIZE` | Dataset handle cache size | `8` |

Example path pattern:

```
gefs.{date}/{cycle}/chem/pgrb2ap25/gefs.chem.t{cycle}z.a2d_0p25.f{fhr:03d}.grib2
```

---

## API Reference

All endpoints are prefixed with `/api`.

### Metadata

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/catalog` | List available products |
| GET | `/api/dates?product=air` | Available forecast dates |
| GET | `/api/runs?product=air&date=YYYYMMDD` | Available model runs (cycles) |
| GET | `/api/variables?product=air&date=...&run=...` | Variables with rendering config |
| GET | `/api/levels?...&variable=...` | Vertical levels for a variable |
| GET | `/api/times?...&run=...` | Forecast hours and valid times |

### Data

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/contours?product=air&date=...&run=...&variable=...&fhr=...` | GeoJSON contour isolines |
| GET | `/api/filled?product=air&date=...&run=...&variable=...&fhr=...` | GeoJSON filled contour polygons |
| GET | `/api/point?...&lat=...&lon=...` | Point value at nearest grid cell |

### Development / Debug

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bounds?...` | Geographic bounds polygon |
| GET | `/api/preview?...` | Downsampled field points |

---

## Adding New Datasets

ForecastView is designed for GRIB2 data accessible via S3. Adding a new product involves three steps.

### 1. Create a Domain Config

Add a YAML file at `config/domains/{product_id}.yaml`:

```yaml
product:
  name: "My New Product"
  id: "my_product"

categories:
  - "Category A"
  - "Category B"

variables:
  myVar:
    shortName: "myVar"
    fullName: "My Variable Long Name"
    units: "kg m-2"
    category: "Category A"
    rendering:
      colormap: "rainbow"        # matplotlib colormap name
      contourInterval: 0.1       # isoline spacing
      fillLevels: [0, 0.1, 0.2, 0.5, 1.0, 2.0]  # filled contour thresholds
```

See `config/domains/air.yaml` for a complete example with multiple categories and variables.

### 2. Configure the Data Source

Point ForecastView at the GRIB2 files via environment variables:

```bash
export FORECASTVIEW_BUCKET="your-s3-bucket"
export FORECASTVIEW_PATH_PATTERN="path/to/{date}/{cycle}/file.f{fhr:03d}.grib2"
```

The path pattern supports these placeholders:
- `{date}` — Forecast date (YYYYMMDD)
- `{cycle}` — Model cycle/run hour (e.g., 00, 06, 12, 18)
- `{fhr}` or `{fhr:03d}` — Forecast hour (zero-padded)

For more advanced data sources, extend the `KerchunkStore` class in `backend/app/data/kerchunk_store.py`.

### 3. Register the Product

Add your product to the catalog list in `backend/app/api/metadata.py` (the `_CATALOG` list). The metadata endpoints will then auto-discover available dates, runs, and variables from the data.

---

## Testing

### Backend

```bash
# Unit tests (no S3 access required)
conda run -n forecastview pytest

# Integration tests (requires S3 access)
pytest -m integration
```

### Frontend

```bash
cd frontend

# Type checking
npx tsc --noEmit

# Full production build (also validates types)
npm run build
```

---

## Deployment

### Backend

Run with multiple workers behind a reverse proxy:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

Build the static SPA and serve with any web server:

```bash
cd frontend
npm run build
# Output in frontend/dist/
```

Serve `frontend/dist/` via nginx, Caddy, CloudFront, or any static file host.

### Reverse Proxy Setup

The frontend is a static single-page application. Configure your web server to:
1. Serve files from `frontend/dist/` for all non-API routes
2. Proxy `/api/*` requests to the backend (e.g., `http://localhost:8000`)

Example nginx snippet:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location / {
    root /path/to/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

### Single-Origin Alternative

You can also mount the built frontend as static files directly in FastAPI, serving everything from a single process. This simplifies deployment at the cost of scaling flexibility.

---

## Project Structure

```
forecastview/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI route handlers
│   │   ├── cache/        # Cache utilities
│   │   ├── config/       # Domain config loader
│   │   ├── contours/     # Contour generation (contourpy) + GeoJSON serialization
│   │   ├── data/         # Kerchunk store + field selector
│   │   ├── point_query/  # Nearest-gridpoint lookup
│   │   ├── projections/  # Coordinate transforms (pyproj)
│   │   ├── rendering/    # Rendering utilities
│   │   ├── utils/        # Dev utilities (field stats, reference plots, grid inspector)
│   │   └── main.py       # FastAPI app entry point
│   ├── scripts/          # Standalone validation scripts
│   └── tests/            # pytest test suite
├── config/
│   └── domains/          # YAML domain configurations (one per product)
├── docs/                 # Design docs, validation reports, performance targets
├── frontend/
│   └── src/
│       ├── api/          # API client + TypeScript types
│       ├── components/   # React components (map layers, selectors, panels)
│       ├── config/       # Map style config
│       ├── context/      # React contexts (ViewerContext, NotificationContext)
│       └── hooks/        # Custom hooks (useMetadata, useContours, useAnimation)
├── environment.yml       # Conda environment specification
└── README.md
```

---

## License

This project is part of the NOAA-EMC ecosystem. See [LICENSE](LICENSE) and [DISCLAIMER](DISCLAIMER) for details.

## Disclaimer

The United States Department of Commerce (DOC) GitHub project code is provided on an "as is" basis and the user assumes responsibility for its use. DOC has relinquished control of the information and no longer has responsibility to protect the integrity, confidentiality, or availability of the information. Any claims against the Department of Commerce stemming from the use of its GitHub project will be governed by all applicable Federal law. Any reference to specific commercial products, processes, or services by service mark, trademark, manufacturer, or otherwise, does not constitute or imply their endorsement, recommendation or favoring by the Department of Commerce. The Department of Commerce seal and logo, or the seal and logo of a DOC bureau, shall not be used in any manner to imply endorsement of any commercial product or activity by DOC or the United States Government.
