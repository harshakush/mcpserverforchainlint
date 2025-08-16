#!/usr/bin/env python3
"""
REST API Server for News and Search Services - ENHANCED VERSION
Handles NewsAPI, RSS feeds, SerpAPI, and event management with improvements
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

# Import our custom modules
from lib.models import EventCreate, ConfigUpdate, HealthResponse
from lib.config import load_config, save_config, load_events, save_events
from lib.utils import validate_env_vars
from lib.services import NewsAPIService, SerpAPIService, RSSService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("news-search-rest")

app = FastAPI(title="News Search REST API", version="2.0.0")

# Load configuration and events
config = load_config()
events = load_events()

# Validate environment variables
validate_env_vars()

# --- REST Endpoints ---

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for monitoring"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="2.0.0",
        services={
            "newsapi": bool(os.getenv("NEWSAPI_KEY")),
            "serpapi": bool(os.getenv("SERPAPI_KEY"))
        }
    )

@app.get("/resources")
def list_resources():
    return [
        {
            "uri": "news://latest",
            "name": "Latest News",
            "description": "Get latest news articles",
            "mimeType": "application/json",
        },
        {
            "uri": "rss://feeds",
            "name": "RSS Feeds",
            "description": "Access RSS feed data",
            "mimeType": "application/json",
        },
        {
            "uri": "events://calendar",
            "name": "Event Calendar",
            "description": "Manage events and calendar",
            "mimeType": "application/json",
        },
        {
            "uri": "config://settings",
            "name": "Configuration",
            "description": "Server configuration settings",
            "mimeType": "application/json",
        },
    ]

@app.get("/news/latest")
async def get_latest_news():
    return await NewsAPIService.get_headlines(
        country=config["default_country"],
        category=None,
        page_size=config["max_articles"],
        timeout=config["api_timeout"]
    )

@app.get("/news/search")
async def search_news(
    query: str = Query(...),
    language: str = Query(config["default_language"]),
    sort_by: str = Query("publishedAt"),
    page_size: int = Query(config["max_articles"], le=100)
):
    return await NewsAPIService.search_news(
        query=query,
        language=language,
        sort_by=sort_by,
        page_size=page_size,
        timeout=config["api_timeout"]
    )

@app.get("/news/headlines")
async def get_top_headlines(
    country: str = Query(config["default_country"]),
    category: Optional[str] = Query(None),
    page_size: int = Query(config["max_articles"], le=100)
):
    return await NewsAPIService.get_headlines(
        country=country,
        category=category,
        page_size=page_size,
        timeout=config["api_timeout"]
    )

@app.get("/web/search")
async def search_web(
    query: str = Query(...),
    num_results: int = Query(10, le=100),
    location: Optional[str] = Query(None)
):
    return await SerpAPIService.search_web(
        query=query,
        num_results=num_results,
        location=location,
        timeout=config["api_timeout"]
    )

@app.get("/rss/feeds")
async def get_rss_feeds():
    """Fetch RSS feeds concurrently with improved error handling"""
    return await RSSService.fetch_feeds_concurrent(
        feed_urls=config["default_rss_feeds"],
        max_concurrent=config["max_concurrent_requests"],
        timeout=config["api_timeout"]
    )

@app.get("/rss/parse")
async def parse_rss_feed(
    url: str = Query(...),
    max_entries: int = Query(10)
):
    """Parse RSS feed with URL validation"""
    return await RSSService.parse_single_feed(
        url=url,
        max_entries=max_entries,
        timeout=config["api_timeout"]
    )

@app.get("/events")
def get_events(date: Optional[str] = None, days_ahead: int = 7):
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        filtered_events = [event for event in events if event["date"] == date]
    else:
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)
        filtered_events = []
        for event in events:
            try:
                event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
                if today <= event_date <= end_date:
                    filtered_events.append(event)
            except ValueError:
                continue
    filtered_events.sort(key=lambda x: (x["date"], x.get("time", "00:00")))
    return {"events": filtered_events, "total_count": len(filtered_events)}

@app.post("/events")
def add_event(event: EventCreate):
    """Add a new event using Pydantic validation"""
    event_id = f"event_{len(events) + 1}_{int(datetime.now().timestamp())}"
    new_event = {
        "id": event_id,
        "title": event.title,
        "description": event.description,
        "date": event.date,
        "time": event.time,
        "location": event.location,
        "created_at": datetime.now().isoformat()
    }
    events.append(new_event)
    save_events(events)
    return {"success": True, "event": new_event}

@app.delete("/events/{event_id}")
def delete_event(event_id: str):
    for i, event in enumerate(events):
        if event["id"] == event_id:
            deleted_event = events.pop(i)
            save_events(events)
            return {"success": True, "deleted_event": deleted_event}
    raise HTTPException(status_code=404, detail="Event not found")

@app.get("/config")
def get_config():
    return config

@app.post("/config")
def update_config(config_update: ConfigUpdate):
    """Update configuration using Pydantic validation"""
    setting = config_update.setting
    value = config_update.value
    
    # Type conversion for numeric settings
    if setting in ["max_articles", "max_concurrent_requests"]:
        try:
            value = int(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid value for {setting}: must be integer")
    elif setting == "api_timeout":
        try:
            value = float(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid value for {setting}: must be numeric")
    
    old_value = config.get(setting)
    config[setting] = value
    save_config(config)
    return {"success": True, "setting": setting, "old_value": old_value, "new_value": value}

# --- Run with: uvicorn main:app --reload --port 8000 ---
