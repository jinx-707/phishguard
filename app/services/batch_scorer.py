"""
Batch scoring service for processing multiple threats efficiently.
"""
import asyncio
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import structlog

from app.services.graph import GraphService
from app.services.scoring import compute_final_score

logger = structlog.get_logger(__name__)


class BatchScorer:
    """Batch scoring service for efficient threat assessment."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.graph_service = GraphService()
    
    async def score_batch(
        self,
        items: List[Dict[str, Any]],
        include_graph: bool = True,
        include_ml: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Score a batch of items.
        
        Args:
            items: List of items to score (each with 'url', 'text', etc.)
            include_graph: Whether to include graph scoring
            include_ml: Whether to include ML scoring
        
        Returns:
            List of scored results
        """
        logger.info("Starting batch scoring", count=len(items))
        
        # Create tasks for parallel processing
        tasks = []
        for item in items:
            task = self._score_single(item, include_graph, include_ml)
            tasks.append(task)
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Batch scoring error", index=i, error=str(result))
                valid_results.append({
                    'error': str(result),
                    'item': items[i],
                })
            else:
                valid_results.append(result)
        
        logger.info("Batch scoring completed", total=len(items), success=len(valid_results))
        return valid_results
    
    async def _score_single(
        self,
        item: Dict[str, Any],
        include_graph: bool,
        include_ml: bool,
    ) -> Dict[str, Any]:
        """Score a single item."""
        url = item.get('url')
        text = item.get('text', '')
        
        # Get scores
        model_score = 0.5
        graph_score = 0.0
        
        if include_ml:
            model_score = await self._get_ml_score(text, url)
        
        if include_graph and url:
            graph_score = await self.graph_service.get_risk_score(url)
        
        # Compute final score
        risk, confidence, reasons = compute_final_score(model_score, graph_score)
        
        return {
            'item': item,
            'risk': risk.value,
            'confidence': confidence,
            'model_score': model_score,
            'graph_score': graph_score,
            'reasons': reasons,
        }
    
    async def _get_ml_score(self, text: str, url: Optional[str]) -> float:
        """Get ML model score."""
        # Placeholder for ML scoring
        # In production, call actual ML service
        score = 0.5
        
        if url:
            url_lower = url.lower()
            suspicious_patterns = ['login', 'verify', 'secure', 'account']
            for pattern in suspicious_patterns:
                if pattern in url_lower:
                    score += 0.1
        
        if text:
            text_lower = text.lower()
            phishing_keywords = ['urgent', 'suspended', 'verify', 'password']
            keyword_count = sum(1 for kw in phishing_keywords if kw in text_lower)
            score += min(keyword_count * 0.08, 0.3)
        
        return min(score, 0.95)
    
    async def score_domains(self, domains: List[str]) -> List[Dict[str, Any]]:
        """
        Score a batch of domains.
        
        Args:
            domains: List of domain names
        
        Returns:
            List of scored domains
        """
        items = [{'url': domain} for domain in domains]
        return await self.score_batch(items, include_graph=True, include_ml=False)
    
    async def rescore_all(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Rescore all domains in database.
        
        Args:
            limit: Maximum number of domains to rescore
        
        Returns:
            Rescoring statistics
        """
        logger.info("Starting full rescore", limit=limit)
        
        try:
            from app.services.database import get_db_session
            from app.models.db import Domain
            from sqlalchemy import select
            
            async for session in get_db_session():
                # Fetch domains
                stmt = select(Domain)
                if limit:
                    stmt = stmt.limit(limit)
                
                result = await session.execute(stmt)
                domains = result.scalars().all()
                
                logger.info("Fetched domains for rescoring", count=len(domains))
                
                # Score in batches
                batch_size = 100
                updated_count = 0
                
                for i in range(0, len(domains), batch_size):
                    batch = domains[i:i + batch_size]
                    domain_names = [d.domain for d in batch]
                    
                    scores = await self.score_domains(domain_names)
                    
                    # Update database
                    for domain, score_result in zip(batch, scores):
                        domain.risk_score = score_result.get('graph_score', 0.0)
                        updated_count += 1
                    
                    await session.commit()
                
                logger.info("Rescore completed", updated=updated_count)
                
                return {
                    'status': 'success',
                    'total_domains': len(domains),
                    'updated': updated_count,
                }
        except Exception as e:
            logger.error("Rescore failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    def shutdown(self):
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)
