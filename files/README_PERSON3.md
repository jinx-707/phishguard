# Person 3 — Graph & Threat Intelligence Layer

## What This Does

Replaces the static CSV-based graph with a **dynamic, living threat map** that grows with every scan.

Five services, one clean interface:

| File | Purpose |
|------|---------|
| `graph_update_service.py` | Resolves IP + SSL after every scan, updates NetworkX graph + DB |
| `embedding_service.py` | GraphSAGE-style inductive embeddings (works for unseen domains) |
| `similarity_service.py` | FAISS vector similarity search — finds related malicious domains |
| `campaign_detector.py` | Identifies coordinated phishing campaigns via infrastructure clustering |
| `domain_intel_service.py` | WHOIS age, ASN, SSL issuer, DNS TTL — reputation signals |
| `threat_graph_engine.py` | **Orchestrator** — the only file Person 2 needs to import |
| `graph_schema.sql` | Run this once to set up DB tables |

---

## Setup

### 1. Install dependencies
```bash
pip install asyncpg networkx torch numpy faiss-cpu python-whois dnspython rapidfuzz
# Optional for Louvain community detection:
pip install python-louvain
```

### 2. Run DB schema
```bash
psql -h localhost -p 5432 -U postgres -d threat_intel -f graph_schema.sql
```

### 3. Wire into FastAPI
```python
# In your main.py or app startup:
from threat_graph_engine import ThreatGraphEngine

engine = ThreatGraphEngine(db_pool=pool, redis_client=redis)

@app.on_event("startup")
async def startup():
    await engine.startup()

@app.on_event("shutdown")
async def shutdown():
    await engine.shutdown()
```

---

## How Person 2 Uses This

Person 2 only needs `threat_graph_engine.py`. Call it once per scan:

```python
from threat_graph_engine import ThreatGraphEngine

result = await engine.analyze("paypal-secure-login.xyz")

# Use these fields in your meta-model:
result.infrastructure_risk_score   # GNN + campaign signal (0–1)
result.reputation_risk_score       # WHOIS/ASN/SSL signal (0–1)
result.gnn_score                   # Raw GNN similarity score
result.cluster_probability         # How likely it's in a malicious cluster
result.campaign_id                 # Campaign ID if part of known campaign
result.domain_age_days             # Days since registration
result.is_established              # True if domain > 1 year old
result.reasons                     # List of human-readable risk reasons
```

---

## What Changed vs. Old System

| Before | After |
|--------|-------|
| Static CSV loaded at startup | Graph rebuilt from PostgreSQL on startup |
| No new domains added to graph | Every scan updates graph automatically |
| Brute-force cosine similarity | FAISS index (scales to millions) |
| Pretrained fixed embeddings | Inductive GraphSAGE (works for unseen domains) |
| Manual campaign count | Louvain + infrastructure clustering |
| No domain reputation | WHOIS age + ASN + SSL + DNS signals |
| Google.com marked MEDIUM | Established domain check reduces false positives |

---

## Scheduled Jobs (Celery)

Add to your Celery beat schedule:

```python
# Every 6 hours — keeps campaigns current as graph grows
@celery_app.task
async def refresh_campaigns():
    await engine.refresh_campaigns()
```

---

## Key Design Decisions

**Why GraphSAGE (inductive)?**
Old GNN couldn't handle new domains without retraining. GraphSAGE generates embeddings
from node features + neighborhood — works for any domain immediately.

**Why FAISS?**
Brute-force cosine is O(n) per query. FAISS IVF is O(log n). At 10k+ domains,
brute-force becomes a bottleneck. FAISS stays fast.

**Why domain age?**
Most phishing domains are < 7 days old at time of use. This single signal kills
the majority of false negatives in real-world datasets.

**Why not block established domains?**
We don't whitelist — we weight. google.com's established status reduces its risk score
but doesn't disable detection. Compromised legitimate domains still get caught by content layers.
