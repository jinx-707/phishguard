"""
Audit logging middleware.

Wraps every inbound HTTP request and logs:
  - method, path, status_code, response_time_ms, client IP
  - Optionally writes HIGH-risk scan events to the audit stream.

This sits at the Starlette middleware level so it catches ALL routes
regardless of auth status.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)

# Paths to skip (noise reduction)
_SKIP_PATHS = frozenset({
    "/health", "/metrics", "/docs", "/redoc",
    "/openapi.json", "/favicon.ico",
})


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Request-level audit logging middleware.

    Emits a structured log line for every meaningful request:
        AUDIT_REQUEST method=POST path=/scan status=200 duration_ms=142 ip=1.2.3.4
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start   = time.perf_counter()
        client_ip = _get_ip(request)
        method    = request.method
        path      = request.url.path

        try:
            response = await call_next(request)
            status   = response.status_code
        except Exception as exc:
            status = 500
            logger.error(
                "AUDIT_REQUEST",
                method=method,
                path=path,
                status=status,
                ip=client_ip,
                error=str(exc),
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        log = logger.info if status < 400 else logger.warning
        log(
            "AUDIT_REQUEST",
            method=method,
            path=path,
            status=status,
            duration_ms=duration_ms,
            ip=client_ip,
        )

        # Tag anomalously slow scans for investigation
        if path in ("/scan", "/api/v1/scan") and duration_ms > 10_000:
            logger.warning(
                "SLOW_SCAN_DETECTED",
                path=path,
                duration_ms=duration_ms,
                ip=client_ip,
            )

        return response


def _get_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For from reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
