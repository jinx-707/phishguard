"""
Threat feed management and ingestion service.
"""
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import aiohttp
import structlog
from urllib.parse import urlparse

from app.config import settings

logger = structlog.get_logger(__name__)


class ThreatFeedManager:
    """Manage threat feed ingestion and processing."""
    
    def __init__(self):
        self.feeds = []
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def fetch_feed(self, feed_url: str) -> Optional[str]:
        """
        Fetch threat feed data from URL.
        
        Args:
            feed_url: URL of the threat feed
        
        Returns:
            Raw feed data or None if failed
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
            
            async with self.session.get(feed_url) as response:
                if response.status == 200:
                    data = await response.text()
                    logger.info("Feed fetched successfully", url=feed_url, size=len(data))
                    return data
                else:
                    logger.error("Feed fetch failed", url=feed_url, status=response.status)
                    return None
        except Exception as e:
            logger.error("Feed fetch error", url=feed_url, error=str(e))
            return None
    
    def parse_feed(self, data: str, feed_type: str) -> List[Dict[str, Any]]:
        """
        Parse raw feed data into structured format.
        
        Args:
            data: Raw feed data
            feed_type: Type of feed (PHISHING, MALWARE, etc.)
        
        Returns:
            List of parsed threat entries
        """
        entries = []
        lines = data.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            # Extract domain/URL
            value = self._extract_value(line)
            if not value:
                continue
            
            # Create entry
            entry = {
                'value': value,
                'type': feed_type,
                'source': 'threat_feed',
                'timestamp': datetime.utcnow(),
                'hash': self._generate_hash(value, feed_type),
            }
            
            entries.append(entry)
        
        logger.info("Feed parsed", entries=len(entries), feed_type=feed_type)
        return entries
    
    def _extract_value(self, line: str) -> Optional[str]:
        """Extract domain or URL from feed line."""
        # Remove common prefixes
        line = line.replace('http://', '').replace('https://', '')
        
        # Split on whitespace and take first part
        parts = line.split()
        if not parts:
            return None
        
        value = parts[0].strip()
        
        # Basic validation
        if '.' not in value:
            return None
        
        # Extract domain from URL
        try:
            parsed = urlparse(f'http://{value}')
            domain = parsed.netloc or parsed.path.split('/')[0]
            return domain.lower()
        except Exception:
            return value.lower()
    
    def _generate_hash(self, value: str, feed_type: str) -> str:
        """Generate hash for deduplication."""
        data = f"{value}:{feed_type}".encode()
        return hashlib.sha256(data).hexdigest()
    
    async def ingest_feed(self, feed_url: str, feed_type: str = 'PHISHING') -> Dict[str, Any]:
        """
        Ingest a threat feed.
        
        Args:
            feed_url: URL of the threat feed
            feed_type: Type of threats in feed
        
        Returns:
            Ingestion result
        """
        logger.info("Starting feed ingestion", url=feed_url, type=feed_type)
        
        # Fetch feed
        data = await self.fetch_feed(feed_url)
        if not data:
            return {'status': 'failed', 'reason': 'fetch_failed'}
        
        # Parse feed
        entries = self.parse_feed(data, feed_type)
        if not entries:
            return {'status': 'failed', 'reason': 'no_entries'}
        
        # Store entries (would integrate with database)
        stored = await self._store_entries(entries)
        
        return {
            'status': 'success',
            'feed_url': feed_url,
            'feed_type': feed_type,
            'parsed': len(entries),
            'stored': stored,
            'timestamp': datetime.utcnow().isoformat(),
        }
    
    async def _store_entries(self, entries: List[Dict[str, Any]]) -> int:
        """
        Store threat entries in database.
        
        Args:
            entries: List of threat entries
        
        Returns:
            Number of entries stored
        """
        # This would integrate with database service
        # For now, just return count
        stored_count = 0
        
        try:
            from app.services.database import get_db_session
            from app.models.db import Domain
            from sqlalchemy import select
            
            async for session in get_db_session():
                for entry in entries:
                    # Check if domain exists
                    stmt = select(Domain).where(Domain.domain == entry['value'])
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        # Update existing
                        existing.is_malicious = True
                        existing.risk_score = max(existing.risk_score, 0.8)
                        existing.last_seen = entry['timestamp']
                        if 'threat_feed' not in (existing.tags or []):
                            existing.tags = (existing.tags or []) + ['threat_feed']
                    else:
                        # Create new
                        domain = Domain(
                            domain=entry['value'],
                            risk_score=0.8,
                            is_malicious=True,
                            first_seen=entry['timestamp'],
                            last_seen=entry['timestamp'],
                            tags=['threat_feed', entry['type'].lower()],
                            meta={'source': entry['source']},
                        )
                        session.add(domain)
                    
                    stored_count += 1
                
                await session.commit()
                break
        except Exception as e:
            logger.error("Failed to store entries", error=str(e))
        
        return stored_count
    
    async def schedule_feeds(self, feeds: List[Dict[str, Any]]):
        """
        Schedule periodic feed ingestion.
        
        Args:
            feeds: List of feed configurations
        """
        tasks = []
        for feed in feeds:
            task = asyncio.create_task(
                self.ingest_feed(feed['url'], feed.get('type', 'PHISHING'))
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
        logger.info("Feed ingestion completed", total=len(feeds), success=success_count)
        
        return results


# Default threat feeds
DEFAULT_FEEDS = [
    {
        'name': 'PhishTank',
        'url': 'http://data.phishtank.com/data/online-valid.csv',
        'type': 'PHISHING',
        'interval_hours': 1,
    },
    {
        'name': 'OpenPhish',
        'url': 'https://openphish.com/feed.txt',
        'type': 'PHISHING',
        'interval_hours': 1,
    },
    {
        'name': 'URLhaus',
        'url': 'https://urlhaus.abuse.ch/downloads/csv_recent/',
        'type': 'MALWARE',
        'interval_hours': 1,
    },
]


async def ingest_all_feeds():
    """Ingest all configured threat feeds."""
    async with ThreatFeedManager() as manager:
        results = await manager.schedule_feeds(DEFAULT_FEEDS)
        return results
