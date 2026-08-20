"""Air Composition Forecast Viewer — FastAPI application."""

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


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", version=app.version)
