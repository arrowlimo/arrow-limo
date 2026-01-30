import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .routers import charges as charges_router
from .routers import charters as charters_router
from .routers import payments as payments_router
from .routers import bookings as bookings_router
from .routers import reports as reports_router
from .routers import receipts as receipts_router
from .routers import receipts_simple as receipts_simple_router
from .routers import receipts_split as receipts_split_router
from .routers import vehicles as vehicles_router
from .routers import employees as employees_router
from .routers import customers as customers_router
from .routers import pricing as pricing_router
from .routers import charter_sheet as charter_sheet_router
from .routers import invoices as invoices_router
from .routers import accounting as accounting_router
from .routers import banking as banking_router
from .routers import banking_allocations as banking_allocations_router
from .routers import driver_auth as driver_auth_router
from .routers import inspection_forms as inspection_forms_router
from .api import receipt_verification as receipt_verification_router
from .settings import get_settings
from .db import get_connection

settings = get_settings()
app = FastAPI(title=settings.app_name)
# Optional Sentry & OpenTelemetry (env-gated)
SENTRY_DSN = os.environ.get("SENTRY_DSN")
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if SENTRY_DSN:
    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        sentry_sdk.init(dsn=SENTRY_DSN, integrations=[FastApiIntegration()], traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE','0.0')))
    except Exception:
        pass

if OTEL_EXPORTER_OTLP_ENDPOINT:
    try:
        from opentelemetry import trace  # type: ignore
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing and correlation
@app.middleware("http")
async def add_correlation_and_timing(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    start = time.time()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Process-Time-ms"] = str(int((time.time() - start) * 1000))
    return response

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    return JSONResponse(status_code=500, content={"error": "internal_error", "message": str(exc), "request_id": rid})

@app.get("/health")
async def health():
    """Health check endpoint - verifies database connectivity"""
    # DB ping is optional here; keep lightweight
    return {"status": "ok"}

@app.get("/db-ping")
async def db_ping():
    """Test database connectivity by running a simple query."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM banking_transactions")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {
            "status": "ok",
            "database": "connected",
            "banking_transactions_count": count
        }
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }

# Mount Vue frontend at root (API routes use /api prefix so no conflict)
DIST_DIR = str(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")))
if os.path.isdir(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")

# Routers
app.include_router(driver_auth_router.router)
app.include_router(inspection_forms_router.router)  # Secure inspection forms
app.include_router(reports_router.router)
app.include_router(charges_router.router)
app.include_router(payments_router.router)
app.include_router(charters_router.router)
app.include_router(bookings_router.router)
app.include_router(receipts_router.router)
app.include_router(receipts_simple_router.router)  # Simplified receipts matching actual schema
app.include_router(receipts_split_router.router)
app.include_router(receipt_verification_router.router)  # Receipt verification (physical match)
app.include_router(invoices_router.router)
app.include_router(accounting_router.router)
app.include_router(banking_router.router)
app.include_router(banking_allocations_router.router)
app.include_router(vehicles_router.router)
app.include_router(employees_router.router)
app.include_router(customers_router.router)
app.include_router(pricing_router.router)
app.include_router(charter_sheet_router.router)