"""
Module: main.py

Purpose:
    FastAPI application entrypoint. In Milestone 1 this only exposes a health
    check and demonstrates the exception-handling wiring; planning/occupant/
    operator routers are added from Milestone 6 onward once the application
    services behind them exist.

Inputs:
    HTTP requests.

Outputs:
    HTTP responses. Domain errors (SSCPBaseError subclasses) are mapped to
    422 Unprocessable Entity with a structured error body; unexpected
    exceptions are mapped to 500 with a generic message (never leaking
    internals to the client).

Workflow:
    Uvicorn boots this module -> configure_logging() runs once -> app is
    created -> routers are registered -> exception handlers are registered.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import SSCPBaseError
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Occupant-Aware Demand-Response Planner for utility managing "
        "overloaded neighbourhood transformers."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production (Milestone 7/8 deployment notes)
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SSCPBaseError)
async def domain_error_handler(request: Request, exc: SSCPBaseError) -> JSONResponse:
    logger.warning("Domain error handling %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"error_type": exc.__class__.__name__, "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s", request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error_type": "InternalServerError", "detail": "An unexpected error occurred."},
    )


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Liveness/readiness probe used by docker-compose and (later) k8s."""
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


# Routers are registered here as they're implemented in later milestones:
from app.api.routers import planning

app.include_router(
    planning.router,
    prefix="/api/planning",
    tags=["planning"],
)