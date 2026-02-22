# Phase 7 Quick Start - SOC Dashboard

## 🚀 Run the Complete PhishGuard System

### Prerequisites
- Python 3.8+
- Node.js 16+
- pip and npm installed

---

## Step 1: Backend Setup

```bash
cd Chrome_extensions/backend

# Install Python dependencies
pip install -r requirements.txt

# Start the integrated server
python integrated_server.py
```

Server will start on: **http://localhost:8000**

You should see:
```
🛡️  PhishGuard Integrated Server Starting...
   Version: 7.0.0 (Phase 7 - SOC Dashboard)
   Threat Intelligence: ✓ Enabled
   GNN Inference: ✓ Enabled
   SOC Dashboard: ✓ Enabled
```

---

## Step 2: Dashboard Setup

Open a new terminal:

```bash
cd Chrome_extensions/dashboard

# Install Node dependencies
npm install

# Start development server
npm run dev
```

Dashboard will start on: **http://localhost:3000**

---

## Step 3: Access Dashboard

1. Open browser: **http://localhost:3000**

2. Login with demo credentials:
   - **Admin**: `admin` / `admin123`
   - **Analyst**: `analyst` / `analyst123`
   - **Viewer**: `viewer` / `viewer123`

3. Explore the dashboard views:
   - 📊 Overview - Summary statistics
   - ⚡ Live Threats - Real-time feed
   - 🎯 Campaigns - Cluster intelligence
   - 🔗 Infrastructure - Graph visualization
   - 💻 Endpoints - Activity metrics
   - 📈 Trends - Historical analytics
   - 🔍 Investigate - Deep-dive analysis

---

## Step 4: Test API Endpoints

### Get Server Status
```bash
curl http://localhost:8000/status
```

### Scan a Domain
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://suspicious-site.xyz/login",
    "password_fields": 1,
    "suspicious_keywords_found": ["verify", "urgent"]
  }'
```

### Get Dashboard Data (requires auth)
```bash
# First, get token
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | jq -r '.access_token')

# Then use token
curl http://localhost:8000/dashboard/summary \
  -H "Authorization: Bearer $TOKEN"
```

---

## Step 5: View API Documentation

FastAPI provides automatic interactive docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Chrome Extension                      │
│  (content.js, blocker.js, local_inference.js, etc.)    │
└────────────────────┬────────────────────────────────────┘
                     │ POST /scan
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Integrated FastAPI Server                   │
│                  (Port 8000)                            │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Core API Routes                                  │  │
│  │  - /scan (threat detection)                      │  │
│  │  - /feedback                                      │  │
│  │  - /status                                        │  │
│  │  - /gnn/* (GNN endpoints)                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Dashboard API Routes                            │  │
│  │  - /auth/login (JWT)                             │  │
│  │  - /dashboard/* (analytics)                      │  │
│  │  - /ws/dashboard (WebSocket)                     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Intelligence Engines                            │  │
│  │  - GNN Inference (Phase 6)                       │  │
│  │  - Threat Intel (Phase 5)                        │  │
│  │  - Graph Analysis                                │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
                     ↓
┌─────────────────────────────────────────────────────────┐
│              React Dashboard (Vite)                      │
│                  (Port 3000)                            │
│                                                          │
│  Views: Overview, Live Threats, Campaigns, Graph,       │
│         Endpoints, Trends, Investigate                   │
│                                                          │
│  Auth: JWT-based with role-based access control         │
└─────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (need 3.8+)
- Install dependencies: `pip install -r requirements.txt`
- Check port 8000 is free: `lsof -i :8000`

### Dashboard won't start
- Check Node version: `node --version` (need 16+)
- Install dependencies: `npm install`
- Check port 3000 is free: `lsof -i :3000`

### GNN not loading
- Check if model file exists: `backend/ml/models/gnn_model.pt`
- Check if data files exist: `backend/ml/data/*.csv`
- Run demo model creator: `python backend/ml/create_demo_model.py`

### Dashboard can't connect to API
- Verify backend is running on port 8000
- Check vite.config.js proxy settings
- Check browser console for CORS errors

---

## Production Deployment

### Backend
```bash
# Use production ASGI server
pip install gunicorn

# Run with multiple workers
gunicorn integrated_server:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000
```

### Frontend
```bash
# Build for production
npm run build

# Serve with nginx or similar
# Build output in: dashboard/dist/
```

### Environment Variables
```bash
export DASHBOARD_SECRET="your-secret-key-here"
export DATABASE_URL="postgresql://..."
export GNN_MODEL_PATH="/path/to/model.pt"
```

---

## What's Next?

### Phase 8: Federated Learning
- Local model training on endpoints
- Gradient aggregation server
- FedAvg algorithm implementation
- Privacy-preserving updates
- Model versioning and distribution

See the original prompt for Phase 8 details.

---

## Support

For issues or questions:
1. Check logs in terminal
2. Review API docs at /docs
3. Inspect browser console
4. Check PHASE7-COMPLETE.md for details

---

**Enjoy your enterprise-grade phishing detection platform!** 🛡️
