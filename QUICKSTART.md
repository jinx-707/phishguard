# 🚀 QUICK START GUIDE

## ⚡ 3-Step Setup

```bash
1. setup.bat      # Install everything
2. run.bat        # Start the API
3. test-api.bat   # Test it works
```

## 🌐 Access Points

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

## 📋 Common Commands

### Setup & Run
```bash
setup.bat           # First-time setup
run.bat             # Start API server
validate.bat        # Check system status
```

### Testing
```bash
test.bat            # Run unit tests
test-api.bat        # Test API endpoints
```

### Docker
```bash
docker-compose up -d              # Start all services
docker-compose down               # Stop all services
docker-compose logs -f api        # View API logs
docker-compose ps                 # Check status
```

## 🔥 Quick API Tests

### Health Check
```bash
curl http://localhost:8000/health
```

### Scan URL
```bash
curl -X POST http://localhost:8000/api/v1/scan ^
  -H "Content-Type: application/json" ^
  -d "{\"url\": \"https://example.com\"}"
```

### Get Domain Intel
```bash
curl http://localhost:8000/api/v1/threat-intel/example.com
```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/scan` | POST | Scan content |
| `/api/v1/feedback` | POST | Submit feedback |
| `/api/v1/threat-intel/{domain}` | GET | Domain intel |
| `/api/v1/model-health` | GET | Model metrics |

## 🔧 Configuration

Edit `.env` file:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/threat_intel
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
MODEL_WEIGHT=0.6
GRAPH_WEIGHT=0.4
```

## 🐛 Troubleshooting

### API won't start
```bash
# Check Docker services
docker-compose ps

# Restart services
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Database connection error
```bash
# Restart PostgreSQL
docker-compose restart db

# Check connection
docker-compose exec db psql -U postgres -c "SELECT 1"
```

### Redis connection error
```bash
# Restart Redis
docker-compose restart redis

# Test connection
docker-compose exec redis redis-cli ping
```

## 📚 Documentation

- `README.md` - Project overview
- `IMPLEMENTATION.md` - Full implementation guide
- `STATUS_REPORT.md` - Detailed status
- `VERIFICATION.md` - Verification steps
- `/docs` - Interactive API docs

## ✅ Verification Checklist

- [ ] Python 3.11+ installed
- [ ] Docker Desktop running
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Docker services running
- [ ] API responding on port 8000
- [ ] Tests passing

## 🎯 Project Structure

```
AWS_Builder/
├── app/              # Application code
├── tests/            # Test suite
├── alembic/          # DB migrations
├── .env              # Configuration
├── docker-compose.yml
├── requirements.txt
└── *.bat             # Helper scripts
```

## 🔐 Security Notes

- Change `SECRET_KEY` in production
- Enable authentication for sensitive endpoints
- Configure CORS for your domain
- Use HTTPS in production
- Set up rate limiting per your needs

## 📈 Performance Tips

- Redis caching enabled by default
- Async operations throughout
- Connection pooling configured
- Scale horizontally by adding workers

## 🚀 Deployment

### Local
```bash
run.bat
```

### Docker
```bash
docker-compose up -d
```

### Cloud (AWS/GCP)
1. Build: `docker build -t threat-intel-api .`
2. Push to registry
3. Deploy to ECS/Cloud Run/K8s
4. Configure environment variables
5. Set up managed DB and Redis

## 💡 Tips

- Use `/docs` for interactive testing
- Check logs for debugging
- Run `validate.bat` before deploying
- Keep `.env` file secure
- Monitor `/health` endpoint

## 🆘 Need Help?

1. Check `IMPLEMENTATION.md` for details
2. Review `STATUS_REPORT.md` for status
3. Run `validate.bat` to diagnose issues
4. Check Docker logs: `docker-compose logs -f`

---

**Status**: ✅ All systems operational  
**Version**: 0.1.0 (MVP)  
**Ready**: Yes 🚀
