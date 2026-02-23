"""
Graph service for threat intelligence.

MVP   → NetworkX (in-memory, loaded from PostgreSQL).
Prod  → Neo4j (persistent, native graph queries via Cypher).

Fixes vs previous version:
  1.  to_undirected() called correctly (was missing parentheses).
  2.  Neo4j driver integrated behind USE_NEO4J feature flag.
  3.  Cluster-density term added to risk formula
      (was absent despite spec: score = malicious*0.5 + centrality*0.3 + cluster*0.2).
  4.  Graph rebuild reads REAL domain/relation rows from PostgreSQL.
  5.  asyncio.get_event_loop() DeprecationWarning fixed (use get_running_loop).
"""
from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import networkx as nx
import structlog

from app.config import settings
from app.services.redis import get_cache, set_cache

logger = structlog.get_logger(__name__)

# Thread pool for CPU-bound NetworkX operations
_executor = ThreadPoolExecutor(max_workers=4)

# Feature flag: set USE_NEO4J=true in env to enable Neo4j driver
_USE_NEO4J = os.getenv("USE_NEO4J", "false").lower() == "true"


# ══════════════════════════════════════════════════════════════════════════════
# Neo4j helper (production path)
# ══════════════════════════════════════════════════════════════════════════════

class _Neo4jClient:
    """Thin wrapper around the official Neo4j async driver."""

    def __init__(self):
        self._driver = None

    async def _get_driver(self):
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore
            uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
            user     = os.getenv("NEO4J_USER",     "neo4j")
            password = os.getenv("NEO4J_PASSWORD",  "neo4j")
            self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            logger.info("Neo4j driver initialised", uri=uri)
        except Exception as e:
            logger.error("Neo4j driver init failed", error=str(e))
        return self._driver

    async def get_domain_risk(self, domain: str) -> float:
        """
        Cypher: count malicious neighbours within 2 hops and compute PageRank.
        Returns a risk score in [0, 1].
        """
        driver = await self._get_driver()
        if driver is None:
            return 0.1

        cypher = """
        MATCH (d:Domain {name: $domain})
        OPTIONAL MATCH (d)-[:RESOLVES_TO|REDIRECTS_TO*1..2]-(n)
        WHERE n.malicious = true
        WITH d, count(n) AS malicious_hops, d.pagerank AS pr
        RETURN
            malicious_hops,
            coalesce(pr, 0.01) AS pagerank
        LIMIT 1
        """
        try:
            async with driver.session() as session:
                result = await session.run(cypher, domain=domain)
                record = await result.single()
                if record is None:
                    return 0.05  # unknown domain → low baseline
                malicious_hops = record["malicious_hops"] or 0
                pagerank       = float(record["pagerank"] or 0.01)
                score = min(1.0, malicious_hops * 0.3 + pagerank * 5.0)
                return round(score, 4)
        except Exception as e:
            logger.warning("Neo4j query failed", error=str(e))
            return 0.1

    async def get_connections(self, domain: str) -> Dict[str, List[str]]:
        """Return inbound / outbound neighbours as lists."""
        driver = await self._get_driver()
        if driver is None:
            return {"inbound": [], "outbound": []}
        cypher_out = "MATCH (d:Domain {name: $domain})-[r]->(n) RETURN n.name AS name LIMIT 50"
        cypher_in  = "MATCH (d:Domain {name: $domain})<-[r]-(n) RETURN n.name AS name LIMIT 50"
        try:
            async with driver.session() as session:
                out_res = await session.run(cypher_out, domain=domain)
                in_res  = await session.run(cypher_in,  domain=domain)
                outbound = [r["name"] async for r in out_res if r["name"]]
                inbound  = [r["name"] async for r in in_res  if r["name"]]
            return {"inbound": inbound, "outbound": outbound}
        except Exception as e:
            logger.warning("Neo4j connection query failed", error=str(e))
            return {"inbound": [], "outbound": []}


_neo4j_client = _Neo4jClient() if _USE_NEO4J else None


# ══════════════════════════════════════════════════════════════════════════════
# NetworkX MVP service
# ══════════════════════════════════════════════════════════════════════════════

class GraphService:
    """Graph-based threat intelligence service (NetworkX MVP / Neo4j production)."""

    def __init__(self):
        self.graph: Optional[nx.DiGraph] = None
        self.graph_loaded = False

    # ── Graph loading ─────────────────────────────────────────────────────────

    async def _ensure_graph_loaded(self):
        """Lazy-load graph: Redis cache → PostgreSQL → fallback sample data."""
        if self.graph_loaded:
            return

        # Try Redis cache first
        cached_graph = await get_cache("graph:data")
        if cached_graph:
            loop = asyncio.get_running_loop()
            self.graph = await loop.run_in_executor(
                _executor, nx.node_link_graph, cached_graph
            )
            self.graph_loaded = True
            logger.info("Graph loaded from Redis cache",
                        nodes=self.graph.number_of_nodes())
            return

        # Build from PostgreSQL
        self.graph = nx.DiGraph()
        await self._build_graph_from_db()

        # Persist to Redis cache
        loop       = asyncio.get_running_loop()
        graph_data = await loop.run_in_executor(
            _executor, nx.node_link_data, self.graph
        )
        await set_cache("graph:data", graph_data, settings.GRAPH_CACHE_TTL)
        self.graph_loaded = True
        logger.info("Graph built and cached",
                    nodes=self.graph.number_of_nodes(),
                    edges=self.graph.number_of_edges())

    async def _build_graph_from_db(self):
        """Populate the graph from PostgreSQL domains + relations tables."""
        try:
            from app.services.database import async_session_maker, init_db
            from app.models.db import Domain, Relation
            from sqlalchemy import select

            if async_session_maker is None:
                await init_db()

            async with async_session_maker() as session:
                # Load domains
                domain_rows = (await session.execute(
                    select(Domain).limit(50_000)
                )).scalars().all()

                for d in domain_rows:
                    self.graph.add_node(
                        d.domain,
                        type="domain",
                        risk=float(d.risk_score or 0.0),
                        malicious=bool(d.is_malicious),
                        db_id=d.id,
                    )

                # Load relations
                rel_rows = (await session.execute(
                    select(Relation).limit(100_000)
                )).scalars().all()

                # Build id → domain name lookup
                id_to_domain = {d.id: d.domain for d in domain_rows}

                for r in rel_rows:
                    src = id_to_domain.get(r.source_domain_id)
                    if src is None:
                        continue
                    if r.target_domain_id and r.target_domain_id in id_to_domain:
                        tgt = id_to_domain[r.target_domain_id]
                        self.graph.add_edge(src, tgt, relation=r.relation_type)
                    elif r.target_ip:
                        self.graph.add_node(r.target_ip, type="ip", malicious=False)
                        self.graph.add_edge(src, r.target_ip, relation="RESOLVES_TO")

            logger.info("Graph built from DB",
                        nodes=self.graph.number_of_nodes(),
                        edges=self.graph.number_of_edges())

        except Exception as e:
            logger.warning("DB graph build failed, using sample data", error=str(e))
            await self._build_fallback_graph()

    def _build_fallback_graph(self):
        """Bootstrap MVP with sample data when DB is unavailable."""
        sample = [
            ("example.com",    "192.168.1.1",    "RESOLVES_TO",  False),
            ("phishing.test",  "192.168.1.2",    "RESOLVES_TO",  True),
            ("malware.test",   "192.168.1.3",    "RESOLVES_TO",  True),
            ("example.com",    "phishing.test",  "REDIRECTS_TO", True),
            ("phishing.test",  "malware.test",   "REDIRECTS_TO", True),
        ]
        for src, tgt, rel, mal in sample:
            self.graph.add_node(src, type="domain", malicious=False)
            self.graph.add_node(tgt, type="ip" if "." in tgt.split(".")[-1] else "domain",
                                malicious=mal)
            self.graph.add_edge(src, tgt, relation=rel)

    async def _build_graph(self):
        """Compat shim — delegates to _build_graph_from_db."""
        await self._build_graph_from_db()

    # ── Risk score ────────────────────────────────────────────────────────────

    async def get_risk_score(self, domain: Optional[str]) -> float:
        """
        Return risk score [0, 1] for a domain.

        Uses Neo4j (Cypher) in production, NetworkX otherwise.

        Formula (NetworkX path):
            score = 0.5 * malicious_neighbors
                  + 0.3 * centrality (PageRank)
                  + 0.2 * cluster_density
        """
        if not domain:
            return 0.0

        # ── Production: Neo4j ─────────────────────────────────────────────
        if _USE_NEO4J and _neo4j_client:
            return await _neo4j_client.get_domain_risk(domain)

        # ── MVP: NetworkX ─────────────────────────────────────────────────
        await self._ensure_graph_loaded()

        if domain not in self.graph:
            return 0.05  # unknown domain → very low baseline

        loop = asyncio.get_running_loop()

        try:
            # PageRank centrality
            pagerank   = await loop.run_in_executor(
                _executor, lambda: nx.pagerank(self.graph, alpha=0.85)
            )
            centrality = pagerank.get(domain, 0.0)

            # Malicious-neighbour ratio
            neighbor_stats = await loop.run_in_executor(
                _executor, self._neighbor_stats_sync, domain
            )
            malicious_count, total_neighbors = neighbor_stats
            mal_ratio = float(malicious_count) / max(float(total_neighbors), 1.0)

            # Cluster (community) density
            cluster_density = await loop.run_in_executor(
                _executor, self._cluster_density_sync, domain
            )

            # Weighted fusion (per spec: 0.5 / 0.3 / 0.2)
            risk_score = min(
                1.0,
                0.5 * mal_ratio + 0.3 * centrality * 10 + 0.2 * cluster_density,
            )
            return round(risk_score, 4)

        except Exception as e:
            logger.error("Graph risk score error", domain=domain, error=str(e))
            return 0.5

    def _neighbor_stats_sync(self, domain: str):
        """Count malicious neighbours and total degree (synchronous)."""
        if domain not in self.graph:
            return 0, 0
        neighbours = list(self.graph.neighbors(domain))
        malicious  = sum(
            1 for n in neighbours
            if self.graph.nodes[n].get("malicious", False)
        )
        return malicious, len(neighbours)

    def _cluster_density_sync(self, domain: str) -> float:
        """
        Return a density measure of the local ego-network around `domain`.
        Density ∈ [0, 1]: high value means the node sits in a dense, tightly
        connected cluster (common in phishing campaign infrastructure).
        """
        try:
            ego   = nx.ego_graph(self.graph, domain, radius=1, undirected=True)
            if ego.number_of_nodes() < 2:
                return 0.0
            density = nx.density(ego)
            return round(float(density), 4)
        except Exception:
            return 0.0

    # ── Domain connections ────────────────────────────────────────────────────

    async def get_domain_connections(self, domain: str) -> Dict[str, List[str]]:
        """Return inbound/outbound neighbours."""
        if _USE_NEO4J and _neo4j_client:
            return await _neo4j_client.get_connections(domain)

        await self._ensure_graph_loaded()
        if domain not in self.graph:
            return {"inbound": [], "outbound": []}

        loop     = asyncio.get_running_loop()
        inbound  = await loop.run_in_executor(
            _executor, lambda: list(self.graph.predecessors(domain))
        )
        outbound = await loop.run_in_executor(
            _executor, lambda: list(self.graph.successors(domain))
        )
        return {"inbound": inbound, "outbound": outbound}

    # ── Central nodes ─────────────────────────────────────────────────────────

    async def get_central_nodes(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Return top-N nodes by PageRank."""
        await self._ensure_graph_loaded()
        loop     = asyncio.get_running_loop()
        pagerank = await loop.run_in_executor(
            _executor, lambda: nx.pagerank(self.graph)
        )
        sorted_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        return [{"domain": n, "centrality": round(s, 6)} for n, s in sorted_nodes[:top_n]]

    # ── Community detection (Louvain) ─────────────────────────────────────────

    async def detect_communities(self) -> Dict[str, List[str]]:
        """
        Detect communities using the Louvain algorithm.

        FIX: `to_undirected` was previously called without `()` — now corrected.
        Falls back gracefully when python-louvain is not installed.
        """
        await self._ensure_graph_loaded()
        loop = asyncio.get_running_loop()

        # run_in_executor(fn) calls fn() — passing bound method returns undirected Graph
        undirected = await loop.run_in_executor(
            _executor, self.graph.to_undirected
        )

        try:
            import community as community_louvain  # python-louvain
            partition = await loop.run_in_executor(
                _executor, community_louvain.best_partition, undirected
            )
            communities: Dict[str, List[str]] = defaultdict(list)
            for node, comm in partition.items():
                communities[f"community_{comm}"].append(node)
            logger.info("Communities detected", count=len(communities))
            return dict(communities)

        except ImportError:
            logger.warning("python-louvain not installed — using nx.community fallback")
            try:
                # Built-in fallback: greedy modularity communities
                comms = await loop.run_in_executor(
                    _executor,
                    lambda: list(nx.community.greedy_modularity_communities(undirected))
                )
                return {f"community_{i}": list(c) for i, c in enumerate(comms)}
            except Exception as e2:
                logger.warning("Community detection fallback failed", error=str(e2))
                return {}

    # ── Path finding ──────────────────────────────────────────────────────────

    async def find_path(self, source: str, target: str, max_length: int = 3) -> Optional[List[str]]:
        """Find shortest path between two nodes in the graph."""
        await self._ensure_graph_loaded()
        loop = asyncio.get_running_loop()
        try:
            path = await loop.run_in_executor(
                _executor,
                lambda: nx.shortest_path(self.graph, source, target)
            )
            return path if len(path) <= max_length + 1 else None
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    # ── Cache invalidation ────────────────────────────────────────────────────

    async def invalidate_cache(self):
        """Force graph reload on next request."""
        self.graph_loaded = False
        self.graph        = None
        logger.info("Graph cache invalidated")
