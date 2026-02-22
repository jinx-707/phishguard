# Phase 5: Real Threat Intelligence Sync Engine ✅

## Overview
Phase 5 adds a sophisticated backend intelligence system that continuously ingests live phishing threat feeds, builds infrastructure relationship graphs, and detects coordinated phishing campaigns. This provides zero-day detection and infrastructure-level threat analysis.

## Architecture

### System Layer
```
Live Threat Feeds (PhishTank, OpenPhish, Custom)
         ↓
Threat Ingestion Pipeline (feeds.py)
         ↓
Threat Database (SQLite/PostgreSQL)
         ↓
Infrastructure Graph Engine (NetworkX)
         ↓
Campaign Detection & Risk Scoring
         ↓
Enhanced API (api_server.py)
         ↓
Extension + Local AI System
```

## Key Components

### 1. Threat Feed Ingestion (`feeds.py`)

**Supported Feed Types**:
- PhishTank public feed
- OpenPhish feed
- Custom curated lists
- Extensible for additional sources

**Features**:
- Async concurrent fetching
- Domain normalization
- Deduplication
- Confidence scoring
- Threat enrichment

**Feed Classes**:
```python
- ThreatFeed (base class)
- PhishTankFeed
- OpenPhishFeed
- CustomFeed
- ThreatFeedAggregator
- ThreatEnricher
```

### 2. Threat Database (`database.py`)

**Schema**:
```sql
Tables:
- domains (domain_id, domain_name, risk_score, confidence, ...)
- ips (ip_id, ip_address, risk_score, ...)
- certificates (cert_id, ssl_fingerprint, issuer, ...)
- domain_ip_relations (links domains to IPs)
- domain_cert_relations (links domains to certificates)
- threat_sources (source_name, confidence_level, ...)
- domain_sources (links domains to sources)
- campaigns (campaign_id, cluster_size, risk_score, ...)
- domain_campaigns (links domains to campaigns)
```

**Features**:
- Structured threat storage
- Relationship tracking
- Incremental updates
- Query optimization with indexes
- Statistics and analytics

### 3. Infrastructure Graph Engine (`graph_engine.py`)

**Graph Structure**:
```
Nodes:
- Domains (with risk_score)
- IPs
- SSL Certificates
- Registrars

Edges:
- Domain → IP (hosts_on)
- Domain → Certificate (uses_cert)
- Domain → Registrar (registered_with)
```

**Features**:
- NetworkX-based graph analysis
- Infrastructure relationship mapping
- Cluster detection
- Campaign identification
- Risk propagation

**Key Methods**:
```python
- add_domain(domain, risk_score)
- link_domain_ip(domain, ip)
- find_domains_sharing_ip(domain)
- find_domains_sharing_cert(domain)
- calculate_infrastructure_risk(domain)
- detect_campaigns(min_cluster_size)
```

### 4. Automated Scheduler (`scheduler.py`)

**Features**:
- Automated threat feed synchronization
- Configurable sync intervals (default: 30 minutes)
- Incremental graph updates
- Campaign detection
- Status monitoring

**Sync Flow**:
```
1. Fetch threats from all feeds
2. Enrich threat data
3. Store in database
4. Update infrastructure graph
5. Detect campaigns
6. Log results
```

### 5. Enhanced API Server (`api_server.py`)

**New Endpoints**:
```
POST /scan - Enhanced with threat intelligence
GET /status - Server and threat intel status
GET /threat-cache - Recent threat data
POST /feedback - User feedback and reports
```

**Enhanced Risk Scoring**:
```python
final_score = 
  0.4 × Threat Intelligence +
  0.2 × Content Analysis (NLP) +
  0.2 × URL Analysis +
  0.2 × DOM Analysis
```

## Infrastructure Risk Scoring

### Risk Factors

**IP Sharing** (up to 0.4):
- Shares IP with known malicious domains
- Weight: 0.15 per malicious neighbor
- Max contribution: 0.4

**Certificate Reuse** (up to 0.3):
- Shares SSL certificate with malicious domains
- Weight: 0.15 per malicious neighbor
- Max contribution: 0.3

**Cluster Size** (0.2):
- Part of large infrastructure cluster (>10 domains)
- Indicates coordinated campaign

**Registrar Patterns** (0.1):
- Registrar associated with many domains (>50)
- Common in phishing operations

### Example Calculation
```python
Domain: suspicious-site.com

Infrastructure Analysis:
- Shares IP with 3 malicious domains → +0.45
- Shares cert with 1 malicious domain → +0.15
- Part of cluster of 15 domains → +0.20
- Suspicious registrar → +0.10

Infrastructure Score: 0.90 (HIGH RISK)
```

## Campaign Detection

### Detection Algorithm
```
1. Build infrastructure graph
2. Find connected components
3. Identify clusters with:
   - Size ≥ min_cluster_size (default: 5)
   - ≥50% malicious domains
4. Assign campaign ID
5. Track campaign metadata
```

### Campaign Metadata
```python
{
  'campaign_id': 1,
  'cluster_size': 12,
  'domains': ['domain1.com', 'domain2.com', ...],
  'avg_risk_score': 0.85,
  'malicious_count': 10,
  'detected_at': '2026-02-14T...'
}
```

## Integration with Detection Pipeline

### Enhanced Scan Flow
```
1. User scans domain
2. Extract domain from URL
3. Check threat intelligence database:
   a. If in database → Use stored risk score (40% weight)
   b. If not in database → Check infrastructure:
      - Find domains sharing IP
      - Find domains sharing certificate
      - Calculate infrastructure risk (20% weight)
4. Perform content analysis (20% weight)
5. Perform URL analysis (10% weight)
6. Perform DOM analysis (10% weight)
7. Combine scores → Final risk verdict
8. Return to extension
```

### Example Response
```json
{
  "risk": "HIGH",
  "confidence": 0.87,
  "reasons": [
    "Domain found in threat database (risk: 0.90)",
    "Shares IP with 3 malicious domain(s)",
    "Found suspicious keywords: verify, urgent",
    "Page contains password input fields"
  ],
  "threat_intel_score": 0.90,
  "total_score": 0.87
}
```

## File Structure

```
Chrome_extensions/backend/
├── threat_intel/
│   ├── feeds.py              # Threat feed ingestion
│   ├── database.py           # Threat database management
│   ├── graph_engine.py       # Infrastructure graph analysis
│   └── scheduler.py          # Automated sync scheduler
│
├── threat_feeds/
│   └── custom_threats.txt    # Custom threat list
│
├── api_server.py             # Enhanced API with threat intel
└── threat_intel.db           # SQLite database (generated)
```

## Usage

### Start Enhanced API Server
```bash
cd Chrome_extensions/backend
python api_server.py
```

Output:
```
🛡️  PhishGuard Enhanced API Server
   Running on http://localhost:8000
   Threat Intelligence: Enabled
   Endpoints:
     POST /scan - Analyze page/email/message
     POST /feedback - Log user feedback
     GET /status - Server status
     GET /threat-cache - Threat intelligence cache

   Waiting for requests...
```

### Manual Threat Sync
```python
from scheduler import ThreatIntelligenceScheduler
from feeds import CustomFeed
import asyncio

scheduler = ThreatIntelligenceScheduler()
scheduler.add_feed(CustomFeed('threat_feeds/custom_threats.txt'))

# Run single sync
result = asyncio.run(scheduler.sync_threats())
print(f"Processed {result['threats_processed']} threats")
```

### Check Domain
```python
# Check if domain is in threat database
result = scheduler.check_domain('phishing-example.com')

if result['in_threat_db']:
    print(f"Risk Score: {result['risk_score']}")
else:
    print(f"Infrastructure Risk: {result['infrastructure_risk']}")
```

### Get Status
```bash
curl http://localhost:8000/status
```

Response:
```json
{
  "server": "PhishGuard API",
  "version": "5.0.0",
  "timestamp": "2026-02-14T...",
  "threat_intelligence": "enabled",
  "threat_intel_status": {
    "is_running": false,
    "last_sync": "2026-02-14T...",
    "sync_count": 1,
    "database": {
      "total_domains": 25,
      "total_ips": 10,
      "total_certificates": 5,
      "total_campaigns": 2,
      "avg_risk_score": 0.82
    },
    "graph": {
      "total_nodes": 40,
      "total_edges": 35,
      "domain_nodes": 25,
      "ip_nodes": 10,
      "certificate_nodes": 5
    }
  }
}
```

## Performance Optimizations

### Async Operations
- Concurrent feed fetching
- Non-blocking database operations
- Async threat enrichment

### Incremental Updates
- Only update changed domains
- Incremental graph building
- Batch database inserts

### Caching
- Query result caching
- Graph computation caching
- Frequent lookup optimization

### Indexing
```sql
CREATE INDEX idx_domain_name ON domains(domain_name);
CREATE INDEX idx_domain_hash ON domains(domain_hash);
CREATE INDEX idx_ip_address ON ips(ip_address);
CREATE INDEX idx_ssl_fingerprint ON certificates(ssl_fingerprint);
```

## Testing

### Test Threat Sync
```bash
cd Chrome_extensions/backend/threat_intel
python scheduler.py
```

### Test Database
```bash
python database.py
```

### Test Graph Engine
```bash
python graph_engine.py
```

### Test API Integration
```bash
# Terminal 1: Start API server
python api_server.py

# Terminal 2: Test scan
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"url": "phishing-example.com", "suspicious_keywords_found": ["verify", "urgent"]}'
```

## Security Considerations

### Data Privacy
- Only malicious domains stored
- No user browsing data retained
- Threat data anonymized

### Database Security
- Parameterized queries (SQL injection prevention)
- Input validation
- Error handling

### API Security
- CORS configured
- Rate limiting (recommended for production)
- Input sanitization

## Deployment

### Production Setup
1. Use PostgreSQL instead of SQLite
2. Configure proper sync intervals (5-10 minutes)
3. Set up monitoring and alerting
4. Enable logging to file
5. Configure backup strategy
6. Use process manager (systemd, supervisor)

### Environment Variables
```bash
export THREAT_DB_PATH=/var/lib/phishguard/threat_intel.db
export SYNC_INTERVAL_MINUTES=10
export API_PORT=8000
```

### Systemd Service
```ini
[Unit]
Description=PhishGuard Threat Intelligence API
After=network.target

[Service]
Type=simple
User=phishguard
WorkingDirectory=/opt/phishguard/backend
ExecStart=/usr/bin/python3 api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Completion Criteria ✅

- [x] Threat feeds auto-sync
- [x] Threat database structured properly
- [x] Infrastructure graph built
- [x] Campaign clusters detected
- [x] Infrastructure score integrated into scan
- [x] System detects domain-level coordination
- [x] No blocking on ingestion
- [x] Stable under repeated updates
- [x] Async operations
- [x] Performance optimized
- [x] Comprehensive documentation

## Future Enhancements

### Advanced Features
- Real-time feed streaming
- Machine learning for campaign detection
- Automated threat hunting
- Threat intelligence sharing (STIX/TAXII)
- Integration with VirusTotal, URLhaus
- Passive DNS integration
- WHOIS data enrichment
- GeoIP analysis

### Scalability
- Distributed graph processing
- Redis caching layer
- Message queue (RabbitMQ/Kafka)
- Horizontal scaling
- Load balancing

---

**Phase 5 Status**: ✅ COMPLETE

PhishGuard now has enterprise-grade threat intelligence capabilities with automated feed ingestion, infrastructure graph analysis, and coordinated campaign detection.
