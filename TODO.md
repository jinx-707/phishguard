# Endpoint Threat Intelligence Platform - Implementation Plan

## Project Overview
Build a scalable, secure Endpoint Threat Intelligence Platform Core with FastAPI, graph-based analysis, and real-time phishing/Threat detection.

---

## PHASE 1: Project Setup & Core Infrastructure

### 1.1 Initialize Project Structure
- [x] Create directory structure:
  - `app/` - Main application
  - `app/api/` - API routes
  - `app/models/` - Pydantic & DB models
  - `app/services/` - Business logic
  - `app/middleware/` - Custom middleware
  - `app/tasks/` - Celery tasks
  - `tests/` - Unit/integration tests
  - `configs/` - Configuration files
- [x] Initialize with `poetry init` or `pip` for dependency management
- [x] Create virtual environment: `python -m venv venv && source venv/bin/activate`

### 1.2 Create requirements.txt / pyproject.toml
- [x] FastAPI, Uvicorn, Pydantic
- [x] SQLAlchemy, Psycopg2-binary (PostgreSQL)
- [x] Redis-py
- [x] NetworkX (MVP graph)
- [x] Celery
- [x] OpenTelemetry packages
- [x] Security: python-jose, cryptography
- [x] Testing: pytest, httpx

---

## PHASE 2: Database Schema Design (PostgreSQL)

### 2.1 Define SQLAlchemy Models in app/models/db.py
- [x] Create Base = declarative_base()
- [x] Define tables:
  - `scans` - Store scan requests & results
  - `feedback` - User feedback on predictions
  - `domains` - Domain intelligence
  - `relations` - Domain/IP relations
  - `models` - ML model metadata
- [x] Add indexes for performance
- [x] Create Alembic configuration for migrations

### 2.2 Database Connection
- [x] Create async engine: `create_async_engine("postgresql+asyncpg://...")`
- [x] Implement session management
- [x] Add connection pooling

---

## PHASE 3: Backend API System

### 3.1 Define Pydantic Schemas in app/models/schemas.py
- [x] ScanRequest (text, url, html, metadata)
- [x] ScanResponse (risk, confidence, reasons, graph_score, model_score, timestamp)
- [x] FeedbackRequest (scan_id, user_flag, corrected_label)
- [x] HealthResponse

### 3.2 Create API Endpoints in app/api/routes.py
- [x] POST /scan - Main threat scanning endpoint
- [x] POST /feedback - User feedback submission
- [x] GET /threat-intel/{domain} - Domain intelligence
- [x] GET /model-health - Model metrics
- [x] GET /health - Health check

### 3.3 Implement Middleware
- [x] Rate limiting (slowapi)
- [x] JWT authentication
- [x] Structured logging (structlog)
- [x] OpenTelemetry tracing

### 3.4 Security Implementation
- [x] Input sanitization
- [x] JWT token validation
- [x] API key management
- [x] HTTPS enforcement

---

## PHASE 4: Graph-Based Threat Intelligence Layer

### 4.1 Graph Service in app/services/graph.py
- [x] Implement NetworkX graph (MVP)
- [x] Node types: domains, IPs, URLs
- [x] Edge types: RESOLVES_TO, REDIRECTS_TO, CONTAINS
- [x] PageRank centrality calculation
- [x] Community detection (Louvain)
- [x] Risk score computation

### 4.2 Graph Query Functions
- [x] Query domain connections
- [x] Find malicious neighbors
- [x] Calculate centrality scores
- [x] Detect clusters/campaigns

---

## PHASE 5: Threat Data Ingestion Pipeline

### 5.1 Celery Tasks in app/tasks/ingestion.py
- [x] Feed ingestion task
- [x] Data normalization
- [x] Deduplication (hash-based)
- [x] Database persistence
- [x] Graph update triggers

### 5.2 Scheduler
- [x] APScheduler setup for periodic tasks
- [x] Configure feed fetch intervals

---

## PHASE 6: Scoring & Fusion Engine

### 6.1 Scoring Service in app/services/scoring.py
- [x] Normalize scores to [0,1]
- [x] Fusion algorithm: weighted combination
- [x] Threshold mapping (LOW/MEDIUM/HIGH)
- [x] Confidence calibration

---

## PHASE 7: Performance Optimization

### 7.1 Caching Strategy
- [x] Redis cache setup
- [x] Cache scan results (1 hour TTL)
- [x] Cache graph data

### 7.2 Async Optimization
- [x] Parallel ML inference calls
- [x] Async database operations
- [x] Circuit breaker implementation

---

## PHASE 8: Continuous Learning & Monitoring

### 8.1 Logging
- [x] Structured JSON logging
- [x] Scan result logging
- [x] Drift detection setup

### 8.2 Health Monitoring
- [x] Model uptime tracking
- [x] Error rate monitoring
- [x] Performance metrics

---

## PHASE 9: Deployment Architecture

### 9.1 Docker Configuration
- [x] Create Dockerfile
- [x] Create docker-compose.yml
- [x] Define services: API, PostgreSQL, Redis, Celery

### 9.2 CI/CD Setup
- [x] GitHub Actions workflow
- [x] Docker build/push
- [x] Test automation

---

## PHASE 10: Testing & Validation

### 10.1 Unit Tests
- [x] API endpoint tests
- [x] Service logic tests
- [x] Model schema validation

### 10.2 Integration Tests
- [ ] Database integration
- [ ] Redis caching
- [ ] Graph operations

---

## Iteration & Fixes

### Issues Found and Fixed:
1. [x] Fixed rate limit middleware integration
2. [x] Fixed GraphService async/sync issues
3. [x] Implemented database persistence functions
4. [x] Fixed database health check
5. [x] Added missing python-louvain dependency
6. [x] Implemented Celery tasks
7. [x] Added GitHub Actions workflow

---

## Project Structure to Create

```
AWS_Builder/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py           # API endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py          # Pydantic models
│   │   └── db.py               # SQLAlchemy models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── graph.py            # Graph service
│   │   ├── scoring.py          # Fusion engine
│   │   └── ml.py               # ML inference
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py             # JWT auth
│   │   └── rate_limit.py       # Rate limiting
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── ingestion.py        # Celery tasks
│   └── config.py               # Configuration
├── tests/
│   ├── __init__.py
│   └── test_api.py
├── configs/
│   └── settings.yaml
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Implementation Priority

1. **Week 1**: Project setup, database schema, basic API
2. **Week 2**: Graph service, scoring engine
3. **Week 3**: Ingestion pipeline, caching
4. **Week 4**: Security, testing, deployment
