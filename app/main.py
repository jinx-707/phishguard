"""
Main FastAPI application entry point.
"""
import logging
import uuid
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import structlog

from app.config import settings
from app.api.routes import router as api_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.database import init_db, close_db, get_db_session
from app.services.redis import init_redis, close_redis, get_redis_client
from app.services.scoring import compute_final_score
from app.services.graph import GraphService
from app.models.db import Scan as DBScan, Feedback as DBFeedback

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# Models for root-level endpoints (Chrome Extension compatibility)
class ChromeExtensionScanRequest(BaseModel):
    url: str
    suspicious_keywords_found: list = []
    long_url: bool = False
    excessive_subdomains: bool = False
    subdomain_count: int = 0
    suspicious_url_keywords: bool = False
    password_fields: int = 0
    external_links: int = 0
    hidden_inputs: int = 0
    iframe_count: int = 0
    local_result: Optional[dict] = None


class FeedbackRequest(BaseModel):
    scan_id: Optional[str] = None
    user_flag: Optional[bool] = None
    corrected_label: Optional[str] = None
    comment: Optional[str] = None
    type: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting application", app_name=settings.APP_NAME, version=settings.APP_VERSION)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis
    await init_redis()
    logger.info("Redis initialized")
    
    # Initialize observability
    try:
        from app.services.observability import init_observability
        init_observability(app)
        logger.info("Observability initialized")
    except Exception as e:
        logger.warning("Observability initialization failed", error=str(e))
    
    # Start task scheduler
    try:
        from app.tasks.scheduler import start_scheduler
        start_scheduler()
        logger.info("Task scheduler started")
    except Exception as e:
        logger.warning("Scheduler initialization failed", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Stop scheduler
    try:
        from app.tasks.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("Scheduler stopped")
    except Exception:
        pass
    
    await close_redis()
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Endpoint Threat Intelligence Platform Core API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally."""
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


# Include API routes
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.services.database import check_database_health
    from app.services.redis import check_redis_health
    
    db_healthy = await check_database_health()
    redis_healthy = await check_redis_health()
    
    status = "healthy" if (db_healthy and redis_healthy) else "degraded"
    
    return {
        "status": status,
        "version": settings.APP_VERSION,
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy",
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from app.services.observability import observability
    return observability.get_prometheus_metrics()


# ============================================
# Chrome Extension Compatible Endpoints
# (Root level for extension compatibility)
# ============================================

@app.post("/scan")
async def scan_chrome_extension(
    request: ChromeExtensionScanRequest,
    redis: redis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Chrome Extension scan endpoint.
    Compatible with the PhishGuard Chrome Extension.
    """
    domain = request.url
    if not domain.startswith('http'):
        domain = f'http://{domain}'
    from urllib.parse import urlparse
    domain = urlparse(domain).netloc or urlparse(domain).path
    
    logger.info(f"Scanning: {domain}")
    
    # Check cache
    input_hash = hashlib.sha256(request.url.encode()).hexdigest()
    cached_result = await redis.get(f"scan:{input_hash}")
    if cached_result:
        import json
        logger.info("Cache hit", input_hash=input_hash)
        return json.loads(cached_result)
    
    # Calculate risk score
    risk_result = await calculate_risk(request.dict(), domain)
    
    # Cache result
    import json
    await redis.setex(f"scan:{input_hash}", 3600, json.dumps(risk_result))
    
    # Persist to database
    scan_id = str(uuid.uuid4())
    try:
        from app.models.db import RiskLevelEnum
        db_scan = DBScan(
            scan_id=scan_id,
            input_hash=input_hash,
            url=request.url,
            risk=RiskLevelEnum(risk_result.get('risk', 'LOW')),
            confidence=risk_result.get('confidence', 0.5),
            graph_score=risk_result.get('infra_gnn_score', 0.0),
            model_score=risk_result.get('threat_intel_score', 0.0),
            reasons=risk_result.get('reasons', []),
            meta={},
        )
        db.add(db_scan)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Failed to persist scan", error=str(e))
    
    logger.info(f"Result: {risk_result['risk']} ({risk_result['confidence']})")
    
    return risk_result


@app.post("/feedback")
async def submit_feedback(
    data: FeedbackRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Feedback endpoint for Chrome Extension.
    """
    logger.info(f"Feedback received: {data.type or 'unknown'}")
    
    # Persist feedback
    try:
        db_feedback = DBFeedback(
            scan_id=data.scan_id or str(uuid.uuid4()),
            user_flag=data.user_flag or False,
            corrected_label=data.corrected_label,
            comment=data.comment,
        )
        db.add(db_feedback)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Failed to persist feedback", error=str(e))
    
    return {"success": True}


@app.get("/status")
async def get_status():
    """Get server status."""
    return {
        "server": "PhishGuard API",
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "redis": "connected",
    }


@app.get("/threat-cache")
async def get_threat_cache():
    """Get threat intelligence cache."""
    return {
        "malicious_domains": [],
        "high_risk_patterns": [],
        "timestamp": datetime.utcnow().isoformat()
    }


# Risk calculation for Chrome Extension
async def calculate_risk(data: dict, domain: str) -> dict:
    """Calculate comprehensive risk score."""
    
    score = 0.0
    reasons = []
    
    # Get graph score
    graph_service = GraphService()
    graph_score = await graph_service.get_risk_score(domain)
    
    # 1. Graph-based analysis
    if graph_score > 0.5:
        score += graph_score * 0.35
        reasons.append(f"Graph detected infrastructure risk: {graph_score:.2f}")
    
    # 2. Content-based analysis
    suspicious_keywords = data.get("suspicious_keywords_found", [])
    if suspicious_keywords:
        keyword_score = min(len(suspicious_keywords) * 0.15, 0.3)
        score += keyword_score
        reasons.append(f"Found suspicious keywords: {', '.join(suspicious_keywords[:3])}")
    
    # 3. URL-based analysis
    if data.get("long_url"):
        score += 0.1
        reasons.append("URL is unusually long")
    
    if data.get("excessive_subdomains"):
        score += 0.08
        reasons.append(f"Excessive subdomains: {data.get('subdomain_count', 0)}")
    
    if data.get("suspicious_url_keywords"):
        score += 0.07
        reasons.append("Suspicious keywords in URL")
    
    # 4. DOM-based analysis
    if data.get("password_fields", 0) > 0:
        score += 0.1
        reasons.append("Page contains password input fields")
    
    if data.get("external_links", 0) > 5:
        score += 0.1
        reasons.append(f"High number of external links: {data.get('external_links')}")
    
    if data.get("hidden_inputs", 0) > 2:
        score += 0.08
        reasons.append(f"Multiple hidden inputs: {data.get('hidden_inputs')}")
    
    if data.get("iframe_count", 0) > 0:
        score += 0.06
        reasons.append(f"Page contains {data.get('iframe_count')} iframe(s)")
    
    # 5. Local AI result
    if data.get("local_result"):
        local_risk = data["local_result"].get("local_risk", "LOW")
        local_conf = data["local_result"].get("local_confidence", 0.0)
        
        if local_risk == "HIGH":
            score += 0.2
        elif local_risk == "MEDIUM":
            score += 0.1
    
    # Normalize score
    score = min(score, 1.0)
    
    # Determine risk level
    if score >= 0.7:
        risk = "HIGH"
        confidence = score
    elif score >= 0.4:
        risk = "MEDIUM"
        confidence = score
    else:
        risk = "LOW"
        confidence = 1 - score
    
    return {
        "risk": risk,
        "confidence": round(confidence, 2),
        "reasons": reasons[:10],
        "threat_intel_score": round(graph_score * 0.5, 2),
        "total_score": round(score, 2),
        "infra_gnn_score": round(graph_score, 2),
        "cluster_probability": 0.0,
        "campaign_id": None,
        "is_zero_day": False,
        "gnn_enabled": False
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
    )
