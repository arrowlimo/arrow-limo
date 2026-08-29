import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..auth import is_auth_exempt_path, is_protected_path, resolve_authenticated_user


def _get_rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return client_host


def _register_correlation_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_correlation_and_timing(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        start = time.time()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time-ms"] = str(int((time.time() - start) * 1000))
        return response


def _register_security_headers_middleware(app: FastAPI, settings: Any) -> None:
    @app.middleware("http")
    async def apply_security_headers(request: Request, call_next):
        response = await call_next(request)
        if settings.security_headers_enabled:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault(
                "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
            )
        return response


def _register_rate_limit_middleware(app: FastAPI, settings: Any) -> None:
    rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
    rate_limit_lock = Lock()

    @app.middleware("http")
    async def enforce_rate_limit(request: Request, call_next):
        auth_rate_limited = request.url.path.startswith("/auth/") and request.url.path not in {
            "/auth/validate",
            "/auth/logout",
        }
        rate_limited_path = is_protected_path(request.url.path) or auth_rate_limited
        if not settings.rate_limit_enabled or not rate_limited_path:
            return await call_next(request)

        key = _get_rate_limit_key(request)
        now = time.monotonic()
        window = max(1, settings.rate_limit_window_seconds)
        limit = max(1, settings.rate_limit_requests)

        with rate_limit_lock:
            bucket = rate_limit_buckets[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(window)},
                )
            bucket.append(now)

        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(limit))
        return response


def _register_request_logging_middleware(
    app: FastAPI, settings: Any, logger: logging.Logger
) -> None:
    @app.middleware("http")
    async def log_http_requests(request: Request, call_next):
        if not settings.log_requests:
            return await call_next(request)

        started = time.time()
        response = await call_next(request)
        elapsed_ms = int((time.time() - started) * 1000)
        req_id = getattr(request.state, "request_id", "-")
        logger.info(
            "http_request request_id=%s method=%s path=%s status=%s duration_ms=%s",
            req_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def _register_authentication_middleware(app: FastAPI) -> None:
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


def _register_unhandled_exception_handler(
    app: FastAPI, settings: Any, logger: logging.Logger
) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
        if not rid:
            rid = uuid.uuid4().hex[:16]
        logger.exception("unhandled_exception request_id=%s path=%s", rid, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Internal server error",
                "request_id": rid,
            },
        )


def register_middlewares(app: FastAPI, settings: Any, logger: logging.Logger) -> None:
    """Register HTTP middleware and global exception handlers."""
    _register_correlation_middleware(app)
    _register_security_headers_middleware(app, settings)
    _register_rate_limit_middleware(app, settings)
    _register_request_logging_middleware(app, settings, logger)
    _register_authentication_middleware(app)
    _register_unhandled_exception_handler(app, settings, logger)
