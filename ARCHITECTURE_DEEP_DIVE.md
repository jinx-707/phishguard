# 🏗️ DETAILED ARCHITECTURE & EXECUTION FLOW

## 📍 Execution Starting Point

### YES - Execution starts from VS Code Terminal

**Command**: `run.bat` or `python -m uvicorn app.main:app --reload`

**Execution Flow**:
```
VS Code Terminal
    ↓
run.bat (Windows Batch Script)
    ↓
Activates venv\Scripts\activate.bat
    ↓
Checks Docker services (PostgreSQL, Redis)
    ↓
Runs: python -m uvicorn app.main:app --reload
    ↓
Uvicorn loads app\main.py
    ↓
FastAPI Application Starts
    ↓
Lifespan Events Execute (startup)
    ↓
API Ready on http://localhost:8000
```

---

## 🎯 TECH STACK - WHAT, WHERE, HOW

### 1. **FastAPI** - Web Framework
**Location**: `app/main.py`
**Purpose**: HTTP API server, request routing, async handling
**How it works**:
```python
# app/main.py
app = FastAPI(
    title="Threat Intelligence Platform",
    lifespan=lifespan  # Startup/shutdown events
)

# Includes routes from app/api/routes.py
app.include_router(api_router, prefix="/api/v1")
```

**What happens**:
1. Creates FastAPI application instance
2. Configures middleware (CORS, rate limiting)
3. Registers API routes
4. Handles HTTP requests asynchronously
5. Returns JSON responses

---

### 2. **Uvicorn** - ASGI Server
**Location**: Command line / run.bat
**Purpose**: Runs the FastAPI application
**How it works**:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**What happens**:
1. Imports `app` from `app.main`
2. Starts ASGI server on port 8000
3. Watches for file changes (--reload)
4. Handles incoming HTTP connections
5. Passes requests to FastAPI

---

### 3. **PostgreSQL** - Database
**Location**: Docker container (port 5432)
**Purpose**: Persistent data storage
**How it works**:
```yaml
# docker-compose.yml
db:
  image: postgres:15-alpine
  ports: ["5432:5432"]
  environment:
    POSTGRES_DB: threat_intel
```

**What happens**:
1. Docker runs PostgreSQL container
2. Creates database "threat_intel"
3. Listens on port 5432
4. Stores: scans, feedback, domains, relations, model_metadata, threat_feeds

**Used by**: `app/services/database.py` via SQLAlchemy

---

### 4. **SQLAlchemy** - ORM (Object-Relational Mapping)
**Location**: `app/services/database.py`, `app/models/db.py`
**Purpose**: Database abstraction, async queries
**How it works**:
```python
# app/services/database.py
engine = create_async_engine(
    "postgresql+asyncpg://postgres:postgres@localhost:5432/threat_intel"
)

# app/models/db.py
class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True)
    risk = Column(Enum(RiskLevelEnum))
```

**What happens**:
1. Creates async database engine
2. Defines table models as Python classes
3. Translates Python objects to SQL queries
4. Executes queries asynchronously
5. Returns results as Python objects

---

### 5. **Redis** - Cache
**Location**: Local instance (port 6379)
**Purpose**: Fast in-memory caching
**How it works**:
```python
# app/services/redis.py
redis_client = redis.from_url("redis://localhost:6379/0")

# Usage in routes
cached = await redis.get(f"scan:{input_hash}")
await redis.setex(f"scan:{input_hash}", 3600, response.json())
```

**What happens**:
1. Connects to Redis on localhost:6379
2. Stores scan results with TTL (1 hour)
3. Caches graph data
4. Implements rate limiting counters
5. Returns cached data instantly (no DB query)

**Cache Keys**:
- `scan:{hash}` - Scan results
- `graph:data` - Graph structure
- `rate_limit:{ip}:{window}` - Rate limit counters

---

### 6. **NetworkX** - Graph Analysis
**Location**: `app/services/graph.py`
**Purpose**: Threat intelligence graph, centrality analysis
**How it works**:
```python
# app/services/graph.py
self.graph = nx.DiGraph()  # Directed graph
self.graph.add_node("example.com", type="domain")
self.graph.add_edge("example.com", "192.168.1.1", relation="RESOLVES_TO")

# Calculate PageRank
pagerank = nx.pagerank(self.graph)
centrality = pagerank.get(domain, 0.0)
```

**What happens**:
1. Builds directed graph of domains/IPs
2. Adds nodes (domains, IPs) and edges (relationships)
3. Calculates PageRank centrality (importance score)
4. Counts malicious neighbors
5. Detects communities (Louvain algorithm)
6. Finds paths between nodes
7. Caches graph in Redis

**Graph Structure**:
```
Domain Nodes: example.com, phishing.test
IP Nodes: 192.168.1.1, 192.168.1.2
Edges: RESOLVES_TO, REDIRECTS_TO, LINKS_TO
```

---

### 7. **Celery** - Task Queue
**Location**: `app/tasks/celery_app.py`, `app/tasks/ingestion.py`
**Purpose**: Background job processing
**How it works**:
```python
# app/tasks/celery_app.py
celery_app = Celery(
    "threat_intel_tasks",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/1"
)

# app/tasks/ingestion.py
@celery_app.task
def ingest_feed(feed_url: str):
    # Fetch threat data
    # Process and store
    # Update graph
```

**What happens**:
1. Uses Redis as message broker
2. Workers poll for tasks
3. Executes tasks asynchronously
4. Returns results to Redis backend

**Tasks**:
- `ingest_feed` - Fetch threat feeds
- `update_graph` - Rebuild graph
- `recalculate_scores` - Update risk scores
- `cleanup_old_scans` - Data retention

**To start workers**:
```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

---

### 8. **Pydantic** - Data Validation
**Location**: `app/models/schemas.py`
**Purpose**: Request/response validation, type checking
**How it works**:
```python
# app/models/schemas.py
class ScanRequest(BaseModel):
    url: Optional[str] = Field(None, description="URL to scan")
    
    @field_validator('url')
    def validate_url(cls, v):
        parsed = urlparse(v)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError("Invalid URL")
        return v
```

**What happens**:
1. Validates incoming JSON requests
2. Converts JSON to Python objects
3. Runs custom validators
4. Raises validation errors (422 status)
5. Serializes responses to JSON

---

### 9. **Structlog** - Structured Logging
**Location**: `app/main.py`, used throughout
**Purpose**: JSON-formatted logging
**How it works**:
```python
# app/main.py
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)

# Usage
logger.info("Scan completed", scan_id=scan_id, risk=risk)
```

**Output**:
```json
{
  "event": "Scan completed",
  "scan_id": "abc123",
  "risk": "HIGH",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 🔄 REQUEST FLOW - DETAILED

### Example: POST /api/v1/scan

```
1. CLIENT REQUEST
   ↓
   curl -X POST http://localhost:8000/api/v1/scan
   -H "Content-Type: application/json"
   -d '{"url": "https://example.com"}'

2. UVICORN (ASGI Server)
   ↓
   Receives HTTP request on port 8000
   Parses headers, body

3. FASTAPI MIDDLEWARE STACK
   ↓
   a) CORS Middleware - Checks origin
   b) Rate Limit Middleware - Checks Redis counter
      - Key: rate_limit:ip:192.168.1.1:timestamp
      - Increments counter
      - If > 60/min → 429 Too Many Requests
   c) Exception Handler - Catches errors

4. FASTAPI ROUTER
   ↓
   Matches route: POST /api/v1/scan
   Calls: app.api.routes.scan()

5. PYDANTIC VALIDATION
   ↓
   app/models/schemas.py:ScanRequest
   - Validates URL format
   - Checks content size
   - Sanitizes input
   - If invalid → 422 Unprocessable Entity

6. ROUTE HANDLER (app/api/routes.py)
   ↓
   async def scan(request: ScanRequest):
   
   a) Generate input hash
      input_hash = hashlib.sha256(json.dumps(request).encode()).hexdigest()
   
   b) Check Redis cache
      cached = await redis.get(f"scan:{input_hash}")
      if cached:
          return cached  # Cache hit!
   
   c) Get ML model score (simulated)
      model_score = await simulate_ml_inference(content, url)
      # In production: calls external ML service
   
   d) Get graph risk score
      graph_service = GraphService()
      graph_score = await graph_service.get_risk_score(url)
      
      Graph Service Flow:
      - Load graph from Redis cache or build new
      - Find domain in graph
      - Calculate PageRank centrality
      - Count malicious neighbors
      - Return risk score (0-1)
   
   e) Fusion scoring
      from app.services.scoring import compute_final_score
      risk, confidence, reasons = compute_final_score(
          model_score=0.8,
          graph_score=0.7
      )
      
      Scoring Logic:
      final = 0.6 * model_score + 0.4 * graph_score
      if final >= 0.7: risk = HIGH
      elif final >= 0.4: risk = MEDIUM
      else: risk = LOW
   
   f) Create response
      response = ScanResponse(
          scan_id=uuid.uuid4(),
          risk=risk,
          confidence=confidence,
          reasons=reasons,
          graph_score=graph_score,
          model_score=model_score
      )
   
   g) Cache result
      await redis.setex(f"scan:{input_hash}", 3600, response.json())
   
   h) Persist to database (async)
      # SQLAlchemy inserts into scans table
      # Not blocking - happens in background

7. FASTAPI RESPONSE
   ↓
   Serializes ScanResponse to JSON
   Sets headers (Content-Type: application/json)

8. UVICORN
   ↓
   Sends HTTP response to client

9. CLIENT RECEIVES
   ↓
   {
     "scan_id": "abc-123",
     "risk": "HIGH",
     "confidence": 0.95,
     "reasons": ["High ML confidence", "Strong graph indicators"],
     "graph_score": 0.7,
     "model_score": 0.8,
     "timestamp": "2024-01-15T10:30:00Z"
   }
```

**Total Time**: <500ms (cached: <50ms)

---

## 📂 FILE STRUCTURE - WHAT DOES WHAT

```
AWS_Builder/
│
├── app/                          # Main application code
│   ├── main.py                   # 🚀 ENTRY POINT - FastAPI app
│   │   └── Creates FastAPI instance
│   │   └── Configures middleware
│   │   └── Includes routes
│   │   └── Lifespan events (startup/shutdown)
│   │
│   ├── config.py                 # ⚙️ Configuration
│   │   └── Loads environment variables
│   │   └── Database URL, Redis URL, secrets
│   │   └── Scoring weights, rate limits
│   │
│   ├── api/
│   │   └── routes.py             # 🛣️ API Endpoints
│   │       └── POST /scan - Scan content
│   │       └── POST /feedback - Submit feedback
│   │       └── GET /threat-intel/{domain} - Domain info
│   │       └── GET /model-health - Model metrics
│   │       └── GET /health - Health check
│   │
│   ├── models/
│   │   ├── schemas.py            # 📋 Pydantic Models
│   │   │   └── ScanRequest - Input validation
│   │   │   └── ScanResponse - Output format
│   │   │   └── FeedbackRequest, ThreatIntelResponse
│   │   │
│   │   └── db.py                 # 🗄️ Database Models
│   │       └── Scan - Scan results table
│   │       └── Feedback - User feedback table
│   │       └── Domain - Domain intelligence table
│   │       └── Relation - Graph edges table
│   │       └── ModelMetadata - ML model tracking
│   │       └── ThreatFeed - Feed configuration
│   │
│   ├── services/
│   │   ├── database.py           # 💾 Database Service
│   │   │   └── init_db() - Initialize connection
│   │   │   └── get_db_session() - Get session
│   │   │   └── Uses SQLAlchemy async engine
│   │   │
│   │   ├── redis.py              # 🔴 Redis Service
│   │   │   └── init_redis() - Connect to Redis
│   │   │   └── get_cache() - Get cached value
│   │   │   └── set_cache() - Store with TTL
│   │   │
│   │   ├── graph.py              # 🕸️ Graph Service
│   │   │   └── GraphService class
│   │   │   └── get_risk_score() - Calculate risk
│   │   │   └── Uses NetworkX for graph analysis
│   │   │   └── PageRank, community detection
│   │   │
│   │   └── scoring.py            # 🎯 Scoring Engine
│   │       └── compute_final_score() - Fusion
│   │       └── Combines model + graph scores
│   │       └── Generates explanations
│   │
│   ├── middleware/
│   │   ├── auth.py               # 🔐 Authentication
│   │   │   └── JWT token validation
│   │   │   └── Role-based access control
│   │   │
│   │   └── rate_limit.py         # 🚦 Rate Limiting
│   │       └── Redis-based rate limiting
│   │       └── 60 requests/minute per IP
│   │
│   └── tasks/
│       ├── celery_app.py         # 📦 Celery Config
│       │   └── Celery application setup
│       │   └── Redis as broker
│       │
│       └── ingestion.py          # 📥 Background Tasks
│           └── ingest_feed() - Fetch threat data
│           └── update_graph() - Rebuild graph
│           └── recalculate_scores() - Update risks
│
├── tests/
│   └── test_api.py               # 🧪 Unit Tests
│       └── Test all endpoints
│       └── Test validation
│       └── Test error handling
│
├── alembic/                      # 🔄 Database Migrations
│   ├── env.py                    # Migration environment
│   └── versions/                 # Migration scripts
│
├── .env                          # 🔑 Environment Variables
│   └── DATABASE_URL, REDIS_URL
│   └── SECRET_KEY, API keys
│   └── Scoring weights
│
├── docker-compose.yml            # 🐳 Docker Services
│   └── PostgreSQL container
│   └── Redis container
│   └── Celery worker container
│
├── requirements.txt              # 📦 Dependencies
│   └── fastapi, uvicorn
│   └── sqlalchemy, asyncpg
│   └── redis, networkx
│   └── celery, pydantic
│
└── run.bat                       # ▶️ Start Script
    └── Activates venv
    └── Starts Docker services
    └── Runs uvicorn
```

---

## 🔧 TECHNOLOGY INTERACTIONS

### Database Flow
```
API Request
    ↓
SQLAlchemy ORM (app/services/database.py)
    ↓
asyncpg Driver (async PostgreSQL driver)
    ↓
PostgreSQL Database (Docker container)
    ↓
Returns data
    ↓
SQLAlchemy converts to Python objects
    ↓
API Response
```

### Cache Flow
```
API Request
    ↓
Check Redis (app/services/redis.py)
    ↓
redis.asyncio library
    ↓
Redis Server (localhost:6379)
    ↓
If HIT: Return cached data (fast!)
If MISS: Query database, cache result
```

### Graph Analysis Flow
```
Domain Query
    ↓
GraphService (app/services/graph.py)
    ↓
Load graph from Redis or build new
    ↓
NetworkX library
    ↓
Calculate PageRank (importance)
    ↓
Count malicious neighbors
    ↓
Return risk score (0-1)
```

### Background Tasks Flow
```
Scheduled Time or Manual Trigger
    ↓
Celery Beat (scheduler)
    ↓
Publishes task to Redis queue
    ↓
Celery Worker polls Redis
    ↓
Executes task (ingest_feed, update_graph)
    ↓
Updates database
    ↓
Invalidates cache
    ↓
Task complete
```

---

## 🚀 STARTUP SEQUENCE

### When you run `run.bat`:

```
1. run.bat executes
   ↓
2. Activates virtual environment
   venv\Scripts\activate.bat
   ↓
3. Checks Docker services
   docker ps
   ↓
4. If not running, starts:
   docker-compose up -d db redis
   ↓
5. Runs Uvicorn
   python -m uvicorn app.main:app --reload
   ↓
6. Uvicorn imports app.main
   ↓
7. app.main.py executes:
   
   a) Import all dependencies
      - FastAPI, SQLAlchemy, Redis, etc.
   
   b) Configure structlog
      - JSON logging setup
   
   c) Create FastAPI app
      app = FastAPI(lifespan=lifespan)
   
   d) Add middleware
      - CORS
      - Rate limiting
      - Exception handler
   
   e) Include routes
      app.include_router(api_router)
   
   f) Lifespan startup event:
      - await init_db()
        → Creates SQLAlchemy engine
        → Connects to PostgreSQL
        → Creates tables if not exist
      
      - await init_redis()
        → Connects to Redis
        → Tests connection with PING
   
   g) Server ready!
      INFO: Uvicorn running on http://0.0.0.0:8000
```

### What's Running After Startup:

```
Process 1: Uvicorn (Python)
  └── FastAPI Application
      ├── HTTP Server (port 8000)
      ├── Connection Pool → PostgreSQL
      ├── Connection Pool → Redis
      └── Background: File watcher (--reload)

Process 2: PostgreSQL (Docker)
  └── Database Server (port 5432)
      └── Database: threat_intel

Process 3: Redis (Local)
  └── Cache Server (port 6379)
      └── Databases: 0 (cache), 1 (celery)

Process 4: Celery Worker (if started)
  └── Task Queue Worker
      └── Polls Redis for tasks
```

---

## 💡 KEY CONCEPTS

### Async/Await
**Why**: Handle multiple requests concurrently without blocking
**Where**: All route handlers, database queries, Redis operations
**How**:
```python
async def scan(request: ScanRequest):
    cached = await redis.get(key)  # Non-blocking
    score = await graph.get_risk_score(domain)  # Non-blocking
    return response
```

### Dependency Injection
**Why**: Share resources (DB sessions, Redis clients)
**Where**: FastAPI Depends()
**How**:
```python
async def get_db():
    async with session_maker() as session:
        yield session

@router.get("/data")
async def get_data(db: AsyncSession = Depends(get_db)):
    result = await db.execute(query)
```

### Middleware
**Why**: Process all requests before reaching routes
**Where**: app/middleware/
**How**:
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Check rate limit
        if exceeded:
            raise HTTPException(429)
        response = await call_next(request)
        return response
```

---

## 🎯 EXECUTION FROM VS CODE TERMINAL

**YES - Everything runs from VS Code Terminal**

### Terminal 1: API Server
```bash
# In VS Code Terminal
cd c:\Users\Admin\Desktop\AWS_Builder
run.bat

# Or directly:
python -m uvicorn app.main:app --reload
```

### Terminal 2: Celery Worker (Optional)
```bash
# In VS Code Terminal (new terminal)
cd c:\Users\Admin\Desktop\AWS_Builder
venv\Scripts\activate
celery -A app.tasks.celery_app worker --loglevel=info
```

### Terminal 3: Testing
```bash
# In VS Code Terminal (new terminal)
cd c:\Users\Admin\Desktop\AWS_Builder
test.bat

# Or test API:
curl http://localhost:8000/health
```

---

## 📊 DATA FLOW SUMMARY

```
HTTP Request → Uvicorn → FastAPI → Middleware → Route Handler
                                                      ↓
                                    ┌─────────────────┴─────────────────┐
                                    ↓                                   ↓
                            Check Redis Cache                   Validate Input
                                    ↓                           (Pydantic)
                            If HIT: Return                              ↓
                            If MISS: Continue                   Get ML Score
                                    ↓                                   ↓
                            Query Graph Service             Get Graph Score
                                    ↓                                   ↓
                            NetworkX Analysis               Fusion Scoring
                                    ↓                                   ↓
                            Calculate Risk                  Generate Response
                                    ↓                                   ↓
                            Cache Result                    Store in DB
                                    ↓                                   ↓
                            Return JSON ←───────────────────────────────┘
```

---

**Generated**: 2024  
**Status**: ✅ COMPLETE TECHNICAL DOCUMENTATION
