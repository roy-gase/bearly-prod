from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("bearly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production:
        # The schema is Alembic's job in production; creating it here would let
        # the database drift from the migration history unnoticed.
        if not settings.email_configured:
            raise RuntimeError(
                "BEARLY_SMTP_HOST must be set in production: without it, password "
                "reset silently does nothing and users are locked out permanently."
            )
        logger.info("Bearly API starting (production; schema managed by Alembic)")
    else:
        init_db()
    logger.info(
        "Bearly API ready (env=%s, ai_provider=%s)", settings.environment, settings.ai_provider
    )
    yield


app = FastAPI(
    title="Bearly API",
    description="Personal finance tracking with a deterministic finance engine and AI agents.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

if settings.is_production:
    # Rejects requests with a forged Host header, which otherwise poisons any
    # absolute URL the app generates.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.environment == "production":
        # Assumes TLS termination in front of the app.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Return field errors without echoing the submitted values.

    A validation error on a finance form would otherwise reflect balances and
    amounts back into logs and error trackers.
    """
    errors = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Some fields need attention", "errors": errors},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


app.include_router(api_router, prefix=settings.api_prefix)
