# Port Integration and Network Connectivity Analysis

## Executive Summary

⚠️ **CRITICAL ISSUE FOUND**: There is a **hostname mismatch** between Docker Compose and local environment configurations that will cause connection failures.

## Port Mapping Overview

### External Ports (Host → Container)
| Service | Host Port | Container Port | Protocol | Status |
|---------|-----------|----------------|----------|--------|
| PostgreSQL | 5432 | 5432 | TCP | ✅ Mapped |
| Redis | 6379 | 6379 | TCP | ✅ Mapped |
| API | 8000 | 8000 | HTTP | ✅ Mapped |
| Flower | 5555 | 5555 | HTTP | ✅ Mapped |
| Prometheus | 9090 | 9090 | HTTP | ✅ Mapped |
| Grafana | 3000 | 3000 | HTTP | ✅ Mapped |
| Nginx | 80 | 80 | HTTP | ✅ Mapped |
| Nginx SSL | 443 | 443 | HTTPS | ✅ Mapped |

## 🔴 CRITICAL ISSUE: Hostname Mismatch

### Problem
The `.env` file uses `localhost` for service hostnames, but Docker containers need to use **service names** to communicate within the Docker network.

### Current Configuration (INCORRECT for Docker)
```bash
# .env file
DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@localhost:5432/threat_intel
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
```

### What Happens
- ✅ **Works**: When running services locally (outside Docker)
- ❌ **FAILS**: When running inside Docker containers
  - `localhost` inside a container refers to the container itself, not the host
  - Containers cannot reach PostgreSQL or Redis using `localhost`

### Docker Compose Configuration (CORRECT)
```yaml
# docker-compose.yml - API service
environment:
  - DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@postgres:5432/threat_intel
  - REDIS_URL=redis://redis:6379/0
  - CELERY_BROKER_URL=redis://redis:6379/1
```

✅ This is **CORRECT** - uses service names (`postgres`, `redis`)

## Service Interconnection Map

```
┌─────────────────────────────────────────────────────────────┐
│                    phishguard-network                        │
│                                                              │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐   │
│  │ postgres │◄────────┤   api    │────────►│  redis   │   │
│  │  :5432   │         │  :8000   │         │  :6379   │   │
│  └──────────┘         └─────┬────┘         └────┬─────┘   │
│                             │                    │          │
│                             │                    │          │
│  ┌──────────┐         ┌────▼─────┐         ┌───▼──────┐   │
│  │ postgres │◄────────┤  celery  │────────►│  redis   │   │
│  │  :5432   │         │  worker  │         │  :6379   │   │
│  └──────────┘         └──────────┘         │  (db 1)  │   │
│                                             └──────────┘   │
│  ┌──────────┐         ┌──────────┐                        │
│  │ postgres │◄────────┤  celery  │                        │
│  │  :5432   │         │   beat   │                        │
│  └──────────┘         └──────────┘                        │
│                                                             │
│  ┌──────────┐         ┌──────────┐                        │
│  │  redis   │◄────────┤  flower  │                        │
│  │  :6379   │         │  :5555   │                        │
│  └──────────┘         └──────────┘                        │
│                                                             │
│  ┌──────────┐         ┌──────────┐                        │
│  │   api    │◄────────┤  nginx   │                        │
│  │  :8000   │         │ :80/:443 │                        │
│  └──────────┘         └──────────┘                        │
│                                                             │
│  ┌──────────┐         ┌──────────┐                        │
│  │   api    │────────►│prometheus│                        │
│  │  :8000   │         │  :9090   │                        │
│  └──────────┘         └─────┬────┘                        │
│                             │                              │
│                       ┌─────▼────┐                        │
│                       │ grafana  │                        │
│                       │  :3000   │                        │
│                       └──────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Service Dependencies

### API Service
**Depends on:**
- ✅ PostgreSQL (postgres:5432) - Database
- ✅ Redis (redis:6379/0) - Cache
- ✅ Redis (redis:6379/1) - Celery broker

**Used by:**
- ✅ Nginx (reverse proxy)
- ✅ Prometheus (metrics scraping)
- ✅ External clients (port 8000)

### Celery Worker
**Depends on:**
- ✅ PostgreSQL (postgres:5432) - Database
- ✅ Redis (redis:6379/0) - Cache
- ✅ Redis (redis:6379/1) - Task queue

**Used by:**
- ✅ Flower (monitoring)

### Celery Beat
**Depends on:**
- ✅ PostgreSQL (postgres:5432) - Database
- ✅ Redis (redis:6379/1) - Task scheduling

### Flower
**Depends on:**
- ✅ Redis (redis:6379/1) - Celery monitoring
- ✅ Celery Worker (must be running)

### Prometheus
**Depends on:**
- ✅ API (api:8000/metrics) - Metrics endpoint

### Grafana
**Depends on:**
- ✅ Prometheus (prometheus:9090) - Data source

### Nginx
**Depends on:**
- ✅ API (api:8000) - Backend service

## Redis Database Separation

✅ **Correctly Configured**

- **Database 0** (`redis:6379/0`): Application cache
  - Used by: API, Celery Worker
  - Purpose: Caching scan results, rate limiting

- **Database 1** (`redis:6379/1`): Celery message broker
  - Used by: Celery Worker, Celery Beat, Flower
  - Purpose: Task queue, results backend

## Health Check Chain

```
1. PostgreSQL starts → Health check passes
2. Redis starts → Health check passes
3. API waits for postgres & redis → Starts
4. Celery Worker waits for postgres & redis → Starts
5. Celery Beat waits for postgres & redis → Starts
6. Flower waits for redis & celery-worker → Starts
7. Nginx waits for api → Starts
8. Prometheus starts (no dependencies)
9. Grafana waits for prometheus → Starts
```

## Environment Variable Analysis

### Issue 1: .env File (Local Development)
```bash
# Current - Works for LOCAL development only
DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@localhost:5432/threat_intel
REDIS_URL=redis://localhost:6379/0
```

### Issue 2: Docker Compose (Container Environment)
```yaml
# Current - CORRECT for Docker
environment:
  - DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@postgres:5432/threat_intel
  - REDIS_URL=redis://redis:6379/0
```

## 🔧 FIXES REQUIRED

### Fix 1: Update .env for Docker Context

Create two separate environment files:

**`.env.docker`** (for Docker Compose):
```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres1234
POSTGRES_DB=threat_intel
DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@postgres:5432/threat_intel

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/1

# ML Service (if running in Docker)
ML_SERVICE_URL=http://ml-service:8001

# OpenTelemetry (if running in Docker)
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

**`.env.local`** (for local development):
```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres1234
POSTGRES_DB=threat_intel
DATABASE_URL=postgresql+asyncpg://postgres:postgres1234@localhost:5432/threat_intel

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ML Service
ML_SERVICE_URL=http://localhost:8001

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Fix 2: Update docker-compose.yml

The docker-compose.yml is already correct! It overrides the environment variables with proper service names.

### Fix 3: Document the Difference

Users need to know:
- Use `.env.local` when running services locally
- Docker Compose automatically uses correct hostnames (no .env needed)

## Port Conflict Check

### Potential Conflicts
| Port | Service | Conflict Risk |
|------|---------|---------------|
| 5432 | PostgreSQL | Medium - May conflict with local PostgreSQL |
| 6379 | Redis | Medium - May conflict with local Redis |
| 8000 | API | Low - Common dev port |
| 5555 | Flower | Low |
| 9090 | Prometheus | Low |
| 3000 | Grafana | Medium - May conflict with React dev servers |
| 80 | Nginx | High - May conflict with other web servers |
| 443 | Nginx | High - May conflict with other HTTPS servers |

### Resolution
```bash
# Check for port conflicts before starting
netstat -ano | findstr :5432
netstat -ano | findstr :6379
netstat -ano | findstr :8000
netstat -ano | findstr :3000
netstat -ano | findstr :80
```

## Network Connectivity Tests

### Test 1: PostgreSQL from API Container
```bash
docker exec phishguard-api ping -c 3 postgres
docker exec phishguard-api nc -zv postgres 5432
```

### Test 2: Redis from API Container
```bash
docker exec phishguard-api ping -c 3 redis
docker exec phishguard-api nc -zv redis 6379
```

### Test 3: API from Nginx Container
```bash
docker exec phishguard-nginx ping -c 3 api
docker exec phishguard-nginx nc -zv api 8000
```

### Test 4: Redis from Celery Worker
```bash
docker exec phishguard-celery-worker ping -c 3 redis
docker exec phishguard-celery-worker nc -zv redis 6379
```

## Integration Verification Checklist

- [x] PostgreSQL port 5432 exposed and mapped
- [x] Redis port 6379 exposed and mapped
- [x] API port 8000 exposed and mapped
- [x] All services on same Docker network
- [x] Health checks configured for critical services
- [x] Service dependencies properly defined
- [x] Redis database separation (0 for cache, 1 for Celery)
- [ ] ⚠️ Environment variables use correct hostnames for Docker
- [x] Connection pooling configured
- [x] Proper async patterns implemented

## Recommendations

### 1. Immediate Actions
- ✅ Docker Compose already uses correct service names
- ⚠️ Document that `.env` file is for local development only
- ✅ All services properly networked

### 2. Testing
- Run `docker-compose up -d`
- Verify all services start successfully
- Check logs for connection errors
- Test API endpoints

### 3. Monitoring
- Check Flower dashboard (http://localhost:5555)
- Monitor Prometheus metrics (http://localhost:9090)
- View Grafana dashboards (http://localhost:3000)

## Conclusion

### ✅ What's Working
1. Docker Compose configuration is **CORRECT**
2. All ports properly mapped
3. Services correctly networked
4. Health checks in place
5. Dependencies properly defined

### ⚠️ What Needs Attention
1. `.env` file uses `localhost` - only works for local development
2. Documentation needed to clarify Docker vs local development
3. Port conflict warnings for users

### 🎯 Action Required
**NO CODE CHANGES NEEDED** - Docker Compose is already correct!

Just need to:
1. Document that `.env` is for local development
2. Clarify that Docker Compose overrides with correct hostnames
3. Add port conflict checking to startup scripts

The system is **properly integrated** for Docker deployment!
