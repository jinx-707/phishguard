# 📚 Threat Intelligence Platform - Documentation Index

## 🚀 Getting Started

Start here if you're new to the project:

1. **[QUICK_START.md](QUICK_START.md)** - One-page quick start guide
2. **[RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md)** - Detailed setup instructions
3. **[SYSTEM_STATUS.md](SYSTEM_STATUS.md)** - Current system status

## 📖 Documentation

### Overview
- **[README.md](README.md)** - Project introduction and overview
- **[FINAL_SUMMARY.md](FINAL_SUMMARY.md)** - Complete project summary

### Technical
- **[ARCHITECTURE_DEEP_DIVE.md](ARCHITECTURE_DEEP_DIVE.md)** - Technical architecture
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Implementation details
- **[VERIFICATION.md](VERIFICATION.md)** - Verification procedures

### Status & Planning
- **[STATUS_REPORT.md](STATUS_REPORT.md)** - Development status
- **[TODO.md](TODO.md)** - Future enhancements
- **[TEST_RESULTS.md](TEST_RESULTS.md)** - Test results

## 🧪 Testing

### Test Files
- **[test_frontend.html](test_frontend.html)** - Interactive web UI for testing ⭐
- **[quick_test.py](quick_test.py)** - Component validation
- **[demo_test.py](demo_test.py)** - Live API demonstration
- **[test_api.py](test_api.py)** - Comprehensive API tests
- **[validate_system.py](validate_system.py)** - Full system validation

### Run Tests
```bash
# Quick component test
python quick_test.py

# Live demo
python demo_test.py

# Full test suite
run_complete_test.bat
```

## 🛠️ Configuration

### Configuration Files
- **[.env](.env)** - Environment variables
- **[docker-compose.yml](docker-compose.yml)** - Docker services
- **[requirements.txt](requirements.txt)** - Python dependencies
- **[alembic.ini](alembic.ini)** - Database migrations

### Database
- **[init_db.sql](init_db.sql)** - Database schema
- **[create_tables.py](create_tables.py)** - Table creation script

## 🏃 Quick Commands

### Start Everything
```bash
run_complete_test.bat
```

### Start API Only
```bash
python -m uvicorn app.main:app --reload
```

### Test Components
```bash
python quick_test.py
```

### Validate System
```bash
python validate_system.py
```

## 📁 Project Structure

```
AWS_Builder/
├── 📚 Documentation
│   ├── INDEX.md (this file)
│   ├── QUICK_START.md
│   ├── RUN_INSTRUCTIONS.md
│   ├── FINAL_SUMMARY.md
│   ├── SYSTEM_STATUS.md
│   └── ARCHITECTURE_DEEP_DIVE.md
│
├── 🧪 Testing
│   ├── test_frontend.html ⭐
│   ├── quick_test.py
│   ├── demo_test.py
│   ├── test_api.py
│   └── validate_system.py
│
├── 🚀 Application
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   ├── middleware/
│   │   └── main.py
│   └── tests/
│
└── ⚙️ Configuration
    ├── .env
    ├── docker-compose.yml
    ├── requirements.txt
    └── init_db.sql
```

## 🎯 Common Tasks

### First Time Setup
1. Read [QUICK_START.md](QUICK_START.md)
2. Run `docker-compose up -d db redis`
3. Run `python quick_test.py`
4. Start API: `python -m uvicorn app.main:app --reload`
5. Open `test_frontend.html`

### Testing
1. Open [test_frontend.html](test_frontend.html) in browser
2. Or run `python demo_test.py`
3. Or run `python test_api.py`

### Development
1. Check [ARCHITECTURE_DEEP_DIVE.md](ARCHITECTURE_DEEP_DIVE.md)
2. Review [TODO.md](TODO.md) for enhancements
3. Check [STATUS_REPORT.md](STATUS_REPORT.md) for progress

### Troubleshooting
1. Check [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md) troubleshooting section
2. Check [SYSTEM_STATUS.md](SYSTEM_STATUS.md) known issues
3. Review logs: `docker-compose logs -f`

## 🔗 Quick Links

### Access Points
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Test Frontend: test_frontend.html

### Docker Services
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## 📞 Support

### Check Status
```bash
python validate_system.py
```

### View Logs
```bash
# API logs (console output)
# Docker logs
docker-compose logs -f
```

### Restart Services
```bash
docker-compose restart
```

## ✅ Checklist

Before starting:
- [ ] Docker installed and running
- [ ] Python 3.11+ installed
- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)

After setup:
- [ ] Docker services running
- [ ] Component tests pass
- [ ] API server starts
- [ ] Test frontend works
- [ ] All endpoints respond

## 🎓 Learning Path

1. **Beginner**: Start with [QUICK_START.md](QUICK_START.md)
2. **User**: Read [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md)
3. **Developer**: Study [ARCHITECTURE_DEEP_DIVE.md](ARCHITECTURE_DEEP_DIVE.md)
4. **Advanced**: Review source code in `app/`

## 📊 Status

- **System Status**: ✅ OPERATIONAL
- **Last Updated**: February 18, 2026
- **Version**: 0.1.0
- **Components**: All working
- **Tests**: All passing

---

**Need help?** Start with [QUICK_START.md](QUICK_START.md) or [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md)
