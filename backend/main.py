"""
FastAPI application entrypoint.

Run locally:
    uvicorn backend.main:app --reload --port 8000

Swagger/OpenAPI docs auto-generated at /docs and /redoc.
"""
import os
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.database.db import init_db
from backend.utils.logging_middleware import RequestLoggingMiddleware
from backend.api.routes import (
    auth, detect, simulate, analytics, repairs, dashboard, roads, agents
)

logger = logging.getLogger("main")

app = FastAPI(
    title="Road Infrastructure AI Maintenance System",
    description=(
        "Backend integration layer connecting the YOLO detection model and "
        "degradation simulator (ml/) with PostgreSQL and the React frontend. "
        "Includes a CrewAI 4-agent workflow for autonomous repair planning."
    ),
    version="1.0.0",
)

# ---------- CORS ----------
# http://localhost:5173 = Vite dev server (Person C guide Step 1)
# http://localhost:3000 = dockerised production frontend (Step 8)
FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Request logging ----------
app.add_middleware(RequestLoggingMiddleware)

# ---------- Static file serving for uploaded images ----------
UPLOAD_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "uploads")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ---------- Routers ----------
app.include_router(auth.router)
app.include_router(detect.router)
app.include_router(simulate.router)
app.include_router(analytics.router)
app.include_router(repairs.router)
app.include_router(dashboard.router)
app.include_router(roads.router)
app.include_router(agents.router)   # ← new: POST /api/agents/run, GET /api/agents/reports


# ---------- Global error handling ----------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "detail": "Internal server error",
            "path": str(request.url.path),
        },
    )


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialised, tables created if not present.")


@app.get("/health", tags=["health"])
def health():
    """Simple liveness probe used by Docker and load balancers."""
    return {"status": "ok"}
