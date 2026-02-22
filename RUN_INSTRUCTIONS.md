# 🛡️ Threat Intelligence Platform - Run Instructions

## Quick Start

### 1. Start Docker Services
```bash
docker-compose up -d db redis
```

Wait a few seconds for services to initialize.

### 2. Verify Docker Services
```bash
docker-compose ps
```

You should see `db` and `redis` containers running.

### 3. Initialize Database (First Time Only)
```bash
docker exec -i aws_builder-db-1 psql -U postgres -d threat_intel < init_db.sql
```

Or copy and execute:
```bash
docker cp init_db.sql aws_builder-db-1:/tmp/init_db.sql
docker exec aws_builder-db-1 psql -U postgres -d threat_intel -f /tmp/init_db.sql
```

### 4. Validate System
```bash
python validate_system.py
```

Note: Database validation may fail if connecting from outside Docker, but this is OK if Docker services are running.

### 5. Start API Server
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the batch file:
```bash
start_server.bat
```

### 6. Test the API

#### Option A: Use Test Frontend (Recommended)
1. Open `test_frontend.html` in your browser
2. The frontend will connect to `http://localhost:8000`
3. Test all endpoints through the UI

#### Option B: Use Python Test Script
```bash
python test_api.py
```

#### Option C: Use Swagger UI
Open in browser: http://localhost:8000/docs

#### Option D: Use cURL
```bash
# Health check
curl http://localhost:8000/health

# Scan URL
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## Architecture Overview

```
┌─────────────────┐
│  Test Frontend  │ (test_frontend.html)
│   (Browser)     │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│   FastAPI App   │ (Port 8000)
│   (Python)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ Redis  │ │  DB    │
│ (6379) │ │ (5432) │
└────────┘ └────────┘
```

## Available Endpoints

### POST /api/v1/scan
Scan content for threats.

**Request:**
```json
{
  "url": "https://example.com",
  "text": "Optional text content",
  "html": "Optional HTML content",
  "meta": {"source": "test"}
}
```

**Response:**
```json
{
  "scan_id": "uuid",
  "risk": "LOW|MEDIUM|HIGH",
  "confidence": 0.95,
  "reasons": ["reason1", "reason2"],
  "graph_score": 0.5,
  "model_score": 0.7,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### POST /api/v1/feedback
Submit feedback on scan results.

**Request:**
```json
{
  "scan_id": "uuid",
  "user_flag": true,
  "corrected_label": "HIGH",
  "comment": "Optional comment"
}
```

### GET /api/v1/threat-intel/{domain}
Get threat intelligence for a domain.

**Response:**
```json
{
  "domain": "example.com",
  "risk_score": 0.5,
  "is_malicious": false,
  "related_ips": [],
  "related_domains": [],
  "tags": ["analyzed"]
}
```

### GET /api/v1/model-health
Get model health metrics.

**Response:**
```json
{
  "model_name": "threat-detector-v1",
  "uptime": 99.9,
  "total_predictions": 10000,
  "error_rate": 0.01,
  "average_latency_ms": 150.0
}
```

## Troubleshooting

### Docker Services Not Running
```bash
docker-compose up -d db redis
docker-compose ps
```

### Database Connection Issues
The app uses Docker's PostgreSQL. If you see connection errors:
1. Ensure Docker containers are running
2. The app will create tables automatically on startup
3. Database validation may fail from outside Docker (this is OK)

### Redis Connection Issues
```bash
docker-compose restart redis
```

### Port Already in Use
If port 8000 is busy:
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process or use a different port
python -m uvicorn app.main:app --reload --port 8001
```

### Clear Cache
```bash
docker exec aws_builder-redis-1 redis-cli FLUSHALL
```

## Testing Checklist

- [ ] Docker services running (db, redis)
- [ ] Database tables created
- [ ] API server started
- [ ] Health endpoint responds
- [ ] Scan endpoint works
- [ ] Feedback endpoint works
- [ ] Threat intel endpoint works
- [ ] Model health endpoint works
- [ ] Caching works (second request faster)
- [ ] Test frontend loads and works

## Performance Notes

- First scan request: ~200-500ms
- Cached scan request: ~10-50ms (20x faster)
- Graph operations: Async with thread pool
- Redis TTL: 1 hour (configurable in .env)

## Next Steps

1. ✅ System is running
2. Test all endpoints via frontend
3. Review logs for any errors
4. Check database for persisted data
5. Monitor performance metrics

## Cleanup

To stop everything:
```bash
# Stop API server (Ctrl+C)

# Stop Docker services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v
```

## Files Overview

- `test_frontend.html` - Interactive test UI (TEMPORARY - can be deleted)
- `test_api.py` - Automated API tests
- `validate_system.py` - System validation script
- `start_server.bat` - Quick start script
- `init_db.sql` - Database schema
- `docker-compose.yml` - Docker configuration
- `.env` - Environment variables

## Support

Check logs for errors:
- API logs: Console output
- Docker logs: `docker-compose logs -f`
- Redis logs: `docker logs aws_builder-redis-1`
- DB logs: `docker logs aws_builder-db-1`
