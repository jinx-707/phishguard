# Quick Start Guide - After Fixes

## Prerequisites
- Docker and Docker Compose installed
- Python 3.11+ (for local development)

## 1. Environment Setup

The `.env` file has been created with the correct password (`postgres1234`). Review and modify if needed:

```bash
# View current configuration
cat .env

# Edit if needed
notepad .env  # Windows
```

## 2. Start All Services

```bash
# Start all services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

## 3. Verify Services

### Option A: Use the verification script
```bash
python verify_fixes.py
```

### Option B: Manual verification

**Check PostgreSQL:**
```bash
docker exec -it phishguard-postgres psql -U postgres -d threat_intel -c "\dt"
```

**Check Redis:**
```bash
docker exec -it phishguard-redis redis-cli ping
```

**Check API Health:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "healthy",
  "redis": "healthy"
}
```

## 4. Test the API

### Scan a URL:
```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "meta": {"source": "test"}
  }'
```

### Chrome Extension Endpoint:
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "suspicious_keywords_found": ["urgent", "verify"],
    "long_url": false
  }'
```

## 5. Access Monitoring Tools

- **API Documentation**: http://localhost:8000/docs
- **Flower (Celery)**: http://localhost:5555
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## 6. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f celery-worker
```

## 7. Database Management

### Connect to PostgreSQL:
```bash
docker exec -it phishguard-postgres psql -U postgres -d threat_intel
```

### Run migrations (if using Alembic):
```bash
docker exec -it phishguard-api alembic upgrade head
```

### View tables:
```sql
\dt
\d+ scans
\d+ domains
```

## 8. Redis Management

### Connect to Redis:
```bash
docker exec -it phishguard-redis redis-cli
```

### Common Redis commands:
```redis
# Check connection
PING

# View all keys
KEYS *

# Get cache stats
INFO stats

# View memory usage
INFO memory

# Clear cache (use with caution!)
FLUSHDB
```

## 9. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

## 10. Troubleshooting

### Services won't start:
```bash
# Check for port conflicts
netstat -ano | findstr :5432
netstat -ano | findstr :6379
netstat -ano | findstr :8000

# View detailed logs
docker-compose logs postgres
docker-compose logs redis
docker-compose logs api
```

### Database connection errors:
```bash
# Verify credentials
docker exec phishguard-api env | findstr DATABASE_URL

# Test connection
docker exec -it phishguard-postgres psql -U postgres -d threat_intel -c "SELECT 1;"
```

### Redis connection errors:
```bash
# Verify Redis is running
docker exec -it phishguard-redis redis-cli ping

# Check Redis logs
docker logs phishguard-redis
```

### API errors:
```bash
# Check API logs
docker logs phishguard-api --tail 100

# Restart API
docker-compose restart api
```

## 11. Development Mode

For local development without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
# Edit .env file with localhost instead of service names:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@localhost:5432/threat_intel
# REDIS_URL=redis://localhost:6379/0

# Start services only (not API)
docker-compose up -d postgres redis

# Run API locally
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker locally
celery -A app.tasks.celery_app worker --loglevel=info
```

## 12. Production Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` in `.env`
- [ ] Change `POSTGRES_PASSWORD` to a strong password
- [ ] Set `DEBUG=false`
- [ ] Configure proper CORS origins
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy
- [ ] Set up monitoring and alerting
- [ ] Review and adjust connection pool sizes
- [ ] Configure log aggregation
- [ ] Set up rate limiting appropriately

## Key Improvements Made

1. ✅ **Connection Pooling**: Redis and PostgreSQL use connection pools
2. ✅ **Proper Async Patterns**: No manual event loop creation
3. ✅ **Environment Variables**: No hardcoded credentials
4. ✅ **Dependency Injection**: FastAPI Depends() for resource management
5. ✅ **Health Checks**: All services have health checks
6. ✅ **Error Handling**: Proper rollback on database errors
7. ✅ **Resource Cleanup**: Async generators ensure cleanup

## Support

For issues or questions, refer to:
- `DOCKER_REDIS_POSTGRES_FIXES.md` - Detailed fix documentation
- `API_DOCUMENTATION.md` - API reference
- `ARCHITECTURE_DEEP_DIVE.md` - System architecture

---

**All systems are now properly configured and ready to use!**
