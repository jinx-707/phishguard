# 🛡️ PhishGuard - Complete Integration Setup

## ✅ Current Status

**Infrastructure Ready:**
- [OK] Python 3.14.2
- [OK] Docker Running
- [OK] PostgreSQL (Port 5432)
- [OK] Redis (Port 6379)

**Need to Start:**
- [ ] FastAPI Server (Port 8000)
- [ ] Chrome Extension
- [ ] Dashboard (Optional)

---

## 🚀 Quick Start (3 Steps)

### Step 1: Start FastAPI Server

```bash
cd c:\Users\Admin\Desktop\AWS_Integrate\phishguard

# Option A: Use startup script
start_all.bat

# Option B: Manual start
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Verify:** Open http://localhost:8000/health (should return `{"status":"healthy"}`)

### Step 2: Load Chrome Extension

1. Open Chrome browser
2. Go to `chrome://extensions/`
3. Enable "Developer mode" (toggle top-right)
4. Click "Load unpacked"
5. Navigate to: `c:\Users\Admin\Desktop\AWS_Integrate\phishguard\aws\Chrome_extensions\`
6. Click "Select Folder"

**Verify:** Extension icon appears in Chrome toolbar

### Step 3: Test the System

1. Visit any website (e.g., https://example.com)
2. Check browser console (F12) for `[PhishGuard]` logs
3. Click extension icon to see scan results

---

## 📊 Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PhishGuard System                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Chrome Extension (Browser)                              │
│  ├─ Local AI Inference (< 50ms)                         │
│  ├─ Content Scanner                                     │
│  └─ Background Worker                                   │
│           ↓                                              │
│  FastAPI Server (Port 8000)                             │
│  ├─ /scan endpoint                                      │
│  ├─ /feedback endpoint                                  │
│  └─ /health endpoint                                    │
│           ↓                                              │
│  ┌──────────────┬──────────────┬──────────────┐        │
│  │              │              │              │        │
│  PostgreSQL     Redis          Graph          ML       │
│  (Port 5432)    (Port 6379)    Service       Engine    │
│  │              │              │              │        │
│  Persistent     Cache          NetworkX      Predictor │
│  Storage        Layer          Analysis      (NLP)     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🔌 Port Configuration

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| PostgreSQL | 5432 | localhost:5432 | Database storage |
| Redis | 6379 | localhost:6379 | Caching layer |
| FastAPI | 8000 | http://localhost:8000 | Main API server |
| Dashboard | 5173 | http://localhost:5173 | SOC Dashboard (optional) |

---

## 🔗 API Endpoints

### Chrome Extension Endpoints
```
POST   http://localhost:8000/scan          # Scan URL/content
POST   http://localhost:8000/feedback      # Submit feedback
GET    http://localhost:8000/status        # Server status
GET    http://localhost:8000/health        # Health check
```

### Standard API Endpoints
```
POST   http://localhost:8000/api/v1/scan
GET    http://localhost:8000/api/v1/threat-intel/{domain}
GET    http://localhost:8000/api/v1/model-health
```

### API Documentation
```
http://localhost:8000/docs                 # Swagger UI
http://localhost:8000/redoc                # ReDoc
```

---

## 🧪 Testing

### Test 1: Check System Status
```bash
python check_status.py
```

Expected output:
```
[OK] Python
[OK] Docker
[OK] PostgreSQL
[OK] Redis
[OK] FastAPI
[OK] API Health
```

### Test 2: Test API Endpoint
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"healthy","version":"1.0.0"}
```

### Test 3: Test Scan Endpoint
```bash
curl -X POST http://localhost:8000/scan -H "Content-Type: application/json" -d "{\"url\":\"https://example.com\"}"
```

Expected response:
```json
{
  "risk": "LOW",
  "confidence": 0.85,
  "reasons": ["Local AI assessment: Low threat"],
  ...
}
```

### Test 4: Chrome Extension
1. Open: `c:\Users\Admin\Desktop\AWS_Integrate\phishguard\aws\Chrome_extensions\test-page.html`
2. Click "Test LOW Risk"
3. Check console for logs
4. Click extension icon to see results

---

## 🔄 Data Flow

### Complete Request Flow
```
1. User visits webpage
   ↓
2. Chrome Extension (content.js) extracts page data
   ↓
3. Local AI Inference (< 50ms)
   - If LOW risk → Allow (skip backend)
   - If MEDIUM/HIGH → Continue to backend
   ↓
4. Background.js sends POST to http://localhost:8000/scan
   ↓
5. FastAPI receives request
   ↓
6. Check Redis cache
   - If cached → Return immediately
   - If not cached → Continue
   ↓
7. Process request:
   - ML Predictor analyzes content
   - Graph Service checks infrastructure
   - Scoring Engine combines results
   ↓
8. Store in PostgreSQL
   Cache in Redis
   ↓
9. Return JSON response
   ↓
10. Extension displays result:
    - HIGH risk → Full-screen block
    - MEDIUM risk → Warning banner
    - LOW risk → Allow
```

---

## 🛠️ Configuration Files

### .env (Environment Variables)
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/threat_intel
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=phishguard-secret-key-2024
PORT=8000
DEBUG=true
```

### docker-compose.yml (Docker Services)
```yaml
services:
  db:
    image: postgres:15-alpine
    ports: ["5432:5432"]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### background.js (Chrome Extension)
```javascript
const API_ENDPOINT = 'http://localhost:8000/scan';
const FEEDBACK_ENDPOINT = 'http://localhost:8000/feedback';
```

---

## 🔍 Troubleshooting

### Issue: FastAPI won't start
```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /PID <PID> /F

# Start FastAPI
python -m uvicorn app.main:app --reload
```

### Issue: PostgreSQL connection failed
```bash
# Check container status
docker ps | findstr postgres

# Restart container
docker-compose restart db

# Check logs
docker logs phishguard-postgres
```

### Issue: Redis connection failed
```bash
# Check container status
docker ps | findstr redis

# Restart container
docker-compose restart redis

# Test connection
docker exec -it phishguard-redis redis-cli ping
```

### Issue: Chrome extension not working
1. Check API is running: http://localhost:8000/health
2. Open browser console (F12) and check for errors
3. Verify extension is loaded: chrome://extensions/
4. Check background.js API_ENDPOINT matches your server

---

## 📁 Project Structure

```
phishguard/
├── app/                    # FastAPI application
│   ├── main.py            # Entry point
│   ├── api/routes.py      # API endpoints
│   ├── services/          # Business logic
│   │   ├── database.py    # PostgreSQL
│   │   ├── redis.py       # Redis cache
│   │   ├── graph.py       # Graph analysis
│   │   └── scoring.py     # Risk scoring
│   └── models/            # Data models
│
├── aws/Chrome_extensions/ # Chrome extension
│   ├── manifest.json      # Extension config
│   ├── background.js      # API communication
│   ├── content.js         # Page scanner
│   ├── local_inference.js # Local AI
│   └── blocker.js         # Blocking system
│
├── intelligence/          # ML/AI engine
│   └── nlp/
│       └── predictor.py   # Phishing predictor
│
├── docker-compose.yml     # Docker services
├── .env                   # Environment config
├── requirements.txt       # Python dependencies
├── start_all.bat          # Startup script
└── check_status.py        # Status checker
```

---

## ✅ Verification Checklist

Before using the system, verify:

- [ ] Docker Desktop is running
- [ ] PostgreSQL container is up: `docker ps | findstr postgres`
- [ ] Redis container is up: `docker ps | findstr redis`
- [ ] FastAPI server is running: http://localhost:8000/health
- [ ] Chrome extension is loaded: chrome://extensions/
- [ ] Extension can scan pages (check console logs)
- [ ] Results appear in extension popup

---

## 🎯 Success Indicators

When everything is working:

1. ✅ `check_status.py` shows 5/7 services operational
2. ✅ http://localhost:8000/health returns `{"status":"healthy"}`
3. ✅ http://localhost:8000/docs shows API documentation
4. ✅ Chrome extension icon is active
5. ✅ Visiting websites triggers scans (check console)
6. ✅ Extension popup shows scan results
7. ✅ Database stores scan records
8. ✅ Redis caches results

---

## 📞 Quick Commands

```bash
# Check system status
python check_status.py

# Start all services
start_all.bat

# Start FastAPI only
python -m uvicorn app.main:app --reload

# View Docker containers
docker ps

# View API logs
# (Check terminal where uvicorn is running)

# Test API health
curl http://localhost:8000/health

# View API documentation
# Open: http://localhost:8000/docs
```

---

## 🎓 Next Steps

After setup is complete:

1. **Test the Extension**
   - Visit various websites
   - Check scan results in popup
   - Test blocking on test-page.html

2. **Explore API**
   - Open http://localhost:8000/docs
   - Try different endpoints
   - Test with curl/Postman

3. **View Database**
   ```bash
   docker exec -it phishguard-postgres psql -U postgres -d threat_intel
   \dt  # List tables
   SELECT * FROM scans LIMIT 5;
   ```

4. **Monitor Redis**
   ```bash
   docker exec -it phishguard-redis redis-cli
   KEYS *  # List all keys
   GET scan:*  # View cached scans
   ```

5. **Start Dashboard (Optional)**
   ```bash
   cd aws\Chrome_extensions\dashboard
   npm install
   npm run dev
   # Open: http://localhost:5173
   ```

---

## 📚 Documentation

- **INTEGRATION_GUIDE.md** - Complete integration details
- **README.md** - Project overview
- **ARCHITECTURE_DEEP_DIVE.md** - Technical architecture
- **API Docs** - http://localhost:8000/docs

---

**Status**: ✅ Ready to Use
**Version**: 1.0.0
**Last Updated**: 2024

---

## 🎉 You're All Set!

Your PhishGuard system is now fully integrated and ready to protect against phishing threats!

**Start the system:**
```bash
start_all.bat
```

**Load the extension and browse safely!** 🛡️
