import os
import logging
from urllib.parse import urlparse
from typing import Any, Dict
import httpx
import feedparser

logger = logging.getLogger("news-search-rest")


def validate_env_vars():
    required_vars = ["NEWSAPI_KEY", "SERPAPI_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.warning(f"Missing environment variables: {missing}")
        logger.warning("Some functionality may be limited without API keys")
    else:
        logger.info("All required environment variables are set")


def validate_url(url: str) -> bool:
    """Validate URL to prevent SSRF attacks"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
            return False
        if parsed.hostname and parsed.hostname.startswith('192.168.'):
            return False
        if parsed.hostname and parsed.hostname.startswith('10.'):
            return False
        if parsed.hostname and parsed.hostname.startswith('172.'):
            octets = parsed.hostname.split('.')
            if len(octets) == 4 and 16 <= int(octets[1]) <= 31:
                return False
        return True
    except Exception:
        return False


async def fetch_single_rss_feed(session: httpx.AsyncClient, feed_url: str, max_entries: int = 5) -> Dict[str, Any]:
    """Fetch a single RSS feed with error handling"""
    try:
        if not validate_url(feed_url):
            return {"url": feed_url, "error": "Invalid or unsafe URL"}
        
        response = await session.get(feed_url)
        response.raise_for_status()
        
        feed = feedparser.parse(response.text)
        entries = []
        for entry in feed.entries[:max_entries]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "description": entry.get("description", ""),
                "published": entry.get("published", ""),
                "author": entry.get("author", "")
            })
        
        return {
            "url": feed_url,
            "data": {
                "feed_title": feed.feed.get("title", ""),
                "feed_description": feed.feed.get("description", ""),
                "entries": entries,
                "total_entries": len(entries)
            }
        }
    except Exception as e:
        return {"url": feed_url, "error": str(e)}
