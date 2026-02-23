"""
Threat data ingestion tasks for Celery.
Implements real DB upsert with hash-based deduplication,
exponential backoff retries, graph rebuild, score recalculation,
and actual scan cleanup.
"""
import asyncio
import hashlib
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

import structlog
from celery import Task
from sqlalchemy import create_engine, text, select, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.tasks.celery_app import celery_app
from app.config import settings

logger = structlog.get_logger(__name__)


# ─── Synchronous DB engine for Celery workers ─────────────────────────────────
def _get_sync_engine():
    """Create a synchronous SQLAlchemy engine (psycopg2) for Celery workers."""
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return create_engine(sync_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def _get_sync_session():
    engine = _get_sync_engine()
    Session = sessionmaker(bind=engine, autoflush=False)
    return Session()


# ─── Base task class with on_failure hook ─────────────────────────────────────
class IngestionTask(Task):
    """Base class for ingestion tasks with structured error handling."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Ingestion task failed",
            task_id=task_id,
            error=str(exc),
            args=args,
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "Ingestion task retrying",
            task_id=task_id,
            error=str(exc),
        )


# ─── 1. INGEST FEED ───────────────────────────────────────────────────────────
@celery_app.task(
    bind=True,
    base=IngestionTask,
    name="ingest_feed",
    max_retries=5,
    default_retry_delay=60,          # base delay; doubles per retry
    autoretry_for=(Exception,),
    retry_backoff=True,              # exponential backoff
    retry_backoff_max=600,           # cap at 10 min
    retry_jitter=True,
)
def ingest_feed(self, feed_url: str, feed_type: str = "PHISHING"):
    """
    Fetch a threat feed URL, normalise its entries, deduplicate via SHA-256,
    upsert into the `domains` table, then trigger a graph + score refresh.

    Retries automatically with exponential back-off on any exception.
    """
    logger.info("Starting feed ingestion", feed_url=feed_url, feed_type=feed_type)

    # ── Fetch ────────────────────────────────────────────────────────────────
    response = requests.get(
        feed_url,
        timeout=30,
        headers={"User-Agent": "PhishGuard-ThreatIntel/1.0"},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Feed fetch failed [{response.status_code}] for {feed_url}"
        )

    raw_data = response.text

    # ── Normalise ────────────────────────────────────────────────────────────
    processed = _parse_feed(raw_data, feed_type)
    logger.info("Feed parsed", entries=len(processed), feed_url=feed_url)

    if not processed:
        return {"status": "empty", "feed_url": feed_url, "processed": 0, "stored": 0}

    # ── Upsert into DB ───────────────────────────────────────────────────────
    stored_count = store_threat_data_sync(processed)
    logger.info("Feed ingested", stored=stored_count, feed_url=feed_url)

    # ── Trigger downstream tasks ─────────────────────────────────────────────
    update_graph.delay()
    recalculate_scores.delay()

    return {
        "status": "success",
        "feed_url": feed_url,
        "processed": len(processed),
        "stored": stored_count,
    }


# ─── 2. PARSE FEED ────────────────────────────────────────────────────────────
def _parse_feed(data: str, feed_type: str) -> List[Dict[str, Any]]:
    """
    Convert raw newline-separated feed text into normalised dicts.
    Filters blank lines and comments. Generates SHA-256 hash for dedup.
    """
    entries: List[Dict[str, Any]] = []
    now = datetime.utcnow().isoformat()

    for raw_line in data.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Strip trailing comma / tab metadata (common in CSV feeds)
        domain_or_url = line.split(",")[0].split("\t")[0].strip().lower()
        if not domain_or_url:
            continue

        entry_hash = hashlib.sha256(
            f"{domain_or_url}:{feed_type}".encode()
        ).hexdigest()

        entries.append({
            "value":     domain_or_url,
            "type":      feed_type,
            "source":    "feed",
            "hash":      entry_hash,
            "timestamp": now,
        })

    return entries


# ─── 3. STORE THREAT DATA (SYNC — Celery) ────────────────────────────────────
def store_threat_data_sync(threats: List[Dict[str, Any]]) -> int:
    """
    Upsert threat entries into the `domains` table using PostgreSQL
    INSERT … ON CONFLICT DO NOTHING for idempotent deduplication.

    Returns the number of rows actually inserted (not skipped).
    """
    if not threats:
        return 0

    from app.models.db import Domain

    session = _get_sync_session()
    stored_count = 0

    try:
        for threat in threats:
            domain_value = threat["value"]
            is_malicious = threat["type"] in ("PHISHING", "MALWARE", "RANSOMWARE")
            tag = threat["type"].lower()

            # PostgreSQL upsert: insert new row only if domain is unseen
            stmt = (
                pg_insert(Domain)
                .values(
                    domain=domain_value,
                    risk_score=0.9 if is_malicious else 0.3,
                    is_malicious=is_malicious,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    tags=[tag],
                    meta={"source": threat.get("source", "feed"), "hash": threat["hash"]},
                )
                .on_conflict_do_update(
                    index_elements=["domain"],
                    set_={
                        "last_seen": datetime.utcnow(),
                        "is_malicious": is_malicious,
                        "risk_score": 0.9 if is_malicious else 0.3,
                    }
                )
            )
            result = session.execute(stmt)
            # rowcount == 1 means inserted; == 0 means conflicted/updated
            if result.rowcount and result.rowcount > 0:
                stored_count += 1

        session.commit()
        logger.info("Threat data upserted", inserted=stored_count, total=len(threats))
    except Exception as e:
        session.rollback()
        logger.error("Failed to store threat data", error=str(e))
        raise
    finally:
        session.close()

    return stored_count


# ─── 4. STORE THREAT DATA (ASYNC — non-Celery usage) ─────────────────────────
async def store_threat_data(threats: List[Dict[str, Any]]) -> int:
    """
    Async version of store_threat_data for use outside Celery
    (e.g. FastAPI background tasks).
    Runs the sync version in a thread-pool executor.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, store_threat_data_sync, threats)


# ─── 5. UPDATE GRAPH ─────────────────────────────────────────────────────────
@celery_app.task(
    bind=True,
    name="update_graph",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def update_graph(self):
    """
    Rebuild the in-memory NetworkX threat graph from the current `domains`
    and `relations` PostgreSQL tables, then flush the Redis graph cache
    so the next API call rebuilds it fresh.
    """
    logger.info("Starting graph update")

    from app.models.db import Domain, Relation
    import networkx as nx

    session = _get_sync_session()
    try:
        # ── Load domains ──────────────────────────────────────────────────
        domain_rows = session.execute(
            text("SELECT id, domain, risk_score, is_malicious FROM domains LIMIT 50000")
        ).fetchall()

        # ── Load relations ────────────────────────────────────────────────
        relation_rows = session.execute(
            text(
                "SELECT rd.domain AS src, rt.domain AS tgt, r.relation_type, r.target_ip "
                "FROM relations r "
                "JOIN domains rd ON r.source_domain_id = rd.id "
                "LEFT JOIN domains rt ON r.target_domain_id = rt.id "
                "LIMIT 100000"
            )
        ).fetchall()
    except Exception as e:
        logger.error("Graph update DB query failed", error=str(e))
        session.rollback()
        raise
    finally:
        session.close()

    # ── Build graph ───────────────────────────────────────────────────────
    G = nx.DiGraph()

    for row in domain_rows:
        G.add_node(
            row.domain,
            type="domain",
            risk=float(row.risk_score or 0.0),
            malicious=bool(row.is_malicious),
        )

    nodes_updated = len(domain_rows)

    for row in relation_rows:
        if row.tgt:
            G.add_edge(row.src, row.tgt, relation=row.relation_type)
        elif row.target_ip:
            G.add_node(row.target_ip, type="ip")
            G.add_edge(row.src, row.target_ip, relation=row.relation_type)

    # ── Flush Redis graph cache ───────────────────────────────────────────
    try:
        import redis as sync_redis
        r = sync_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.delete("graph:data")
        r.close()
        logger.info("Graph Redis cache invalidated")
    except Exception as e:
        logger.warning("Could not flush graph cache", error=str(e))

    logger.info(
        "Graph updated",
        nodes=G.number_of_nodes(),
        edges=G.number_of_edges(),
        sourced_from_db=nodes_updated,
    )

    return {
        "status": "success",
        "nodes_updated": nodes_updated,
        "edges": G.number_of_edges(),
    }


# ─── 6. RECALCULATE RISK SCORES ──────────────────────────────────────────────
@celery_app.task(
    bind=True,
    name="recalculate_scores",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def recalculate_scores(self):
    """
    Recompute `risk_score` for every domain in the database using:
        score = 0.5 * is_malicious + 0.3 * neighbor_malicious_ratio + 0.2 baseline
    Batch-updates the `domains` table.
    """
    logger.info("Starting score recalculation")

    session = _get_sync_session()
    scores_updated = 0

    try:
        # Fetch domains with a count of malicious neighbours
        rows = session.execute(
            text("""
                SELECT
                    d.id,
                    d.domain,
                    d.is_malicious,
                    COUNT(CASE WHEN d2.is_malicious THEN 1 END) AS malicious_neighbors,
                    COUNT(r.id) AS total_neighbors
                FROM domains d
                LEFT JOIN relations r ON r.source_domain_id = d.id
                LEFT JOIN domains d2  ON d2.id = r.target_domain_id
                GROUP BY d.id
            """)
        ).fetchall()

        for row in rows:
            neighbor_ratio = (
                row.malicious_neighbors / row.total_neighbors
                if row.total_neighbors else 0.0
            )
            new_score = round(
                0.5 * float(row.is_malicious or 0) +
                0.3 * neighbor_ratio +
                0.2 * 0.1,       # baseline
                4
            )
            new_score = min(new_score, 1.0)

            session.execute(
                text(
                    "UPDATE domains SET risk_score = :score, updated_at = :now "
                    "WHERE id = :id"
                ),
                {"score": new_score, "now": datetime.utcnow(), "id": row.id},
            )
            scores_updated += 1

        session.commit()
        logger.info("Scores recalculated", count=scores_updated)

    except Exception as e:
        session.rollback()
        logger.error("Score recalculation failed", error=str(e))
        raise
    finally:
        session.close()

    return {"status": "success", "scores_updated": scores_updated}


# ─── 7. CLEANUP OLD SCANS ────────────────────────────────────────────────────
@celery_app.task(
    bind=True,
    name="cleanup_old_scans",
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(Exception,),
)
def cleanup_old_scans(self, days: int = 90):
    """
    Hard-delete scan rows older than `days` that have *no* associated user
    feedback (we keep feedback-linked scans for retraining purposes).
    """
    logger.info("Starting scan cleanup", days=days)

    cutoff = datetime.utcnow() - timedelta(days=days)
    session = _get_sync_session()
    deleted = 0

    try:
        result = session.execute(
            text(
                """
                DELETE FROM scans
                WHERE created_at < :cutoff
                  AND scan_id NOT IN (SELECT scan_id FROM feedback)
                """
            ),
            {"cutoff": cutoff},
        )
        deleted = result.rowcount
        session.commit()
        logger.info("Old scans deleted", count=deleted, cutoff=cutoff.isoformat())

    except Exception as e:
        session.rollback()
        logger.error("Scan cleanup failed", error=str(e))
        raise
    finally:
        session.close()

    return {"status": "success", "deleted": deleted, "cutoff": cutoff.isoformat()}
