@echo off
REM PhishGuard Deployment Script for Windows
REM This script deploys the complete PhishGuard infrastructure

echo ========================================
echo PhishGuard Deployment Script
echo ========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

echo [OK] Docker and Docker Compose are installed
echo.

REM Create necessary directories
echo Creating directories...
if not exist logs mkdir logs
if not exist data\postgres mkdir data\postgres
if not exist data\redis mkdir data\redis
if not exist ssl mkdir ssl

REM Copy environment file if it doesn't exist
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo [WARNING] Please update .env file with your configuration
)

REM Build Docker images
echo.
echo Building Docker images...
docker-compose build

REM Start services
echo.
echo Starting services...
docker-compose up -d

REM Wait for services to be healthy
echo.
echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

REM Check service health
echo.
echo Checking service health...

REM Check PostgreSQL
docker-compose exec -T postgres pg_isready -U postgres >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PostgreSQL is not healthy
) else (
    echo [OK] PostgreSQL is healthy
)

REM Check Redis
docker-compose exec -T redis redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Redis is not healthy
) else (
    echo [OK] Redis is healthy
)

REM Check API
curl -f http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [WARNING] API is starting up...
) else (
    echo [OK] API is healthy
)

REM Run database migrations
echo.
echo Running database migrations...
docker-compose exec -T api alembic upgrade head

REM Display service URLs
echo.
echo ========================================
echo Deployment complete!
echo ========================================
echo.
echo Service URLs:
echo   API:        http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo   Prometheus: http://localhost:9090
echo   Grafana:    http://localhost:3000 (admin/admin)
echo   Flower:     http://localhost:5555
echo.
echo To view logs:
echo   docker-compose logs -f
echo.
echo To stop services:
echo   docker-compose down
echo.

pause
