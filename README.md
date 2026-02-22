# Endpoint Threat Intelligence Platform

A scalable, secure Endpoint Threat Intelligence Platform Core built with FastAPI, designed for real-time phishing and threat detection.

## Features

- **REST API**: High-performance async API using FastAPI
- **Graph-Based Intelligence**: NetworkX for threat graph analysis (MVP), Neo4j for production
- **ML Integration**: Ready for ML model integration
- **Caching**: Redis for caching scan results
- **Rate Limiting**: Protect against abuse
- **JWT Authentication**: Secure API access
- **Structured Logging**: JSON-based logging with structlog
- **Observability**: OpenTelemetry integration

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI   │────▶│  PostgreSQL │
└─────────────┘     │    API     │     └─────────────┘
                    └─────────────┘            │
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │    Redis    │     │    Graph    │
                    │   (Cache)   │     │  (NetworkX) │
                    └─────────────┘     └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+

### Installation

1. Clone the repository
2. Copy environment variables:
   
```
bash
   cp .env.example .env
   
```

3. Start with Docker Compose:
   
```
bash
   docker-compose up -d
   
```

4. Access the API at http://localhost:8000

### Local Development

1. Create virtual environment:
   
```
bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   
```

2. Install dependencies:
   
```
bash
   pip install -r requirements.txt
   
```

3. Run the server:
   
```
bash
   uvicorn app.main:app --reload
   
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/scan | Scan content for threats |
| POST | /api/v1/feedback | Submit feedback on scan |
| GET | /api/v1/threat-intel/{domain} | Get domain intelligence |
| GET | /api/v1/model-health | Get model metrics |
| GET | /health | Health check |

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Configuration

See `.env.example` for available configuration options.

## Testing

Run tests:
```
bash
pytest
```

## Project Structure

```
app/
├── api/           # API routes
├── models/        # Pydantic & SQLAlchemy models
├── services/      # Business logic
├── middleware/    # Auth, rate limiting
└── tasks/         # Celery tasks
```

## License

MIT
