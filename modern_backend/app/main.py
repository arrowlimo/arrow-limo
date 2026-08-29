import logging
import os

import psycopg2
from dotenv import load_dotenv

# Force rebuild: 2026-01-30 14:35:00 UTC - Login endpoint deployment
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from psycopg2.pool import PoolError

from .bootstrap.middleware import register_middlewares
from .bootstrap.router_registry import register_routers
from .bootstrap.spa_routes import register_spa_routes
from .db import (
    DatabaseConfigurationError,
    close_all_connections,
    get_connection,
    return_connection,
)
from .services.auth.provisioning import provision_2026_chauffeur_accounts
from .settings import get_settings

# Load environment variables from .env before settings resolution.
load_dotenv()

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
logger = logging.getLogger("modern_backend")
# Optional Sentry & OpenTelemetry (env-gated)
SENTRY_DSN = os.environ.get("SENTRY_DSN")
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if SENTRY_DSN:
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FastApiIntegration()],
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.environment,
            release=os.environ.get("RELEASE_VERSION"),
        )
    except Exception:
        pass

if OTEL_EXPORTER_OTLP_ENDPOINT:
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

        resource = Resource.create({"service.name": settings.app_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
    except Exception:
        pass

register_middlewares(app, settings, logger)

allowed_hosts = settings.trusted_hosts
if not allowed_hosts or allowed_hosts == ["*"]:
    allowed_hosts = ["arrow-limo.onrender.com", "localhost", "127.0.0.1", "testserver"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# CORS should be added last in the middleware chain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Report ready only when the production database is reachable."""
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            if cur.fetchone() != (1,):
                raise DatabaseConfigurationError("Database readiness query failed")
    except (psycopg2.Error, PoolError, OSError, RuntimeError) as exc:
        logger.error("Database readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    finally:
        if conn is not None:
            return_connection(conn)
    return {"status": "ok"}


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    close_all_connections()


@app.on_event("startup")
async def provision_driver_accounts():
    """Create missing driver accounts after deployment configuration is loaded."""
    try:
        provision_2026_chauffeur_accounts()
    except Exception as exc:
        logger.error("Driver account provisioning failed: %s", type(exc).__name__)


# Routers (MUST be included BEFORE mounting static files)
register_routers(app)

register_spa_routes(app)
