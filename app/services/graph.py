"""
Graph service for threat intelligence using NetworkX (MVP) / Neo4j (production).
"""
import asyncio
import networkx as nx
import structlog
from typing import Optional, List, Dict, Any
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.services.redis import get_cache, set_cache

logger = structlog.get_logger(__name__)

# Thread pool for running synchronous NetworkX operations
_executor = ThreadPoolExecutor(max_workers=2)


class GraphService:
    """Graph-based threat intelligence service."""
    
    def __init__(self):
        self.graph = None
        self.graph_loaded = False
    
    async def _ensure_graph_loaded(self):
        """Ensure graph is loaded into memory."""
        if self.graph_loaded:
            return
        
        # Try to load from cache
        cached_graph = await get_cache("graph:data")
        if cached_graph:
            # Run synchronous operation in thread pool
            loop = asyncio.get_event_loop()
            self.graph = await loop.run_in_executor(
                _executor, 
                nx.node_link_graph, 
                cached_graph
            )
            self.graph_loaded = True
            logger.info("Graph loaded from cache")
            return
        
        # Build graph from database (MVP: in-memory)
        self.graph = nx.DiGraph()
        await self._build_graph()
        
        # Cache the graph
        loop = asyncio.get_event_loop()
        graph_data = await loop.run_in_executor(
            _executor, 
            nx.node_link_data, 
            self.graph
        )
        await set_cache("graph:data", graph_data, settings.GRAPH_CACHE_TTL)
        self.graph_loaded = True
        logger.info("Graph built and cached", nodes=self.graph.number_of_nodes())
    
    async def _build_graph(self):
        """Build graph from database (to be implemented)."""
        # In MVP, build from sample data
        # In production, query from Neo4j or PostgreSQL
        sample_domains = [
            ("example.com", "192.168.1.1", "RESOLVES_TO"),
            ("phishing.test", "192.168.1.2", "RESOLVES_TO"),
            ("malware.test", "192.168.1.3", "RESOLVES_TO"),
            ("example.com", "phishing.test", "REDIRECTS_TO"),
            ("phishing.test", "malware.test", "REDIRECTS_TO"),
        ]
        
        # Run synchronous operation in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _executor,
            self._build_graph_sync,
            sample_domains
        )
    
    def _build_graph_sync(self, sample_domains: List[tuple]):
        """Synchronous graph building."""
        for source, target, relation in sample_domains:
            self.graph.add_node(source, type="domain")
            self.graph.add_node(target, type="ip" if "." in target and not "." in target.split(".")[-1] else "domain")
            self.graph.add_edge(source, target, relation=relation)
    
    async def get_risk_score(self, domain: Optional[str]) -> float:
        """Get risk score for a domain using graph centrality."""
        if not domain:
            return 0.0
        
        await self._ensure_graph_loaded()
        
        if domain not in self.graph:
            # Unknown domain - return baseline risk
            return 0.1
        
        try:
            # Run synchronous operation in thread pool
            loop = asyncio.get_event_loop()
            
            # Calculate PageRank centrality
            pagerank = await loop.run_in_executor(
                _executor,
                nx.pagerank,
                self.graph,
                0.85
            )
            centrality = pagerank.get(domain, 0.0)
            
            # Count malicious neighbors
            malicious_count = await loop.run_in_executor(
                _executor,
                self._count_malicious_neighbors_sync,
                domain
            )
            
            # Calculate risk score
            risk_score = min(1.0, (malicious_count * 0.5 + centrality * 0.5))
            return round(risk_score, 3)
        except Exception as e:
            logger.error("Error calculating risk score", error=str(e))
            return 0.5
    
    def _count_malicious_neighbors_sync(self, domain: str) -> int:
        """Count malicious neighbors in the graph (synchronous)."""
        if domain not in self.graph:
            return 0
        
        # In production, check malicious flag from database
        # For MVP, count redirects to known bad domains
        malicious_domains = {"phishing.test", "malware.test", "spam.test"}
        count = 0
        
        for neighbor in self.graph.neighbors(domain):
            if neighbor in malicious_domains:
                count += 1
        
        return count
    
    async def get_domain_connections(self, domain: str) -> Dict[str, List[str]]:
        """Get all connections for a domain."""
        await self._ensure_graph_loaded()
        
        if domain not in self.graph:
            return {"inbound": [], "outbound": []}
        
        loop = asyncio.get_event_loop()
        
        # Run synchronous operations in thread pool
        inbound = await loop.run_in_executor(
            _executor,
            list,
            self.graph.predecessors(domain)
        )
        outbound = await loop.run_in_executor(
            _executor,
            list,
            self.graph.successors(domain)
        )
        
        return {
            "inbound": inbound,
            "outbound": outbound,
        }
    
    async def get_central_nodes(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get most central nodes (by PageRank)."""
        await self._ensure_graph_loaded()
        
        loop = asyncio.get_event_loop()
        pagerank = await loop.run_in_executor(
            _executor,
            nx.pagerank,
            self.graph
        )
        sorted_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"domain": node, "centrality": score}
            for node, score in sorted_nodes[:top_n]
        ]
    
    async def detect_communities(self) -> Dict[str, List[str]]:
        """Detect communities in the graph."""
        await self._ensure_graph_loaded()
        
        # Convert to undirected for community detection
        loop = asyncio.get_event_loop()
        undirected = await loop.run_in_executor(
            _executor,
            self.graph.to_undirected
        )
        
        try:
            import community as community_louvain
            partition = await loop.run_in_executor(
                _executor,
                community_louvain.best_partition,
                undirected
            )
            
            # Group by community
            communities = defaultdict(list)
            for node, comm in partition.items():
                communities[f"community_{comm}"].append(node)
            
            return dict(communities)
        except ImportError:
            logger.warning("python-louvain not installed, skipping community detection")
            return {}
    
    async def find_path(self, source: str, target: str, max_length: int = 3) -> Optional[List[str]]:
        """Find path between two nodes."""
        await self._ensure_graph_loaded()
        
        loop = asyncio.get_event_loop()
        try:
            path = await loop.run_in_executor(
                _executor,
                nx.shortest_path,
                self.graph,
                source,
                target,
                max_length
            )
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    async def invalidate_cache(self):
        """Invalidate graph cache."""
        self.graph_loaded = False
        self.graph = None
        logger.info("Graph cache invalidated")
