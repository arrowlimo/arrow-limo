import os
import time
import uuid

from dotenv import load_dotenv

# Force rebuild: 2026-01-30 14:35:00 UTC - Login endpoint deployment
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api import receipt_verification as receipt_verification_router
from .auth import (
    get_current_user,
    is_auth_exempt_path,
    is_protected_path,
    require_roles,
    resolve_authenticated_user,
)
from .db import close_all_connections
from .routers import accounting as accounting_router
from .routers import (
    bank_audit_reconciliation as bank_audit_reconciliation_router,
)
from .routers import banking as banking_router
from .routers import banking_allocations as banking_allocations_router
from .routers import beverage_order as beverage_order_router
from .routers import beverage_reconciliation as beverage_reconciliation_router
from .routers import bookings as bookings_router
from .routers import charges as charges_router
from .routers import charter_sheet as charter_sheet_router
from .routers import charters as charters_router
from .routers import continuous_employment as continuous_employment_router
from .routers import customers as customers_router
from .routers import driver_auth as driver_auth_router
from .routers import employees as employees_router
from .routers import file_storage as file_storage_router
from .routers import inspection_forms as inspection_forms_router
from .routers import invoices as invoices_router
from .routers import metrics as metrics_router
from .routers import owe_david as owe_david_router
from .routers import payments as payments_router
from .routers import payroll_compliance as payroll_compliance_router
from .routers import payroll_entries as payroll_entries_router
from .routers import payroll_tax as payroll_tax_router
from .routers import pdf as pdf_router
from .routers import pricing as pricing_router
from .routers import receipts as receipts_router
from .routers import receipts_linked_display as receipts_linked_display_router
from .routers import receipts_simple as receipts_simple_router
from .routers import receipts_split as receipts_split_router
from .routers import reconciliation_report as reconciliation_report_router
from .routers import reports as reports_router
from .routers import cash_box as cash_box_router
from .routers import year_end as year_end_router
from .routers import t2_returns as t2_returns_router
from .routers import table_management as table_management_router
from .routers import vehicles as vehicles_router
from .routers import vendor_standardization as vendor_standardization_router
from .audit import router as audit_router
from .routes import cheque_books as cheque_books_router
from .routes import received_payments as received_payments_router
from .settings import get_settings

# Load environment variables from .env before settings resolution.
load_dotenv()

settings = get_settings()
app = FastAPI(title=settings.app_name)
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
            traces_sample_rate=float(
                os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")
            ),
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
    response.headers["X-Process-Time-ms"] = str(
        int((time.time() - start) * 1000)
    )
    return response


@app.middleware("http")
async def require_authenticated_api_user(request: Request, call_next):
    path = request.url.path
    if is_auth_exempt_path(path) or not is_protected_path(path):
        return await call_next(request)

    user = resolve_authenticated_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
        )

    request.state.current_user = user
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc),
            "request_id": rid,
        },
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
finance_roles = Depends(
    require_roles("admin", "manager", "super_user", "accountant")
)
admin_roles = Depends(require_roles("admin", "manager", "super_user"))
ops_roles = Depends(
    require_roles("admin", "manager", "super_user", "dispatcher", "dispatch")
)
authenticated_user = Depends(get_current_user)

app.include_router(driver_auth_router.router)
app.include_router(inspection_forms_router.router)  # Secure inspection forms
app.include_router(
    metrics_router.router, dependencies=[authenticated_user]
)  # Dashboard metrics
app.include_router(pdf_router.router)  # PDF generation
app.include_router(reports_router.router, dependencies=[finance_roles])
app.include_router(year_end_router.router, dependencies=[finance_roles])
app.include_router(charges_router.router, dependencies=[authenticated_user])
app.include_router(payments_router.router, dependencies=[authenticated_user])
app.include_router(charters_router.router, dependencies=[authenticated_user])
app.include_router(bookings_router.router, dependencies=[authenticated_user])
app.include_router(
    beverage_order_router.router, dependencies=[authenticated_user]
)
app.include_router(
    beverage_reconciliation_router.router, dependencies=[finance_roles]
)
app.include_router(receipts_router.router, dependencies=[authenticated_user])
app.include_router(
    receipts_simple_router.router,
    dependencies=[authenticated_user],
)  # Simplified receipts matching actual schema
app.include_router(
    receipts_split_router.router, dependencies=[authenticated_user]
)
app.include_router(
    receipts_linked_display_router.router,
    dependencies=[authenticated_user],
)  # Linked split receipts display
app.include_router(
    receipt_verification_router.router,
    dependencies=[authenticated_user],
)  # Receipt verification (physical match)
app.include_router(invoices_router.router, dependencies=[finance_roles])
app.include_router(accounting_router.router, dependencies=[finance_roles])
app.include_router(banking_router.router, dependencies=[finance_roles])
app.include_router(
    banking_allocations_router.router, dependencies=[finance_roles]
)
app.include_router(vehicles_router.router, dependencies=[ops_roles])
app.include_router(employees_router.router, dependencies=[admin_roles])
app.include_router(customers_router.router, dependencies=[authenticated_user])
app.include_router(
    owe_david_router.router, dependencies=[authenticated_user]
)  # David account tracking
app.include_router(pricing_router.router, dependencies=[ops_roles])
app.include_router(table_management_router.router, dependencies=[admin_roles])
app.include_router(
    t2_returns_router.router, dependencies=[finance_roles]
)  # T2 Corporate Tax Return entry
app.include_router(
    charter_sheet_router.router, dependencies=[authenticated_user]
)
app.include_router(
    file_storage_router.router, dependencies=[authenticated_user]
)  # File storage with role-based access
app.include_router(
    payroll_tax_router.router, dependencies=[finance_roles]
)  # Payroll & T4 form entry
app.include_router(
    payroll_entries_router.router, dependencies=[finance_roles]
)
app.include_router(
    continuous_employment_router.router, dependencies=[finance_roles]
)  # ROE lifecycle + submission tracking
app.include_router(
    payroll_compliance_router.router, dependencies=[finance_roles]
)  # PD7A submission audit + reporting
app.include_router(cash_box_router.router, dependencies=[finance_roles])
app.include_router(
    reconciliation_report_router.router, dependencies=[finance_roles]
)  # Banking-receipt reconciliation
app.include_router(
    vendor_standardization_router.router, dependencies=[admin_roles]
)  # Vendor name standardization
app.include_router(
    bank_audit_reconciliation_router.router, dependencies=[finance_roles]
)  # Bank account reconciliation for auditors

app.include_router(audit_router, dependencies=[finance_roles])

app.include_router(
    cheque_books_router.router, dependencies=[finance_roles]
)  # Cheque book management

app.include_router(
    received_payments_router.router, dependencies=[finance_roles]
)  # Record received payments


def get_frontend_dist_dir() -> str | None:
    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.abspath(
            os.path.join(base_dir, "..", "..", "..", "frontend", "dist")
        ),
        os.path.abspath(
            os.path.join(base_dir, "..", "..", "frontend", "dist")
        ),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


def get_frontend_index_path() -> str | None:
    dist_dir = get_frontend_dist_dir()
    if not dist_dir:
        return None
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.isfile(index_path):
        return index_path
    return None


def get_frontend_file_path(request_path: str) -> str | None:
    dist_dir = get_frontend_dist_dir()
    if not dist_dir:
        return None

    normalized_path = request_path.lstrip("/")
    candidate = os.path.abspath(os.path.join(dist_dir, normalized_path))
    dist_root = os.path.abspath(dist_dir)
    if candidate != dist_root and not candidate.startswith(dist_root + os.sep):
        return None
    if os.path.isfile(candidate):
        return candidate
    return None


@app.get("/beverage-order/print")
async def spa_beverage_order_print():
    """Serve SPA index for beverage print deep links opened in a new tab."""
    index_path = get_frontend_index_path()
    if index_path:
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/charter/confirmation/print")
async def spa_charter_confirmation_print():
    """Serve SPA index for charter confirmation print deep links."""
    index_path = get_frontend_index_path()
    if index_path:
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/")
async def spa_root():
    index_path = get_frontend_index_path()
    if index_path:
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    frontend_file = get_frontend_file_path(full_path)
    if frontend_file:
        return FileResponse(frontend_file)

    index_path = get_frontend_index_path()
    if index_path:
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})
