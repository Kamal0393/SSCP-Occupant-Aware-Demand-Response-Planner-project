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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import (
    HardConstraintViolationError, InsufficientReductionCapacityError,
    SSCPBaseError, UnauthorizedOverrideError,
)
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
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SSCPBaseError)
async def domain_error_handler(request: Request, exc: SSCPBaseError) -> JSONResponse:
    logger.warning("Domain error handling %s: %s", request.url.path, exc)
    if isinstance(exc, UnauthorizedOverrideError) and request.url.path.endswith("/emergency-override"):
        status = 403
    elif isinstance(exc, (HardConstraintViolationError, InsufficientReductionCapacityError)):
        status = 409
    else:
        status = 422
    return JSONResponse(
        status_code=status,
        content={"error_type": exc.__class__.__name__, "detail": str(exc)},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.info("Database constraint failure on %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=409, content={
        "error_type": "Conflict", "detail": "The request conflicts with stored data or references an unknown resource."
    })


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database failure on %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={
        "error_type": "DatabaseUnavailable", "detail": "The database could not complete the request."
    })


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
from app.api.routers import analysis, planning, resources

app.include_router(
    planning.router,
    prefix="/api/planning",
    tags=["planning"],
)
app.include_router(resources.router, prefix="/api", tags=["resources"])
app.include_router(analysis.router, prefix="/api/planning", tags=["planning analysis"])
