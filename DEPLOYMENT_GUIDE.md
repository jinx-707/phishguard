# 🚀 PhishGuard Deployment Guide

Complete guide for deploying the PhishGuard Threat Intelligence Platform.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Docker Deployment](#docker-deployment)
4. [Production Deployment](#production-deployment)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.11+**
- **Docker 20.10+**
- **Docker Compose 2.0+**
- **PostgreSQL 15+** (if not using Docker)
- **Redis 7+** (if not using Docker)

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4 GB
- Disk: 20 GB

**Recommended:**
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 50+ GB SSD

---

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/phishguard.git
cd phishguard
```

### 2. Create Virtual Environment

**Linux/Mac:**
```bash
python3.11 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Start Infrastructure Services

**Using Docker:**
```bash
docker-compose up -d postgres redis
```

**Or install locally:**
- PostgreSQL: https://www.postgresql.org/download/
- Redis: https://redis.io/download

### 6. Run Database Migrations

```bash
alembic upgrade head
```

### 7. Start Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the run script
./run.sh  # Linux/Mac
run.bat   # Windows
```

### 8. Start Celery Worker (Optional)

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

### 9. Access Application

- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## Docker Deployment

### Quick Start

```bash
# Deploy all services
./deploy.sh  # Linux/Mac
deploy.bat   # Windows

# Or manually
docker-compose up -d
```

### Services Included

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI application |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache & message broker |
| Celery Worker | - | Background task processor |
| Celery Beat | - | Task scheduler |
| Flower | 5555 | Celery monitoring |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Metrics visualization |
| Nginx | 80, 443 | Reverse proxy |

### Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild images
docker-compose build --no-cache

# Scale workers
docker-compose up -d --scale celery-worker=4
```

---

## Production Deployment

### AWS Deployment

#### 1. Infrastructure Setup (Terraform)

```hcl
# main.tf
provider "aws" {
  region = "us-east-1"
}

# ECS Cluster
resource "aws_ecs_cluster" "phishguard" {
  name = "phishguard-cluster"
}

# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier        = "phishguard-db"
  engine            = "postgres"
  engine_version    = "15.3"
  instance_class    = "db.t3.medium"
  allocated_storage = 100
  
  db_name  = "threat_intel"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  backup_retention_period = 7
  multi_az               = true
  storage_encrypted      = true
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "phishguard-redis"
  engine               = "redis"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  
  security_group_ids = [aws_security_group.redis.id]
  subnet_group_name  = aws_elasticache_subnet_group.main.name
}

# ECS Task Definition
resource "aws_ecs_task_definition" "api" {
  family                   = "phishguard-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  
  container_definitions = jsonencode([{
    name  = "api"
    image = "${var.ecr_repository}:latest"
    
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    
    environment = [
      {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/threat_intel"
      },
      {
        name  = "REDIS_URL"
        value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
      }
    ]
    
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/phishguard-api"
        "awslogs-region"        = "us-east-1"
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "phishguard-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

# ECS Service
resource "aws_ecs_service" "api" {
  name            = "phishguard-api"
  cluster         = aws_ecs_cluster.phishguard.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"
  
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }
  
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }
}
```

#### 2. Deploy to AWS

```bash
# Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t phishguard-api .
docker tag phishguard-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/phishguard-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/phishguard-api:latest

# Deploy infrastructure
terraform init
terraform plan
terraform apply

# Update ECS service
aws ecs update-service --cluster phishguard-cluster --service phishguard-api --force-new-deployment
```

### Kubernetes Deployment

#### 1. Create Kubernetes Manifests

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: phishguard-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: phishguard-api
  template:
    metadata:
      labels:
        app: phishguard-api
    spec:
      containers:
      - name: api
        image: phishguard-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: phishguard-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: phishguard-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: phishguard-api
spec:
  selector:
    app: phishguard-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: phishguard-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: phishguard-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### 2. Deploy to Kubernetes

```bash
# Create secrets
kubectl create secret generic phishguard-secrets \
  --from-literal=database-url='postgresql+asyncpg://...' \
  --from-literal=redis-url='redis://...'

# Deploy application
kubectl apply -f deployment.yaml

# Check status
kubectl get pods
kubectl get services
kubectl logs -f deployment/phishguard-api
```

---

## Configuration

### Environment Variables

```bash
# Application
APP_NAME=Threat Intelligence Platform
APP_VERSION=1.0.0
DEBUG=false
API_PREFIX=/api/v1

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Scoring
MODEL_WEIGHT=0.6
GRAPH_WEIGHT=0.4

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=threat-intel-api
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

---

## Monitoring

### Prometheus Metrics

Access Prometheus at http://localhost:9090

**Key Metrics:**
- `scan_requests_total` - Total scan requests
- `scan_duration_seconds` - Scan duration histogram
- `cache_hits_total` - Cache hit count
- `cache_misses_total` - Cache miss count
- `errors_total` - Error count by type

### Grafana Dashboards

Access Grafana at http://localhost:3000 (admin/admin)

**Pre-configured Dashboards:**
1. API Performance
2. Database Metrics
3. Cache Performance
4. Error Rates
5. Celery Tasks

### Logs

```bash
# View all logs
docker-compose logs -f

# View API logs
docker-compose logs -f api

# View Celery logs
docker-compose logs -f celery-worker

# Export logs
docker-compose logs > logs/phishguard.log
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection
docker-compose exec postgres psql -U postgres -c "SELECT 1"

# View logs
docker-compose logs postgres
```

#### 2. Redis Connection Failed

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# View logs
docker-compose logs redis
```

#### 3. API Not Responding

```bash
# Check API status
curl http://localhost:8000/health

# View logs
docker-compose logs api

# Restart API
docker-compose restart api
```

#### 4. High Memory Usage

```bash
# Check resource usage
docker stats

# Reduce workers
# Edit docker-compose.yml: --workers 2

# Restart services
docker-compose restart
```

### Performance Tuning

#### Database

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM scans WHERE created_at > NOW() - INTERVAL '1 day';

-- Create indexes
CREATE INDEX idx_scans_created_at ON scans(created_at DESC);
CREATE INDEX idx_domains_risk_score ON domains(risk_score DESC);
```

#### Redis

```bash
# Monitor Redis
redis-cli --stat

# Check memory usage
redis-cli INFO memory

# Clear cache
redis-cli FLUSHDB
```

#### Application

```python
# Increase worker pool
# docker-compose.yml
command: uvicorn app.main:app --workers 8

# Adjust database pool
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

---

## Security Best Practices

1. **Change default passwords**
2. **Use HTTPS in production**
3. **Enable firewall rules**
4. **Regular security updates**
5. **Implement rate limiting**
6. **Use secrets management**
7. **Enable audit logging**
8. **Regular backups**

---

## Backup & Recovery

### Database Backup

```bash
# Backup
docker-compose exec postgres pg_dump -U postgres threat_intel > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres threat_intel < backup.sql
```

### Redis Backup

```bash
# Backup
docker-compose exec redis redis-cli SAVE
docker cp phishguard-redis:/data/dump.rdb ./backup/

# Restore
docker cp ./backup/dump.rdb phishguard-redis:/data/
docker-compose restart redis
```

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/phishguard/issues
- Documentation: https://docs.phishguard.io
- Email: support@phishguard.io
