"""Air Composition Forecast Viewer — FastAPI application."""

import subprocess
import threading
from pathlib import Path as _Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.api.bounds import router as bounds_router
from backend.app.api.contours import router as contours_router
from backend.app.api.export_gif import router as export_gif_router
from backend.app.api.fill_image import router as fill_image_router
from backend.app.api.filled import router as filled_router
from backend.app.api.metadata import router as metadata_router
from backend.app.api.point import router as point_router
from backend.app.api.preview import router as preview_router

app = FastAPI(
    title="Air Composition Forecast Viewer API",
    version="0.1.0",
    description=(
        "Backend API for the Air Composition Forecast Viewer. "
        "Provides metadata discovery, contour generation, filled-field rendering, "
        "and point-query services over GRIB2 forecast data accessed via Kerchunk."
    ),
)

# CORS: allow the Vite frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str


# Include API routers
app.include_router(metadata_router)
app.include_router(bounds_router)
app.include_router(contours_router)
app.include_router(filled_router)
app.include_router(fill_image_router)
app.include_router(export_gif_router)
app.include_router(point_router)
app.include_router(preview_router)


def _background_ingest():
    """Run ingest scripts in background on startup."""
    import contextlib
    import os
    import sys

    python = sys.executable
    base = _Path(__file__).resolve().parent.parent

    gefs_local = os.environ.get("FORECASTVIEW_GEFS_LOCAL_PATH") or os.environ.get(
        "FORECASTVIEW_LOCAL_PATH"
    )
    aqm_local = os.environ.get("FORECASTVIEW_AQM_LOCAL_PATH")

    gefs_cmd = [python, str(base / "scripts" / "ingest.py"), "--days", "1"]
    if gefs_local:
        gefs_cmd.extend(["--local-path", gefs_local])

    # Ingest latest GEFS
    with contextlib.suppress(Exception):
        subprocess.run(
            gefs_cmd,
            cwd=str(base.parent),
            capture_output=True,
            timeout=120,
        )

    aqm_cmd = [python, str(base / "scripts" / "ingest_aqm.py"), "--days", "1"]
    if aqm_local:
        aqm_cmd.extend(["--local-path", aqm_local])

    # Ingest latest AQM
    with contextlib.suppress(Exception):
        subprocess.run(
            aqm_cmd,
            cwd=str(base.parent),
            capture_output=True,
            timeout=60,
        )


@app.on_event("startup")
async def startup_ingest():
    """Trigger background data ingest on server startup."""
    thread = threading.Thread(target=_background_ingest, daemon=True)
    thread.start()


@app.post("/api/ingest")
async def trigger_ingest(
    product: str = "all",
    days: int = 1,
):
    """Trigger background data ingest for the specified product."""
    import os
    import sys

    python = sys.executable
    base = _Path(__file__).resolve().parent.parent

    results = {}

    gefs_local = os.environ.get("FORECASTVIEW_GEFS_LOCAL_PATH") or os.environ.get(
        "FORECASTVIEW_LOCAL_PATH"
    )
    aqm_local = os.environ.get("FORECASTVIEW_AQM_LOCAL_PATH")

    if product in ("all", "air"):
        try:
            cmd = [python, str(base / "scripts" / "ingest.py"), "--days", str(days)]
            if gefs_local:
                cmd.extend(["--local-path", gefs_local])
            proc = subprocess.run(
                cmd,
                cwd=str(base.parent),
                capture_output=True,
                text=True,
                timeout=120,
            )
            results["air"] = {
                "status": "ok" if proc.returncode == 0 else "error",
                "output": proc.stdout[-500:] if proc.stdout else "",
            }
        except Exception as e:
            results["air"] = {"status": "error", "output": str(e)}

    if product in ("all", "aqm"):
        try:
            cmd = [python, str(base / "scripts" / "ingest_aqm.py"), "--days", str(days)]
            if aqm_local:
                cmd.extend(["--local-path", aqm_local])
            proc = subprocess.run(
                cmd,
                cwd=str(base.parent),
                capture_output=True,
                text=True,
                timeout=60,
            )
            results["aqm"] = {
                "status": "ok" if proc.returncode == 0 else "error",
                "output": proc.stdout[-500:] if proc.stdout else "",
            }
        except Exception as e:
            results["aqm"] = {"status": "error", "output": str(e)}

    return {"results": results}


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", version=app.version)
