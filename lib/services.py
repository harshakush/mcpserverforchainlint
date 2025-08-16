import os
import asyncio
from typing import Optional, Dict, Any, List
import httpx
from fastapi import HTTPException
from .utils import fetch_single_rss_feed


class NewsAPIService:
    @staticmethod
    async def search_news(query: str, language: str, sort_by: str, page_size: int, timeout: float):
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="NEWSAPI_KEY environment variable not set")
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": page_size,
            "apiKey": api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="NewsAPI request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"NewsAPI request failed: {str(e)}")

    @staticmethod
    async def get_headlines(country: str, category: Optional[str], page_size: int, timeout: float):
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="NEWSAPI_KEY environment variable not set")
        
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": country,
            "pageSize": page_size,
            "apiKey": api_key
        }
        if category:
            params["category"] = category
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="NewsAPI request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"NewsAPI request failed: {str(e)}")


class SerpAPIService:
    @staticmethod
    async def search_web(query: str, num_results: int, location: Optional[str], timeout: float):
        api_key = os.getenv("SERPAPI_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="SERPAPI_KEY environment variable not set")
        
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "num": num_results,
            "api_key": api_key,
            "engine": "google"
        }
        if location:
            params["location"] = location
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="SerpAPI request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"SerpAPI request failed: {str(e)}")


class RSSService:
    @staticmethod
    async def fetch_feeds_concurrent(feed_urls: List[str], max_concurrent: int, timeout: float):
        """Fetch RSS feeds concurrently with improved error handling"""
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def fetch_with_semaphore(feed_url):
                async with semaphore:
                    return await fetch_single_rss_feed(client, feed_url, max_entries=5)
            
            # Fetch all feeds concurrently
            tasks = [fetch_with_semaphore(feed_url) for feed_url in feed_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions that occurred
            processed_results = []
            for result in results:
                if isinstance(result, Exception):
                    processed_results.append({"error": str(result)})
                else:
                    processed_results.append(result)
            
            return {"feeds": processed_results, "total_feeds": len(processed_results)}

    @staticmethod
    async def parse_single_feed(url: str, max_entries: int, timeout: float):
        """Parse RSS feed with URL validation"""
        from .utils import validate_url
        import feedparser
        
        if not validate_url(url):
            raise HTTPException(status_code=400, detail="Invalid or unsafe URL")
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)
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
                "feed_title": feed.feed.get("title", ""),
                "feed_description": feed.feed.get("description", ""),
                "entries": entries,
                "total_entries": len(entries)
            }
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="RSS feed request timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RSS parsing failed: {str(e)}")
