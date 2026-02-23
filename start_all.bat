@echo off
echo ========================================
echo PhishGuard - Complete System Startup
echo ========================================
echo.

REM Check if Docker is running
echo [1/5] Checking Docker services...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

REM Start Docker services if not running
echo [2/5] Starting PostgreSQL and Redis...
docker-compose up -d db redis
if %errorlevel% neq 0 (
    echo ERROR: Failed to start Docker services
    pause
    exit /b 1
)

REM Wait for services to be ready
echo [3/5] Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [4/5] Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    echo [4/5] Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Initialize database tables if needed
echo [5/5] Initializing database...
python create_tables.py

echo.
echo ========================================
echo All services started successfully!
echo ========================================
echo.
echo Services running:
echo   - PostgreSQL: localhost:5432
echo   - Redis: localhost:6379
echo   - API Server: Starting on http://localhost:8000
echo.
echo Starting FastAPI server...
echo Press Ctrl+C to stop
echo.

REM Start FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
