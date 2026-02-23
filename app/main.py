"""
Main FastAPI application entry point.

Changes in this version:
  1.  Chrome Extension /scan now calls the real zero-day detector.
  2.  HTML inputs are sanitised via bleach before processing.
  3.  CORS origins configurable from env (not hardcoded *).
  4.  Audit log written on every scan completion.
  5.  DB model for AuditLog created on startup alongside other tables.
  6.  /metrics endpoint serves actual Prometheus text exposition format.
"""
from __future__ import annotations

import json
import logging
import uuid
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import structlog

from app.config import settings
from app.api.routes import router as api_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.audit import AuditMiddleware
from app.services.database import init_db, close_db, get_db_session
from app.services.redis import init_redis, close_redis, get_redis_client
from app.services.scoring import compute_final_score
from app.services.graph import GraphService
from app.services.security import sanitize_html, sanitize_text, audit_log
from app.models.db import Scan as DBScan, Feedback as DBFeedback, RiskLevelEnum

# ── Structured logging ────────────────────────────────────────────────────────
# Get log level from settings, default to INFO
log_level = getattr(settings, 'LOG_LEVEL', 'INFO').upper()

# Configure standard library logging
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# Choose renderer based on log level
renderer = structlog.dev.ConsoleRenderer() if log_level == "DEBUG" else structlog.processors.JSONRenderer()

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        renderer,
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# ── Chrome Extension request models ──────────────────────────────────────────
class ChromeExtensionScanRequest(BaseModel):
    url: str
    suspicious_keywords_found: list  = []
    long_url:                  bool  = False
    excessive_subdomains:      bool  = False
    subdomain_count:           int   = 0
    suspicious_url_keywords:   bool  = False
    password_fields:           int   = 0
    external_links:            int   = 0
    hidden_inputs:             int   = 0
    iframe_count:              int   = 0
    html_content:              Optional[str] = None   # raw page HTML
    local_result:              Optional[dict] = None


class RootFeedbackRequest(BaseModel):
    scan_id:         Optional[str]  = None
    user_flag:       Optional[bool] = None
    corrected_label: Optional[str]  = None
    comment:         Optional[str]  = None
    type:            Optional[str]  = None


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup → yield → shutdown."""
    logger.info("Starting", app_name=settings.APP_NAME, version=settings.APP_VERSION)

    await init_db()
    logger.info("Database initialised")

    await init_redis()
    logger.info("Redis initialised")

    # Warm up zero-day model if not yet trained
    try:
        import sys, os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ml_path = os.path.join(project_root, "intelligence", "nlp")
        if ml_path not in sys.path:
            sys.path.insert(0, ml_path)
        import zero_day_detector as zdd
        # Ensures model is loaded / bootstrapped; non-blocking since it returns quickly
        zdd._ensure_loaded()
        logger.info("Zero-day detector ready")
    except Exception as e:
        logger.warning("Zero-day detector warm-up failed", error=str(e))

    try:
        from app.services.observability import init_observability
        init_observability(app)
        logger.info("Observability initialised")
    except Exception as e:
        logger.warning("Observability init failed", error=str(e))

    try:
        from app.tasks.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning("Scheduler init failed", error=str(e))

    yield  # ── Application running ────────────────────────────────────────────

    logger.info("Shutting down")
    try:
        from app.tasks.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    await close_redis()
    await close_db()
    logger.info("Shutdown complete")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Endpoint Threat Intelligence Platform — PhishGuard API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — restrict in production via CORS_ORIGINS env var
_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Request-level audit logging (outermost — captures all routes)
app.add_middleware(AuditMiddleware)

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Uncaught exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Versioned API routes ──────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_PREFIX)


# ══════════════════════════════════════════════════════════════════════════════
# Root / Chrome Extension compatible endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "name":    settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health")
async def health_check():
    from app.services.database import check_database_health
    from app.services.redis   import check_redis_health

    db_ok    = await check_database_health()
    redis_ok = await check_redis_health()

    svc_status = "healthy" if (db_ok and redis_ok) else "degraded"
    return {
        "status":   svc_status,
        "version":  settings.APP_VERSION,
        "database": "healthy" if db_ok    else "unhealthy",
        "redis":    "healthy" if redis_ok else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/metrics")
async def metrics():
    """Prometheus text exposition format metrics endpoint."""
    try:
        from app.services.observability import observability
        data = observability.get_prometheus_metrics()
        # If the observability service returns raw Prometheus text, serve as-is
        if isinstance(data, str):
            return PlainTextResponse(content=data, media_type="text/plain; version=0.0.4")
        return data
    except Exception as e:
        logger.warning("Prometheus metrics unavailable", error=str(e))
        return PlainTextResponse("# metrics unavailable\n", media_type="text/plain")


@app.get("/status")
async def get_status():
    return {
        "server":    "PhishGuard API",
        "version":   settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENVIRONMENT,
    }


@app.get("/threat-cache")
async def get_threat_cache():
    return {
        "malicious_domains":  [],
        "high_risk_patterns": [],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Chrome Extension: POST /scan ──────────────────────────────────────────────
@app.post("/scan")
async def scan_chrome_extension(
    request: ChromeExtensionScanRequest,
    redis:   aioredis.Redis   = Depends(get_redis_client),
    db:      AsyncSession     = Depends(get_db_session),
    req:     Request          = None,
):
    """
    Chrome Extension scan endpoint.
    Full pipeline: cache → ML + graph (parallel) → zero-day → fuse → persist.
    """
    from urllib.parse import urlparse
    import asyncio

    # ── Sanitise URL ──────────────────────────────────────────────────────
    raw_url = request.url.strip()
    domain  = urlparse(raw_url if raw_url.startswith("http") else f"http://{raw_url}").netloc

    # ── Sanitise optional HTML payload ───────────────────────────────────
    clean_html = sanitize_html(request.html_content or "") if request.html_content else None

    # ── Cache check ───────────────────────────────────────────────────────
    input_hash    = hashlib.sha256(raw_url.encode()).hexdigest()
    cached_raw    = await redis.get(f"scan:{input_hash}")
    if cached_raw:
        logger.info("Cache hit (extension)", domain=domain)
        return json.loads(cached_raw)

    # ── Parallel: graph score + feature-based ML score ───────────────────
    graph_service = GraphService()
    content       = sanitize_text(
        " ".join(request.suspicious_keywords_found) + " " + raw_url
    )

    try:
        graph_score, model_score = await asyncio.gather(
            asyncio.wait_for(graph_service.get_risk_score(domain), timeout=10.0),
            asyncio.wait_for(_feature_score(request), timeout=5.0),
        )
    except asyncio.TimeoutError:
        graph_score = 0.1
        model_score = 0.3

    # ── Zero-day detection ────────────────────────────────────────────────
    is_zero_day, anomaly_score = await _run_zero_day(content, raw_url)

    # ── Fuse ──────────────────────────────────────────────────────────────
    risk_level, confidence, reasons = compute_final_score(
        model_score=model_score,
        graph_score=graph_score,
        anomaly_score=anomaly_score,
    )

    if is_zero_day:
        reasons.insert(0, "⚠ Zero-day anomaly: never-before-seen pattern detected")

    result = {
        "risk":               risk_level.value,
        "confidence":         confidence,
        "reasons":            reasons[:10],
        "threat_intel_score": round(model_score, 3),
        "infra_gnn_score":    round(graph_score, 3),
        "total_score":        round(
            settings.MODEL_WEIGHT * model_score + settings.GRAPH_WEIGHT * graph_score, 3
        ),
        "is_zero_day":       is_zero_day,
        "anomaly_score":     round(anomaly_score, 3),
        "cluster_probability": 0.0,
        "campaign_id":        None,
        "gnn_enabled":        False,
    }

    # ── Cache ────────────────────────────────────────────────────────────
    await redis.setex(f"scan:{input_hash}", settings.REDIS_CACHE_TTL, json.dumps(result))

    # ── Persist ───────────────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    try:
        db_scan = DBScan(
            scan_id=scan_id,
            input_hash=input_hash,
            url=raw_url,
            html=clean_html,
            risk=RiskLevelEnum(risk_level.value),
            confidence=confidence,
            graph_score=graph_score,
            model_score=model_score,
            reasons=reasons,
            meta={"source": "chrome_extension", "is_zero_day": is_zero_day,
                  "anomaly_score": anomaly_score},
        )
        db.add(db_scan)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Failed to persist extension scan", error=str(e))

    # ── Audit log ────────────────────────────────────────────────────────
    client_ip = req.client.host if req and req.client else None
    audit_log(
        event="CHROME_EXTENSION_SCAN",
        ip=client_ip,
        details={
            "domain": domain,
            "risk":   risk_level.value,
            "zero_day": is_zero_day,
        },
    )

    logger.info("Extension scan complete", domain=domain, risk=risk_level.value, zero_day=is_zero_day)
    return result


# ── Chrome Extension: POST /feedback ─────────────────────────────────────────
@app.post("/feedback")
async def submit_feedback_root(
    data: RootFeedbackRequest,
    db:   AsyncSession = Depends(get_db_session),
):
    try:
        db_feedback = DBFeedback(
            scan_id=data.scan_id or str(uuid.uuid4()),
            user_flag=data.user_flag or False,
            corrected_label=data.corrected_label,
            comment=sanitize_text(data.comment or ""),
        )
        db.add(db_feedback)
        await db.commit()
        logger.info("Feedback persisted", scan_id=data.scan_id)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to persist feedback", error=str(e))

    return {"success": True}


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

async def _feature_score(req: ChromeExtensionScanRequest) -> float:
    """Lightweight feature-based score from Chrome Extension metadata."""
    score = 0.2  # baseline
    if req.long_url:               score += 0.10
    if req.excessive_subdomains:   score += 0.08 + req.subdomain_count * 0.01
    if req.suspicious_url_keywords: score += 0.07
    if req.password_fields > 0:    score += 0.10
    if req.external_links > 5:     score += 0.08
    if req.hidden_inputs > 2:      score += 0.06
    if req.iframe_count > 0:       score += 0.05
    if req.suspicious_keywords_found:
        score += min(len(req.suspicious_keywords_found) * 0.07, 0.25)
    if req.local_result:
        lr = req.local_result.get("local_risk", "LOW")
        if lr == "HIGH":   score += 0.20
        elif lr == "MEDIUM": score += 0.10
    return round(min(score, 1.0), 3)


async def _run_zero_day(content: str, url: str) -> tuple[bool, float]:
    """Run IsolationForest zero-day scorer in a thread pool."""
    import asyncio
    try:
        import sys, os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ml_path = os.path.join(project_root, "intelligence", "nlp")
        if ml_path not in sys.path:
            sys.path.insert(0, ml_path)
        import zero_day_detector as zdd

        loop  = asyncio.get_running_loop()
        score = await asyncio.wait_for(
            loop.run_in_executor(None, zdd.get_anomaly_score, content, url),
            timeout=5.0,
        )
        return bool(score >= settings.ZERO_DAY_THRESHOLD), float(score)
    except Exception:
        return False, 0.0


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
    )
