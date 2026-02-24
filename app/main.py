"""
Main FastAPI application entry point.
"""
import asyncio
import logging
import uuid
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from app.config import settings
from app.api.routes import router as api_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.database import init_db, close_db, async_session_maker
from app.services.redis import init_redis, close_redis, get_redis_client
from app.services.scoring import compute_final_score
from app.services.graph import GraphService
from app.services.threat_graph_engine import ThreatGraphEngine
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

# Global ThreatGraphEngine instance for Person 3
threat_engine: Optional[ThreatGraphEngine] = None


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
    global threat_engine
    
    # Startup
    logger.info("Starting application", 
                app_name=settings.APP_NAME, 
                version=settings.APP_VERSION,
                environment=settings.ENVIRONMENT)
    logger.info(f"Redis URL: {settings.REDIS_URL}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'local'}")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Initialize Redis
    await init_redis()
    logger.info("Redis initialized")
    
    # Initialize threat feeds (if enabled)
    try:
        from app.services.threat_feeds import get_feed_aggregator
        feed_aggregator = get_feed_aggregator()
        feed_status = feed_aggregator.get_status()
        enabled_feeds = [f["name"] for f in feed_status if f["enabled"]]
        if enabled_feeds:
            logger.info(f"Threat feeds enabled: {enabled_feeds}")
            # Initial fetch in background
            asyncio.create_task(fetch_initial_feeds())
        else:
            logger.info("No threat feeds enabled (set OPENPHISH_ENABLED=true etc.)")
    except Exception as e:
        logger.warning(f"Threat feeds initialization failed: {e}")
    
    # Initialize Person 3 ThreatGraphEngine
    try:
        redis_client = await get_redis_client()
        from app.services.database import engine
        threat_engine = ThreatGraphEngine(db_pool=engine, redis_client=redis_client)
        await threat_engine.startup()
        logger.info("Person 3 ThreatGraphEngine initialized")
    except Exception as e:
        logger.warning(f"ThreatGraphEngine initialization failed (will use fallback): {e}")
        threat_engine = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    if threat_engine:
        await threat_engine.shutdown()
    await close_redis()
    await close_db()
    logger.info("Application shutdown complete")


async def fetch_initial_feeds():
    """Fetch initial threat feeds in background after startup."""
    try:
        from app.services.threat_feeds import get_feed_aggregator
        await asyncio.sleep(5)  # Wait for app to fully start
        aggregator = get_feed_aggregator()
        indicators = await aggregator.fetch_all()
        logger.info(f"Initial threat feeds fetched: {len(indicators)} indicators")
    except Exception as e:
        logger.warning(f"Initial feed fetch failed: {e}")


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
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }


# ============================================
# Chrome Extension Compatible Endpoints
# (Root level for extension compatibility)
# ============================================

@app.post("/scan")
async def scan_chrome_extension(request: ChromeExtensionScanRequest):
    """
    Chrome Extension scan endpoint.
    Compatible with the PhishGuard Chrome Extension.
    """
    from app.services.redis import get_redis_client
    
    domain = request.url
    if not domain.startswith('http'):
        domain = f'http://{domain}'
    from urllib.parse import urlparse
    domain = urlparse(domain).netloc or urlparse(domain).path
    
    logger.info(f"Scanning: {domain}")
    
    # Check cache
    redis = await get_redis_client()
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
        from app.services.database import get_db_session
        from app.models.db import RiskLevelEnum
        async for session in get_db_session():
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
            session.add(db_scan)
            await session.commit()
            break
    except Exception as e:
        logger.error("Failed to persist scan", error=str(e))
    
    logger.info(f"Result: {risk_result['risk']} ({risk_result['confidence']})")
    
    return risk_result


@app.post("/feedback")
async def submit_feedback(data: FeedbackRequest):
    """
    Feedback endpoint for Chrome Extension.
    """
    logger.info(f"Feedback received: {data.type or 'unknown'}")
    
    # Persist feedback
    try:
        from app.services.database import get_db_session
        async for session in get_db_session():
            db_feedback = DBFeedback(
                scan_id=data.scan_id or str(uuid.uuid4()),
                user_flag=data.user_flag or False,
                corrected_label=data.corrected_label,
                comment=data.comment,
            )
            session.add(db_feedback)
            await session.commit()
            break
    except Exception as e:
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


# ============================================
# Auth Endpoints (for Frontend Dashboard)
# ============================================

@app.post("/auth/login")
async def login(request: Request):
    """
    Login endpoint for dashboard.
    """
    # Simple demo auth - in production use proper JWT
    body = await request.body()
    import urllib.parse
    data = urllib.parse.parse_qs(body.decode())
    username = data.get('username', [''])[0]
    password = data.get('password', [''])[0]
    
    # Demo credentials
    if username == "admin" and password == "admin123":
        # Generate simple token (in production use proper JWT)
        token = f"demo_token_{username}_{datetime.utcnow().timestamp()}"
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "username": username,
                "full_name": "Admin User",
                "role": "admin"
            }
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ============================================
# Dashboard Endpoints (for Frontend)
# ============================================

@app.get("/dashboard/summary")
async def get_dashboard_summary():
    """Dashboard summary data."""
    return {
        "total_threats_blocked_today": 142,
        "active_campaigns": 8,
        "zero_day_detections": 3,
        "endpoints_protected": 1524,
        "top_targeted_brands": [
            {"brand": "Microsoft", "attempts": 45},
            {"brand": "PayPal", "attempts": 32},
            {"brand": "Amazon", "attempts": 28},
            {"brand": "Apple", "attempts": 21},
            {"brand": "Google", "attempts": 18}
        ],
        "recent_activity": [
            {"time": "2 min ago", "event": "paypal-fake.com blocked", "severity": "high"},
            {"time": "5 min ago", "event": "amazon-verify.net blocked", "severity": "high"},
            {"time": "12 min ago", "event": "microsoft-login.co blocked", "severity": "medium"}
        ]
    }


@app.get("/dashboard/live-threats")
async def get_live_threats(limit: int = 20):
    """Live threat feed."""
    return [
        {
            "id": "1",
            "domain": "paypal-verify-account.com",
            "risk_score": 0.95,
            "confidence": 0.92,
            "detection_source": "GNN",
            "campaign_id": "campaign_001",
            "timestamp": datetime.utcnow().isoformat()
        },
        {
            "id": "2",
            "domain": "amazon-order-confirm.net",
            "risk_score": 0.88,
            "confidence": 0.85,
            "detection_source": "INFRA",
            "campaign_id": "campaign_002",
            "timestamp": datetime.utcnow().isoformat()
        }
    ][:limit]


@app.get("/dashboard/campaigns")
async def get_campaigns():
    """Campaign intelligence."""
    return [
        {
            "campaign_id": "campaign_001",
            "cluster_size": 12,
            "avg_risk_score": 0.85,
            "shared_ip": "192.168.1.100",
            "shared_cert": "*.ssl.com",
            "domains": ["paypal-verify.com", "paypal-secure.net", "paypal-login.org"],
            "first_seen": "2024-01-15T00:00:00Z",
            "growth_trend": "growing"
        }
    ]


@app.get("/dashboard/graph")
async def get_graph_data():
    """Infrastructure graph data."""
    return {
        "nodes": [
            {"id": "1", "label": "paypal-verify.com", "type": "domain", "risk": 0.9},
            {"id": "2", "label": "192.168.1.100", "type": "ip", "risk": 0.85},
            {"id": "3", "label": "amazon-order.net", "type": "domain", "risk": 0.7}
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "3", "target": "2"}
        ]
    }


@app.get("/dashboard/endpoint-stats")
async def get_endpoint_stats():
    """Endpoint statistics."""
    return {
        "total_endpoints": 1524,
        "scans_per_minute": 45,
        "blocked_attempts": 8923,
        "override_rate": 0.08,
        "offline_detections": 12
    }


@app.get("/dashboard/risk-trends")
async def get_risk_trends(days: int = 7):
    """Risk trend analytics."""
    return [
        {"date": "2024-01-15", "blocked_count": 120, "zero_day_count": 2, "new_campaigns": 1},
        {"date": "2024-01-16", "blocked_count": 145, "zero_day_count": 4, "new_campaigns": 2},
        {"date": "2024-01-17", "blocked_count": 98, "zero_day_count": 1, "new_campaigns": 0}
    ][:days]


@app.get("/dashboard/investigate/{domain}")
async def investigate_domain(domain: str):
    """Domain investigation."""
    return {
        "domain": domain,
        "risk_score": 0.75,
        "nlp_explanation": "Contains urgency keywords typical of phishing",
        "dom_indicators": ["Hidden input fields detected", "External links to untrusted domains"],
        "infra_gnn_score": 0.68,
        "campaign_id": "campaign_001",
        "domain_age_days": 5,
        "whois_summary": {
            "registrar": "NameCheap",
            "created_date": "2024-01-10"
        },
        "related_domains": [
            {"domain": "paypal-secure.net", "relation": "same_campaign", "risk": 0.9}
        ]
    }


# Risk calculation for Chrome Extension
async def calculate_risk(data: dict, domain: str) -> dict:
    """Calculate comprehensive risk score using Person 3 ThreatGraphEngine."""
    
    # Try to use Person 3 ThreatGraphEngine if available
    if threat_engine and threat_engine._started:
        try:
            result = await threat_engine.analyze(domain)
            threat_result = result.to_dict()
            
            combined_score = (threat_result.get("infrastructure_risk_score", 0) + threat_result.get("reputation_risk_score", 0)) / 2
            
            return {
                "risk": "HIGH" if combined_score >= 0.7 else "MEDIUM" if combined_score >= 0.4 else "LOW",
                "confidence": round(combined_score, 2),
                "reasons": threat_result.get("reasons", []),
                "threat_intel_score": round(threat_result.get("reputation_risk_score", 0), 2),
                "total_score": round(combined_score, 2),
                "infra_gnn_score": round(threat_result.get("infrastructure_risk_score", 0), 2),
                "cluster_probability": threat_result.get("cluster_probability", 0),
                "campaign_id": threat_result.get("campaign_id"),
                "is_zero_day": threat_result.get("cluster_probability", 0) > 0.5,
                "gnn_enabled": True
            }
        except Exception as e:
            logger.warning(f"ThreatGraphEngine analysis failed, falling back: {e}")
    
    # Fallback to original calculation
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
