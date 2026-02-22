# 🚀 Quick Start Guide

## One-Command Start

```bash
run_complete_test.bat
```

This will:
1. ✅ Check Docker services
2. ✅ Validate components
3. ✅ Start API server
4. ✅ Run tests
5. ✅ Open test frontend

---

## Manual Start (3 Steps)

### Step 1: Start Docker
```bash
docker-compose up -d db redis
```

### Step 2: Start API
```bash
python -m uvicorn app.main:app --reload
```

### Step 3: Test
Open `test_frontend.html` in your browser

---

## Quick Commands

```bash
# Test components only
python quick_test.py

# Run live demo
python demo_test.py

# Validate system
python validate_system.py

# Run API tests
python test_api.py
```

---

## Access Points

- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **Frontend:** test_frontend.html

---

## Test an Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

---

## Stop Everything

```bash
# Stop API: Ctrl+C
# Stop Docker: docker-compose down
```

---

## Need Help?

- See `RUN_INSTRUCTIONS.md` for detailed guide
- See `FINAL_SUMMARY.md` for complete overview
- See `SYSTEM_STATUS.md` for current status
