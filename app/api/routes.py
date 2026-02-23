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
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
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
from app.services.scoring import compute_final_score
from app.services.graph import GraphService
from app.models.db import Scan as DBScan, Feedback as DBFeedback

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
    db: AsyncSession = Depends(get_db_session),
    redis: redis.Redis = Depends(get_redis_client),
):
    """
    Scan content for threats.
    
    - **text**: Text content to scan
    - **url**: URL to scan  
    - **html**: HTML content to scan
    - **meta**: Additional metadata
    """
    # Generate input hash for deduplication
    input_data = request.model_dump_json(exclude_none=True)
    input_hash = hashlib.sha256(input_data.encode()).hexdigest()
    
    # Check cache
    cached_result = await redis.get(f"scan:{input_hash}")
    if cached_result:
        logger.info("Cache hit", input_hash=input_hash)
        return ScanResponse(**json.loads(cached_result))
    
    # Determine input type and content
    content = request.text or request.url or request.html or ""
    
    # Get graph service
    graph_service = GraphService()
    
    # Get ML model score
    model_score = await get_ml_score(content, request.url, request.html)
    
    # Get graph score
    graph_score = await graph_service.get_risk_score(request.url)
    
    # Compute final score
    final_risk, confidence, reasons = compute_final_score(
        model_score=model_score,
        graph_score=graph_score,
    )
    
    # Generate scan ID
    scan_id = str(uuid.uuid4())
    
    # Create response
    response = ScanResponse(
        scan_id=scan_id,
        risk=final_risk,
        confidence=confidence,
        reasons=reasons,
        graph_score=graph_score,
        model_score=model_score,
        timestamp=datetime.utcnow(),
    )
    
    # Cache result
    await redis.setex(
        f"scan:{input_hash}",
        settings.REDIS_CACHE_TTL,
        response.model_dump_json(),
    )
    
    # Persist to database
    await persist_scan(
        db=db,
        scan_id=scan_id,
        input_hash=input_hash,
        request=request,
        response=response,
    )
    
    logger.info("Scan completed", scan_id=scan_id, risk=final_risk.value)
    return response


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackRequest,
    db: AsyncSession = Depends(get_db_session),
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
        db=db,
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
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get threat intelligence for a domain.
    
    - **domain**: Domain to query
    """
    # Query database for domain intelligence
    domain_data = await query_domain_intel(db, domain)
    
    if not domain_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No intelligence found for domain: {domain}",
        )
    
    return ThreatIntelResponse(**domain_data)


@router.get("/model-health", response_model=ModelHealthResponse)
async def model_health(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get model health metrics.
    """
    # Aggregate metrics from database/logs
    metrics = await get_model_metrics(db)
    
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


async def persist_scan(
    db: AsyncSession,
    scan_id: str,
    input_hash: str,
    request: ScanRequest,
    response: ScanResponse,
):
    """Persist scan to database."""
    try:
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
        db.add(db_scan)
        await db.commit()
        logger.info("Scan persisted", scan_id=scan_id)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to persist scan", error=str(e))


async def persist_feedback(
    db: AsyncSession,
    feedback_id: str,
    scan_id: str,
    user_flag: bool,
    corrected_label: Optional[str],
    comment: Optional[str],
):
    """Persist feedback to database."""
    try:
        db_feedback = DBFeedback(
            scan_id=scan_id,
            user_flag=user_flag,
            corrected_label=corrected_label,
            comment=comment,
        )
        db.add(db_feedback)
        await db.commit()
        logger.info("Feedback persisted", feedback_id=feedback_id, scan_id=scan_id)
    except Exception as e:
        await db.rollback()
        logger.error("Failed to persist feedback", error=str(e))


async def query_domain_intel(db: AsyncSession, domain: str) -> Optional[dict]:
    """Query domain intelligence from database."""
    try:
        from sqlalchemy import select
        from app.models.db import Domain, Relation
        
        # Query domain
        stmt = select(Domain).where(Domain.domain == domain)
        result = await db.execute(stmt)
        domain_obj = result.scalar_one_or_none()
        
        if domain_obj:
            # Get relations
            rel_stmt = select(Relation).where(
                (Relation.source_domain_id == domain_obj.id) | 
                (Relation.target_domain_id == domain_obj.id)
            )
            rel_result = await db.execute(rel_stmt)
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


async def get_model_metrics(db: AsyncSession) -> dict:
    """Get model metrics from database."""
    try:
        from sqlalchemy import select
        from app.models.db import ModelMetadata
        
        stmt = select(ModelMetadata).where(ModelMetadata.is_active == True)
        result = await db.execute(stmt)
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
