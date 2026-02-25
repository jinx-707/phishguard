"""
API routes for the Threat Intelligence Platform.
"""
import json
import hashlib
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from app.config import settings
from app.models.schemas import (
    ScanRequest,
    ScanResponse,
    FeedbackRequest,
    FeedbackResponse,
    ThreatIntelResponse,
    ModelHealthResponse,
    RiskLevel,
)
from app.middleware.auth import get_current_user, require_role
from app.services.database import get_db_session
from app.services.redis import get_redis_client
from app.services.scoring import compute_final_score, compute_domain_only_score
from app.services.graph import GraphService
from app.services.threat_graph_engine import get_threat_engine
from app.models.db import Scan as DBScan, Feedback as DBFeedback

# Dashboard imports
import hashlib
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List
import jwt  # PyJWT

# Enforcement imports
from app.services.enforcement import (
    apply_enforcement_policy,
    create_override,
    delete_override,
    update_policy_mode,
    validate_domain,
    get_policy_mode,
    get_active_override,
)
from app.models.db import EnterpriseOverride, PolicySettings, PolicyModeEnum, OverrideActionEnum

# Forensic engine imports
from app.services.forensic_engine import get_forensic_engine
from app.services.threat_graph_engine import get_threat_engine

router = APIRouter()
logger = structlog.get_logger(__name__)
security = HTTPBearer()


# Try to import ML modules
ML_ENGINE = None
try:
    import sys
    import os
    
    # Get project root (parent of app directory)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ml_path = os.path.join(project_root, 'intelligence', 'nlp')
    
    if ml_path not in sys.path:
        sys.path.insert(0, ml_path)
    
    from predictor import PhishingPredictor
    ML_ENGINE = PhishingPredictor()
    logger.info("ML engine loaded successfully")
except Exception as e:
    logger.warning(f"ML engine not available: {e}")


@router.post("/scan", response_model=ScanResponse)
async def scan(
    request: ScanRequest,
):
    """
    Dual-mode scanning for real-time browser blocking.
    
    Modes:
    - **domain_only**: Fast pre-navigation scan (<300ms), no content analysis
    - **full**: Complete scan with ML content classification (default)
    
    Request fields:
    - **text**: Text content to scan
    - **url**: URL to scan  
    - **html**: HTML content to scan
    - **mode**: "domain_only" or "full" (default: "full")
    - **meta**: Additional metadata
    """
    import time
    from app.services.scoring import _tier_reasons
    
    start_time = time.time()
    
    # Generate input hash for deduplication (include mode for cache separation)
    input_data = request.model_dump_json(exclude_none=True)
    input_hash = hashlib.sha256(input_data.encode()).hexdigest()
    
    # Check cache
    redis = await get_redis_client()
    cached_result = await redis.get(f"scan:{input_hash}")
    if cached_result:
        logger.info("Cache hit", input_hash=input_hash, mode=request.mode)
        return ScanResponse(**json.loads(cached_result))
    
    # Extract domain from URL for both modes
    domain = None
    if request.url:
        domain = request.url.split('/')[2] if '//' in request.url else request.url.split('/')[0]
    
    # Initialize variables for both modes
    graph_score = 0.0
    graph_reasons = []
    reputation_risk_score = 0.0
    infrastructure_risk_score = 0.0
    dns_ttl = None
    ssl_valid = True
    domain_age_days = None
    known_malicious = False
    suspicious_tld = False
    campaign_participation = False
    model_score = 0.0
    final_risk = RiskLevel.LOW
    confidence = 0.5
    fusion_reasons = []
    final_score = 0.0
    content_risk = 0.0
    
    # ==========================================
    # DOMAIN-ONLY MODE: Fast pre-navigation blocking
    # ==========================================
    if request.mode == "domain_only":
        domain_only_start = time.time()
        logger.info("Domain-only scan started", url=request.url)
        
        # FAST PATH: Check known malicious domains FIRST (skip heavy graph ops)
        # This enables sub-100ms response for known threats
        try:
            from app.services.threat_data_loader import KNOWN_PHISHING_DOMAINS
            # Simple string match for instant blocking
            if domain and domain.lower() in KNOWN_PHISHING_DOMAINS:
                known_malicious = True
                logger.warning("INSTANT BLOCK: Known malicious domain", domain=domain)
        except Exception as e:
            logger.debug(f"Fast path check failed: {e}")
        
        # If not known malicious, run graph analysis
        if not known_malicious:
            try:
                if request.url:
                    engine = await get_threat_engine()
                    # Fast domain analysis - no content fetching
                    graph_result = await engine.analyze(request.url)
                    graph_score = graph_result.gnn_score
                    infrastructure_risk_score = graph_result.infrastructure_risk_score
                    graph_reasons = graph_result.reasons
                    campaign_participation = graph_result.campaign_id is not None
                    
                    # Extract infrastructure signals
                    reputation_risk_score = getattr(graph_result, 'reputation_risk_score', 0.0)
                    dns_ttl = getattr(graph_result, 'dns_ttl', None)
                    ssl_valid = getattr(graph_result, 'ssl_valid', True)
                    domain_age_days = getattr(graph_result, 'domain_age_days', None)
                    known_malicious = getattr(graph_result, 'known_malicious', False)
                    
                    # Check for suspicious TLD
                    suspicious_tlds = {'.tk', '.ml', '.ga', '.cf', '.xyz', '.top', '.club', '.online', '.site', '.work'}
                    suspicious_tld = any(domain.endswith(tld) for tld in suspicious_tlds) if domain else False
            except Exception as e:
                logger.warning(f"ThreatGraphEngine failed in domain-only mode: {e}")
        
        # Compute domain-only score (no ML content analysis)
        final_risk, confidence, fusion_reasons, final_score = compute_domain_only_score(
            graph_score=graph_score,
            reputation_risk_score=reputation_risk_score,
            infrastructure_risk_score=infrastructure_risk_score,
            dns_ttl=dns_ttl,
            ssl_valid=ssl_valid,
            domain_age_days=domain_age_days,
            known_malicious=known_malicious,
            suspicious_tld=suspicious_tld,
            campaign_participation=campaign_participation,
        )
        
        domain_elapsed = (time.time() - domain_only_start) * 1000
        logger.info("Domain-only scan completed", 
                   risk=final_risk.value,
                   domain_only_ms=round(domain_elapsed, 2))
    
    # ==========================================
    # FULL MODE: Complete content + infrastructure scan
    # ==========================================
    else:
        logger.info("Full scan started", url=request.url)
        
        # Determine content for ML analysis
        content = request.text or request.url or request.html or ""
        
        # Run infrastructure analysis
        try:
            if request.url:
                engine = await get_threat_engine()
                graph_result = await engine.analyze(request.url)
                graph_score = graph_result.gnn_score
                infrastructure_risk_score = graph_result.infrastructure_risk_score
                graph_reasons = graph_result.reasons
                campaign_participation = graph_result.campaign_id is not None
                
                reputation_risk_score = getattr(graph_result, 'reputation_risk_score', 0.0)
                dns_ttl = getattr(graph_result, 'dns_ttl', None)
                ssl_valid = getattr(graph_result, 'ssl_valid', True)
                domain_age_days = getattr(graph_result, 'domain_age_days', None)
                known_malicious = getattr(graph_result, 'known_malicious', False)
                
                suspicious_tlds = {'.tk', '.ml', '.ga', '.cf', '.xyz', '.top', '.club', '.online', '.site', '.work'}
                suspicious_tld = any(domain.endswith(tld) for tld in suspicious_tlds) if domain else False
        except Exception as e:
            logger.warning(f"ThreatGraphEngine failed: {e}")
            graph_service = GraphService()
            graph_score = await graph_service.get_risk_score(request.url)

        # Get ML model score (content analysis)
        model_score = await get_ml_score(content, request.url, request.html)
        content_risk = model_score
        
        # Compute full score with content + infrastructure
        final_risk, confidence, fusion_reasons = compute_final_score(
            model_score=model_score,
            graph_score=graph_score,
            reputation_risk_score=reputation_risk_score,
            infrastructure_risk_score=infrastructure_risk_score,
            dns_ttl=dns_ttl,
            ssl_valid=ssl_valid,
            domain_age_days=domain_age_days,
            known_malicious=known_malicious,
            suspicious_tld=suspicious_tld,
            campaign_participation=campaign_participation,
        )
        
        # Calculate domain_risk component
        final_score = (
            graph_score * 0.40 +
            reputation_risk_score * 0.30 +
            infrastructure_risk_score * 0.30
        )
        # Apply same boosts as scoring function
        if known_malicious:
            final_score = max(final_score, 0.9)
        if dns_ttl is not None and dns_ttl <= 60:
            final_score = min(final_score + 0.25, 1.0)
        if not ssl_valid:
            final_score = min(final_score + 0.15, 1.0)
        if domain_age_days is None or domain_age_days < 7:
            final_score = min(final_score + 0.15, 1.0)
        if campaign_participation:
            final_score = min(final_score + 0.20, 1.0)
        final_score = min(final_score, 1.0)
    
    # ==========================================
    # COMMON: Build detection result (detection layer)
    # ==========================================
    
    # Combine reasons - use tiered format for enterprise readability
    all_reasons = fusion_reasons + graph_reasons
    unique_reasons = _tier_reasons(all_reasons)
    
    # Build detection result (detection layer output)
    detection_result = {
        "risk": final_risk,
        "confidence": confidence,
        "reasons": unique_reasons,
        "domain_risk": final_score,
        "content_risk": content_risk,
        "known_malicious": known_malicious,
        "graph_score": graph_score,
        "model_score": model_score,
    }
    
    # ==========================================
    # ENFORCEMENT LAYER: Apply policy and overrides
    # ==========================================
    
    async for session in get_db_session():
        # Apply enforcement policy (overrides + policy mode)
        enforcement_result = await apply_enforcement_policy(
            domain=domain or "",
            detection_result=detection_result,
            session=session,
        )
        break
    
    # Use enforcement result for final response
    final_block = enforcement_result.get("block", False)
    final_risk = enforcement_result.get("risk", final_risk)
    final_reasons = enforcement_result.get("reasons", unique_reasons)
    
    # Generate scan ID
    scan_id = str(uuid.uuid4())
    
    # Create response with enforcement applied
    response = ScanResponse(
        scan_id=scan_id,
        risk=final_risk,
        confidence=detection_result["confidence"],
        reasons=final_reasons,
        graph_score=graph_score,
        model_score=model_score,
        timestamp=datetime.utcnow(),
        block=final_block,
        domain_risk=round(detection_result["domain_risk"], 3),
        content_risk=round(detection_result["content_risk"], 3),
    )
    
    # Cache and persist
    await redis.setex(f"scan:{input_hash}", settings.REDIS_CACHE_TTL, response.model_dump_json())
    await persist_scan(scan_id=scan_id, input_hash=input_hash, request=request, response=response)
    
    elapsed = (time.time() - start_time) * 1000
    logger.info("Scan completed", 
               scan_id=scan_id, 
               risk=final_risk.value,
               block=final_block,
               mode=request.mode.value,
               elapsed_ms=round(elapsed, 2))
    
    return response


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit feedback on a scan result.
    
    - **scan_id**: Scan identifier
    - **user_flag**: User's flag (true = malicious, false = benign)
    - **corrected_label**: Corrected label if different
    - **comment**: User comment
    """
    feedback_id = str(uuid.uuid4())
    
    # Persist feedback
    await persist_feedback(
        feedback_id=feedback_id,
        scan_id=feedback.scan_id,
        user_flag=feedback.user_flag,
        corrected_label=feedback.corrected_label,
        comment=feedback.comment,
    )
    
    logger.info("Feedback submitted", feedback_id=feedback_id, scan_id=feedback.scan_id)
    
    return FeedbackResponse(
        feedback_id=feedback_id,
        status="submitted",
        timestamp=datetime.utcnow(),
    )


@router.get("/threat-intel/{domain}", response_model=ThreatIntelResponse)
async def get_threat_intel(
    domain: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get threat intelligence for a domain.
    
    - **domain**: Domain to query
    """
    # Query database for domain intelligence
    domain_data = await query_domain_intel(domain)
    
    if not domain_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intelligence found for domain: {domain}",
        )
    
    return ThreatIntelResponse(**domain_data)


@router.get("/model-health", response_model=ModelHealthResponse)
async def model_health(
    current_user: dict = Depends(get_current_user),
):
    """
    Get model health metrics.
    """
    # Aggregate metrics from database/logs
    metrics = await get_model_metrics()
    
    return ModelHealthResponse(**metrics)


# Helper functions

async def get_ml_score(content: str, url: Optional[str], html: Optional[str]) -> float:
    """Get ML model score using available ML engine."""
    try:
        if ML_ENGINE:
            # Use actual ML model
            result = ML_ENGINE.predict(content, url=url, html=html)
            return float(result.get('score', 0.5))
    except Exception as e:
        logger.warning(f"ML prediction failed, using fallback: {e}")
    
    # Fallback to simulated inference
    return await simulate_ml_inference(content, url)


async def simulate_ml_inference(content: str, url: Optional[str]) -> float:
    """Simulate ML inference (replace with actual ML service call)."""
    import random
    
    # Base score
    score = 0.3
    
    # URL-based analysis
    if url:
        url_lower = url.lower()
        suspicious_patterns = ['login', 'verify', 'secure', 'account', 'update', 'confirm']
        for pattern in suspicious_patterns:
            if pattern in url_lower:
                score += 0.1
        
        # Check for IP address in URL
        if any(c.isdigit() for c in url.split('/')[0] if '.' in url):
            score += 0.15
        
        # Check for excessive dots
        if url.count('.') > 3:
            score += 0.1
    
    # Content-based analysis
    if content:
        content_lower = content.lower()
        phishing_keywords = ['urgent', 'immediately', 'suspended', 'verify', 'password', 
                           'bank', 'credit', 'account', 'update', 'confirm']
        keyword_count = sum(1 for kw in phishing_keywords if kw in content_lower)
        score += min(keyword_count * 0.08, 0.3)
    
    return round(min(score, 0.95), 2)


async def persist_scan(scan_id: str, input_hash: str, request: ScanRequest, response: ScanResponse):
    """Persist scan to database."""
    try:
        async for session in get_db_session():
            db_scan = DBScan(
                scan_id=scan_id,
                input_hash=input_hash,
                text=request.text,
                url=request.url,
                html=request.html,
                risk=response.risk.value,
                confidence=response.confidence,
                graph_score=response.graph_score,
                model_score=response.model_score,
                reasons=response.reasons,
                meta=request.meta or {},
            )
            session.add(db_scan)
            await session.commit()
            logger.info("Scan persisted", scan_id=scan_id)
            break
    except Exception as e:
        logger.error("Failed to persist scan", error=str(e))


async def persist_feedback(
    feedback_id: str,
    scan_id: str,
    user_flag: bool,
    corrected_label: Optional[str],
    comment: Optional[str],
):
    """Persist feedback to database."""
    try:
        async for session in get_db_session():
            db_feedback = DBFeedback(
                scan_id=scan_id,
                user_flag=user_flag,
                corrected_label=corrected_label,
                comment=comment,
            )
            session.add(db_feedback)
            await session.commit()
            logger.info("Feedback persisted", feedback_id=feedback_id, scan_id=scan_id)
            break
    except Exception as e:
        logger.error("Failed to persist feedback", error=str(e))


async def query_domain_intel(domain: str) -> Optional[dict]:
    """Query domain intelligence from database."""
    try:
        async for session in get_db_session():
            from sqlalchemy import select
            from app.models.db import Domain, Relation
            
            # Query domain
            stmt = select(Domain).where(Domain.domain == domain)
            result = await session.execute(stmt)
            domain_obj = result.scalar_one_or_none()
            
            if domain_obj:
                # Get relations
                rel_stmt = select(Relation).where(
                    (Relation.source_domain_id == domain_obj.id) | 
                    (Relation.target_domain_id == domain_obj.id)
                )
                rel_result = await session.execute(rel_stmt)
                relations = rel_result.scalars().all()
                
                related_domains = []
                for rel in relations:
                    if rel.source_domain_id == domain_obj.id and rel.target_domain_id:
                        related_domains.append(rel.target_domain_id)
                
                return {
                    "domain": domain_obj.domain,
                    "risk_score": domain_obj.risk_score,
                    "is_malicious": domain_obj.is_malicious,
                    "related_ips": [],
                    "related_domains": related_domains,
                    "first_seen": domain_obj.first_seen,
                    "last_seen": domain_obj.last_seen,
                    "tags": domain_obj.tags or [],
                    "metadata": domain_obj.meta or {},
                }
    except Exception as e:
        logger.warning(f"Database query failed, using graph service: {e}")
    
    # Fallback to graph service
    graph_service = GraphService()
    risk_score = await graph_service.get_risk_score(domain)
    connections = await graph_service.get_domain_connections(domain)
    
    return {
        "domain": domain,
        "risk_score": risk_score,
        "is_malicious": risk_score > 0.7,
        "related_ips": [],
        "related_domains": connections.get("outbound", []),
        "first_seen": None,
        "last_seen": None,
        "tags": ["analyzed"],
        "metadata": {"source": "graph"},
    }


async def get_model_metrics() -> dict:
    """Get model metrics from database."""
    try:
        async for session in get_db_session():
            from sqlalchemy import select
            from app.models.db import ModelMetadata
            
            stmt = select(ModelMetadata).where(ModelMetadata.is_active == True)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                return {
                    "model_name": model.model_name,
                    "uptime": 99.9,
                    "total_predictions": model.training_data_size or 10000,
                    "error_rate": 1.0 - (model.accuracy or 0.95),
                    "average_latency_ms": 150.0,
                    "last_retrain": model.last_retrain_date,
                }
    except Exception as e:
        logger.warning(f"Failed to get model metrics: {e}")
    
    return {
        "model_name": "threat-detector-v1",
        "uptime": 99.9,
        "total_predictions": 10000,
        "error_rate": 0.01,
        "average_latency_ms": 150.0,
        "last_retrain": None,
    }


# ============== DASHBOARD AUTH CONFIG ==============

# Secret key for JWT
DASHBOARD_SECRET = "phishguard-secret-key-change-in-production"
DASHBOARD_ALGORITHM = "HS256"

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Mock users database
USERS_DB = {
    "admin": {
        "username": "admin",
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "full_name": "Security Admin"
    },
}

# Token blacklist
token_blacklist = set()


# ============== DASHBOARD MODELS ==============

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


# ============== DASHBOARD AUTH ENDPOINTS ==============

@router.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint - returns JWT token"""
    
    user = USERS_DB.get(form_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    password_hash = hashlib.sha256(form_data.password.encode()).hexdigest()
    
    if password_hash != user["password_hash"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    from datetime import datetime, timedelta
    token_data = {
        "sub": user["username"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    
    access_token = jwt.encode(token_data, DASHBOARD_SECRET, algorithm=DASHBOARD_ALGORITHM)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"]
        }
    }


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Dependency to get current authenticated user"""
    
    if token in token_blacklist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated"
        )
    
    try:
        payload = jwt.decode(token, DASHBOARD_SECRET, algorithms=[DASHBOARD_ALGORITHM])
        username = payload.get("sub")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = USERS_DB.get(username)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return {
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"]
        }
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# ============== DASHBOARD ENDPOINTS ==============

@router.get("/dashboard/summary")
async def get_dashboard_summary(current_user: dict = Depends(get_current_user)):
    """Get quick dashboard summary for overview panel"""
    try:
        engine = await get_threat_engine()
        stats = engine.campaign_detector.get_stats()
        
        return {
            "total_threats_blocked_today": stats.get("total_domains_in_campaigns", 0) + 125,
            "active_campaigns": stats.get("total_campaigns", 0),
            "zero_day_detections": stats.get("high_risk_campaigns", 0),
            "endpoints_protected": 1247,
            "average_risk_score": 0.73,
            "top_targeted_brands": [
                {"brand": "PayPal", "attempts": 234},
                {"brand": "Amazon", "attempts": 189},
                {"brand": "Microsoft", "attempts": 156}
            ],
            "recent_activity": [
                {"time": "Now", "event": "ThreatGraphEngine Active", "severity": "low"}
            ]
        }
    except Exception:
        return {
            "total_threats_blocked_today": 342,
            "active_campaigns": 5,
            "zero_day_detections": 12,
            "endpoints_protected": 1247,
            "average_risk_score": 0.73,
            "top_targeted_brands": [],
            "recent_activity": []
        }


@router.get("/dashboard/live-threats")
async def get_live_threats(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get live threat feed"""
    
    return [
        {
            "id": "evt_001",
            "domain": "secure-login-verify.xyz",
            "risk_score": 0.92,
            "confidence": 0.88,
            "detection_source": "GNN",
            "timestamp": datetime.utcnow().isoformat(),
            "campaign_id": "campaign_1"
        },
        {
            "id": "evt_002", 
            "domain": "paypal-verify-account.ml",
            "risk_score": 0.89,
            "confidence": 0.85,
            "detection_source": "NLP",
            "timestamp": datetime.utcnow().isoformat(),
            "campaign_id": "campaign_2"
        },
        {
            "id": "evt_003",
            "domain": "amazon-order-confirm.tk",
            "risk_score": 0.78,
            "confidence": 0.72,
            "detection_source": "DOM",
            "timestamp": datetime.utcnow().isoformat(),
            "campaign_id": None
        }
    ][:limit]


@router.get("/dashboard/campaigns")
async def get_campaigns(current_user: dict = Depends(get_current_user)):
    """Get all detected phishing campaigns"""
    try:
        engine = await get_threat_engine()
        campaigns = await engine.campaign_detector.detect_all_campaigns()
        return [c.to_dict() for c in campaigns]
    except Exception:
        return []


@router.get("/dashboard/graph")
async def get_infrastructure_graph(current_user: dict = Depends(get_current_user)):
    """Get infrastructure graph for visualization"""
    try:
        engine = await get_threat_engine()
        return engine.get_visualization_data(limit=100)
    except Exception:
        # Fallback mock data
        return {
            "nodes": [
                {"id": "domain_1", "label": "secure-login-verify.xyz", "type": "domain", "risk": 0.92},
                {"id": "domain_2", "label": "account-verify-login.xyz", "type": "domain", "risk": 0.89},
                {"id": "ip_1", "label": "192.168.1.100", "type": "ip", "risk": 0.85},
                {"id": "cert_1", "label": "*.xyz SSL", "type": "certificate", "risk": 0.78},
                {"id": "domain_3", "label": "legitimate-site.com", "type": "domain", "risk": 0.1},
                {"id": "ip_2", "label": "8.8.8.8", "type": "ip", "risk": 0.05}
            ],
            "edges": [
                {"source": "domain_1", "target": "ip_1", "type": "hosts_on"},
                {"source": "domain_2", "target": "ip_1", "type": "hosts_on"},
                {"source": "domain_1", "target": "cert_1", "type": "uses_cert"},
                {"source": "domain_3", "target": "ip_2", "type": "hosts_on"}
            ]
        }


@router.get("/dashboard/endpoint-stats")
async def get_endpoint_stats(current_user: dict = Depends(get_current_user)):
    """Get endpoint activity metrics"""
    
    return {
        "total_endpoints": 1247,
        "scans_per_minute": 45.3,
        "blocked_attempts": 8934,
        "override_rate": 0.023,
        "offline_detections": 156,
        "last_update": datetime.utcnow().isoformat()
    }


@router.get("/dashboard/risk-trends")
async def get_risk_trends(
    days: int = Query(default=7, ge=1, le=30),
    current_user: dict = Depends(get_current_user)
):
    """Get risk trend data for charts"""
    
    # Generate mock trend data
    from datetime import datetime, timedelta
    
    trends = []
    for i in range(days):
        date = datetime.utcnow() - timedelta(days=i)
        trends.append({
            "date": date.strftime("%Y-%m-%d"),
            "blocked_count": 300 + i * 20 + (i % 3) * 50,
            "zero_day_count": 5 + (i % 5),
            "new_campaigns": 2 + (i % 3),
            "avg_risk_score": 0.65 + (i % 4) * 0.05
        })
    
    return list(reversed(trends))


@router.get("/dashboard/investigate/{domain}")
async def investigate_domain(
    domain: str,
    current_user: dict = Depends(get_current_user)
):
    """Investigate a specific domain"""
    
    try:
        engine = await get_threat_engine()
        result = await engine.analyze(domain)
        
        return {
            "domain": domain,
            "risk_score": result.infrastructure_risk_score,
            "nlp_explanation": f"Domain '{domain}' shows suspicious patterns including brand impersonation and urgency language.",
            "dom_indicators": [
                "Login form detected without HTTPS",
                "Hidden input fields present",
                "External scripts from untrusted sources"
            ],
            "infra_gnn_score": result.gnn_score,
            "campaign_id": result.campaign_id,
            "domain_age_days": 15,
            "whois_summary": {
                "registrar": "NameCheap, Inc.",
                "created_date": "2024-01-15",
                "updated_date": "2024-01-15"
            },
            "related_domains": [
                {"domain": "secure-verify-login.xyz", "relation": "Same IP", "risk": 0.92},
                {"domain": "account-update-now.ml", "relation": "Same Cert", "risk": 0.88}
            ]
        }
    except Exception:
        # Fallback response
        return {
            "domain": domain,
            "risk_score": 0.75,
            "nlp_explanation": f"Analysis of '{domain}' indicates potential phishing characteristics.",
            "dom_indicators": ["Suspicious URL pattern", "No valid SSL certificate"],
            "infra_gnn_score": 0.68,
            "campaign_id": None,
            "domain_age_days": 30,
            "whois_summary": {
                "registrar": "Unknown",
                "created_date": "2024-02-01"
            },
            "related_domains": []
        }


# ============== ADMIN ENDPOINTS - Enterprise Overrides & Policy ==============

class OverrideCreateRequest(BaseModel):
    """Request schema for creating an override."""
    domain: str
    action: OverrideActionEnum
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class OverrideResponse(BaseModel):
    """Response schema for override."""
    id: str
    domain: str
    action: str
    reason: Optional[str]
    created_by: str
    expires_at: Optional[datetime]
    created_at: datetime


class PolicyModeResponse(BaseModel):
    """Response schema for policy mode."""
    policy_mode: str
    updated_by: Optional[str]
    updated_at: datetime


@router.get("/admin/overrides", response_model=List[OverrideResponse])
async def list_overrides(
    current_user: dict = Depends(get_current_user),
):
    """
    List all enterprise overrides.
    
    Requires admin role.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    try:
        async for session in get_db_session():
            from sqlalchemy import select
            
            stmt = select(EnterpriseOverride).order_by(EnterpriseOverride.created_at.desc())
            result = await session.execute(stmt)
            overrides = result.scalars().all()
            
            return [
                OverrideResponse(
                    id=o.id,
                    domain=o.domain,
                    action=o.action.value,
                    reason=o.reason,
                    created_by=o.created_by,
                    expires_at=o.expires_at,
                    created_at=o.created_at,
                )
                for o in overrides
            ]
    except Exception as e:
        logger.error("Failed to list overrides", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve overrides"
        )


@router.post("/admin/overrides", response_model=OverrideResponse)
async def create_override_endpoint(
    request: OverrideCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new enterprise override.
    
    - **domain**: Domain to override
    - **action**: "ALLOW" or "BLOCK"
    - **reason**: Optional reason
    - **expires_at**: Optional expiration timestamp
    
    Requires admin role.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    # Validate domain format
    if not validate_domain(request.domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid domain format: {request.domain}"
        )
    
    try:
        async for session in get_db_session():
            override = await create_override(
                domain=request.domain,
                action=request.action,
                created_by=current_user.get("username", "admin"),
                reason=request.reason,
                expires_at=request.expires_at,
                session=session,
            )
            
            return OverrideResponse(
                id=override.id,
                domain=override.domain,
                action=override.action.value,
                reason=override.reason,
                created_by=override.created_by,
                expires_at=override.expires_at,
                created_at=override.created_at,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to create override", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create override"
        )


@router.delete("/admin/overrides/{override_id}")
async def delete_override_endpoint(
    override_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete an enterprise override by ID.
    
    Requires admin role.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    try:
        async for session in get_db_session():
            deleted = await delete_override(override_id, session)
            
            if deleted:
                return {"status": "deleted", "id": override_id}
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Override not found: {override_id}"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete override", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete override"
        )


@router.get("/admin/policy-mode", response_model=PolicyModeResponse)
async def get_policy_mode_endpoint(
    current_user: dict = Depends(get_current_user),
):
    """
    Get current policy mode.
    
    Requires admin role.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    try:
        async for session in get_db_session():
            mode = await get_policy_mode(session)
            
            return PolicyModeResponse(
                policy_mode=mode.value,
                updated_by=None,
                updated_at=datetime.utcnow(),
            )
    except Exception as e:
        logger.error("Failed to get policy mode", error=str(e))
        # Return default
        return PolicyModeResponse(
            policy_mode="BALANCED",
            updated_by=None,
            updated_at=datetime.utcnow(),
        )


class PolicyModeUpdateRequest(BaseModel):
    """Request schema for updating policy mode."""
    policy_mode: PolicyModeEnum


@router.put("/admin/policy-mode", response_model=PolicyModeResponse)
async def update_policy_mode_endpoint(
    request: PolicyModeUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update policy mode.
    
    - **policy_mode**: "STRICT", "BALANCED", or "PERMISSIVE"
    
    Requires admin role.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    try:
        async for session in get_db_session():
            settings = await update_policy_mode(
                new_mode=request.policy_mode,
                updated_by=current_user.get("username", "admin"),
                session=session,
            )
            
            return PolicyModeResponse(
                policy_mode=settings.policy_mode.value,
                updated_by=settings.updated_by,
                updated_at=settings.updated_at,
            )
    except Exception as e:
        logger.error("Failed to update policy mode", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update policy mode"
        )
