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
from app.services.scoring import compute_final_score
from app.services.graph import GraphService

router = APIRouter()
logger = structlog.get_logger(__name__)
security = HTTPBearer()


@router.post("/scan", response_model=ScanResponse)
async def scan(
    request: ScanRequest,
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
    redis = await get_redis_client()
    cached_result = await redis.get(f"scan:{input_hash}")
    if cached_result:
        logger.info("Cache hit", input_hash=input_hash)
        return ScanResponse(**json.loads(cached_result))
    
    # Determine input type and content
    content = request.text or request.url or request.html or ""
    
    # Get graph service
    graph_service = GraphService()
    
    # Get ML model score (simulated for MVP)
    model_score = await simulate_ml_inference(content, request.url)
    
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
async def model_health():
    """
    Get model health metrics.
    """
    # Aggregate metrics from database/logs
    metrics = await get_model_metrics()
    
    return ModelHealthResponse(**metrics)


# Helper functions (to be implemented in services)
async def simulate_ml_inference(content: str, url: Optional[str]) -> float:
    """Simulate ML inference (replace with actual ML service call)."""
    # In production, this would call an external ML service
    # For MVP, return a random score based on content
    import random
    return round(random.uniform(0.1, 0.9), 2)


async def persist_scan(scan_id: str, input_hash: str, request: ScanRequest, response: ScanResponse):
    """Persist scan to database."""
    # This would use SQLAlchemy to insert into the scans table
    # Implemented in database service
    pass


async def persist_feedback(
    feedback_id: str,
    scan_id: str,
    user_flag: bool,
    corrected_label: Optional[str],
    comment: Optional[str],
):
    """Persist feedback to database."""
    # This would use SQLAlchemy to insert into the feedback table
    # Implemented in database service
    pass


async def query_domain_intel(domain: str) -> Optional[dict]:
    """Query domain intelligence from database."""
    # For MVP, return mock data
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
    # This would aggregate metrics from the model_metadata table
    return {
        "model_name": "threat-detector-v1",
        "uptime": 99.9,
        "total_predictions": 10000,
        "error_rate": 0.01,
        "average_latency_ms": 150.0,
        "last_retrain": None,
    }
