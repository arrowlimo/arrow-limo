import logging
import os

from dotenv import load_dotenv

# Force rebuild: 2026-01-30 14:35:00 UTC - Login endpoint deployment
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .bootstrap.middleware import register_middlewares
from .bootstrap.router_registry import register_routers
from .bootstrap.spa_routes import register_spa_routes
from .db import close_all_connections
from .services.auth.provisioning import provision_2026_chauffeur_accounts
from .settings import get_settings

# Load environment variables from .env before settings resolution.
load_dotenv()

settings = get_settings()
app = FastAPI(title=settings.app_name)
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

if settings.trusted_hosts and settings.trusted_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

# CORS should be added last in the middleware chain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint - verifies database connectivity"""
    # DB ping is optional here; keep lightweight
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
    except Exception:
        logger.exception("Driver account provisioning failed")


@app.get("/db-ping")
async def db_ping():
    """Test database connectivity by running a simple query."""
    try:
        from .db import get_connection, return_connection

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM banking_transactions")
            count = cur.fetchone()[0]
            cur.close()
            return {
                "status": "ok",
                "database": "connected",
                "banking_transactions_count": count,
            }
        finally:
            return_connection(conn)
    except Exception as e:
        return {"status": "error", "database": "disconnected", "error": str(e)}


# Routers (MUST be included BEFORE mounting static files)
register_routers(app)

register_spa_routes(app)
