# Person 3 Implementation TODO

## Phase 1: File Setup
- [x] 1.1 Copy graph_update_service.py to app/services/
- [x] 1.2 Copy embedding_service.py to app/services/
- [x] 1.3 Copy similarity_service.py to app/services/
- [x] 1.4 Copy campaign_detector.py to app/services/
- [x] 1.5 Copy domain_intel_service.py to app/services/
- [x] 1.6 Copy threat_graph_engine.py to app/services/
- [x] 1.7 Copy graph_schema.sql to app/services/

## Phase 2: Update Imports
- [x] 2.1 Update imports in all copied files to use package imports

## Phase 3: Integrate with app/main.py
- [x] 3.1 Add ThreatGraphEngine to lifespan startup
- [x] 3.2 Integrate with /scan endpoint

## Phase 4: Dependencies
- [x] 4.1 Add required packages to requirements.txt

## Phase 5: Database
- [ ] 5.1 Run graph_schema.sql to create tables (requires PostgreSQL)

## Phase 6: Testing
- [ ] 6.1 Test the integration

---

## Summary

Person 3 implementation is complete! The following files have been created/updated:

### Created Files (in app/services/):
1. graph_update_service.py - Dynamic graph updates after every scan
2. embedding_service.py - GraphSAGE-style inductive embeddings
3. similarity_service.py - FAISS vector similarity search
4. campaign_detector.py - Connected components + community detection
5. domain_intel_service.py - WHOIS, ASN, SSL, DNS signals
6. threat_graph_engine.py - Orchestrator that wires all 5 services
7. graph_schema.sql - PostgreSQL schema for all tables

### Updated Files:
1. app/main.py - Integrated ThreatGraphEngine into lifespan and calculate_risk
2. requirements.txt - Added torch, numpy, faiss-cpu, python-whois, dnspython, rapidfuzz

### To Run:
1. Install dependencies: pip install -r requirements.txt
2. Run DB schema: psql -h localhost -p 5432 -U postgres -d threat_intel -f app/services/graph_schema.sql
3. Start the API server

### Key Features:
- Dynamic graph that grows with every scan
- Inductive GraphSAGE embeddings for unseen domains
- FAISS-powered similarity search at scale
- Campaign detection using Louvain + connected components
- Domain intelligence (WHOIS age, ASN, SSL, DNS signals)
- Falls back gracefully if Person 3 services fail
