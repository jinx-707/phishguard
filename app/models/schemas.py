"""
Pydantic schemas for API request/response models.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import re
from urllib.parse import urlparse


class RiskLevel(str, Enum):
    """Risk level enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ScanRequest(BaseModel):
    """Request schema for threat scanning."""
    text: Optional[str] = Field(None, description="Text content to scan")
    url: Optional[str] = Field(None, description="URL to scan")
    html: Optional[str] = Field(None, description="HTML content to scan")
    meta: Optional[Dict] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize URL."""
        if v is None:
            return v
        try:
            parsed = urlparse(v)
            if not parsed.scheme:
                raise ValueError("URL must include a scheme (http/https)")
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("URL must use http or https scheme")
            return v.lower()
        except Exception as e:
            raise ValueError(f"Invalid URL: {str(e)}")
    
    @field_validator('text', 'html')
    @classmethod
    def validate_content(cls, v: Optional[str]) -> Optional[str]:
        """Validate content length."""
        if v is not None and len(v) > 1000000:  # 1MB limit
            raise ValueError("Content too large (max 1MB)")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://example.com",
                "meta": {"source": "api"}
            }
        }
    }


class ScanResponse(BaseModel):
    """Response schema for threat scan results."""
    scan_id: str = Field(..., description="Unique scan identifier")
    risk: RiskLevel = Field(..., description="Risk level assessment")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasons: List[str] = Field(default_factory=list, description="Explanation reasons")
    graph_score: float = Field(..., ge=0.0, le=1.0, description="Graph-based score")
    model_score: float = Field(..., ge=0.0, le=1.0, description="ML model score")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Scan timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "scan_id": "abc123",
                "risk": "HIGH",
                "confidence": 0.95,
                "reasons": ["Known malicious domain", "High centrality score"],
                "graph_score": 0.8,
                "model_score": 0.9,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    }


class FeedbackRequest(BaseModel):
    """Request schema for user feedback on scans."""
    scan_id: str = Field(..., description="Scan identifier")
    user_flag: bool = Field(..., description="User's flag (true = malicious, false = benign)")
    corrected_label: Optional[str] = Field(None, description="Corrected label if different")
    comment: Optional[str] = Field(None, description="User comment")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "scan_id": "abc123",
                "user_flag": True,
                "corrected_label": "HIGH",
                "comment": "This is clearly a phishing site"
            }
        }
    }


class FeedbackResponse(BaseModel):
    """Response schema for feedback submission."""
    feedback_id: str = Field(..., description="Feedback identifier")
    status: str = Field(..., description="Feedback status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Application version")
    database: Optional[str] = Field(None, description="Database status")
    redis: Optional[str] = Field(None, description="Redis status")


class TokenData(BaseModel):
    """JWT token data schema."""
    sub: str = Field(..., description="Subject (user identifier)")
    exp: datetime = Field(..., description="Expiration time")
    roles: List[str] = Field(default_factory=list, description="User roles")


class User(BaseModel):
    """User schema."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    roles: List[str] = Field(default_factory=list)


class UserInDB(User):
    """User database schema with hashed password."""
    hashed_password: str


class Token(BaseModel):
    """JWT token response schema."""
    access_token: str
    token_type: str = "bearer"


class ThreatIntelResponse(BaseModel):
    """Response schema for threat intelligence data."""
    domain: str
    risk_score: float
    is_malicious: bool
    related_ips: List[str]
    related_domains: List[str]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    tags: List[str] = Field(default_factory=list)
    meta: Dict = Field(default_factory=dict)


class ModelHealthResponse(BaseModel):
    """Response schema for model health metrics."""
    model_name: str
    uptime: float
    total_predictions: int
    error_rate: float
    average_latency_ms: float
    last_retrain: Optional[datetime]
