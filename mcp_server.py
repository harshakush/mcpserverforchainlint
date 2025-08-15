#!/usr/bin/env python3
"""
REST API Server for News and Search Services - ENHANCED VERSION
Handles NewsAPI, RSS feeds, SerpAPI, and event management with improvements
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import feedparser
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("news-search-rest")

app = FastAPI(title="News Search REST API", version="2.0.0")

# --- Configuration and State Management ---

CONFIG_FILE = "config.json"
EVENTS_FILE = "events.json"

def load_config() -> Dict[str, Any]:
    default_config = {
        "default_country": "us",
        "default_language": "en",
        "max_articles": 20,
        "default_rss_feeds": [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss"
        ],
        "api_timeout": 30.0,
        "max_concurrent_requests": 5
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                default_config.update(loaded_config)
                logger.info("Configuration loaded from file")
        else:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info("Created default configuration file")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
    return default_config

def save_config(config: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Config saved")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")

def load_events() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, 'r') as f:
                events = json.load(f)
                logger.info(f"Loaded {len(events)} events from file")
                return events
    except Exception as e:
        logger.error(f"Failed to load events: {e}")
    return []

def save_events(events: List[Dict[str, Any]]):
    try:
        with open(EVENTS_FILE, 'w') as f:
            json.dump(events, f, indent=2)
        logger.info(f"Saved {len(events)} events to file")
    except Exception as e:
        logger.error(f"Failed to save events: {e}")

config = load_config()
events = load_events()

# --- Helper Functions ---

def validate_env_vars():
    required_vars = ["NEWSAPI_KEY", "SERPAPI_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.warning(f"Missing environment variables: {missing}")
        logger.warning("Some functionality may be limited without API keys")
    else:
        logger.info("All required environment variables are set")

validate_env_vars()

# --- REST Endpoints ---

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
    return await get_top_headlines()

@app.get("/rss/feeds")
async def get_rss_feeds():
    results = []
    for feed_url in config["default_rss_feeds"]:
        try:
            result = await parse_rss_feed(feed_url, max_entries=5)
            results.append({"url": feed_url, "data": result})
        except Exception as e:
            results.append({"url": feed_url, "error": str(e)})
    return results

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
def add_event(
    title: str = Body(...),
    date: str = Body(...),
    description: str = Body(""),
    time: str = Body(""),
    location: str = Body("")
):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    if time:
        try:
            datetime.strptime(time, "%H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    event_id = f"event_{len(events) + 1}_{int(datetime.now().timestamp())}"
    event = {
        "id": event_id,
        "title": title,
        "description": description,
        "date": date,
        "time": time,
        "location": location,
        "created_at": datetime.now().isoformat()
    }
    events.append(event)
    save_events(events)
    return {"success": True, "event": event}

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
def update_config(setting: str = Body(...), value: str = Body(...)):
    if setting not in ["default_country", "default_language", "max_articles", "api_timeout"]:
        raise HTTPException(status_code=400, detail=f"Invalid setting: {setting}")
    if setting in ["max_articles", "api_timeout"]:
        try:
            value = float(value) if setting == "api_timeout" else int(value)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid value for {setting}: must be numeric")
    old_value = config.get(setting)
    config[setting] = value
    save_config(config)
    return {"success": True, "setting": setting, "old_value": old_value, "new_value": value}

# --- NewsAPI and SerpAPI Endpoints ---

@app.get("/news/search")
async def search_news(
    query: str = Query(...),
    language: str = Query(config["default_language"]),
    sort_by: str = Query("publishedAt"),
    page_size: int = Query(config["max_articles"], le=100)
):
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
        async with httpx.AsyncClient(timeout=config["api_timeout"]) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="NewsAPI request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NewsAPI request failed: {str(e)}")

@app.get("/news/headlines")
async def get_top_headlines(
    country: str = Query(config["default_country"]),
    category: Optional[str] = Query(None),
    page_size: int = Query(config["max_articles"], le=100)
):
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
        async with httpx.AsyncClient(timeout=config["api_timeout"]) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="NewsAPI request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NewsAPI request failed: {str(e)}")

@app.get("/web/search")
async def search_web(
    query: str = Query(...),
    num_results: int = Query(10, le=100),
    location: Optional[str] = Query(None)
):
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
        async with httpx.AsyncClient(timeout=config["api_timeout"]) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="SerpAPI request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SerpAPI request failed: {str(e)}")

@app.get("/rss/parse")
async def parse_rss_feed(
    url: str = Query(...),
    max_entries: int = Query(10)
):
    try:
        async with httpx.AsyncClient(timeout=config["api_timeout"]) as client:
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
        result = {
            "feed_title": feed.feed.get("title", ""),
            "feed_description": feed.feed.get("description", ""),
            "entries": entries,
            "total_entries": len(entries)
        }
        return result
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="RSS feed request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RSS parsing failed: {str(e)}")

# --- Run with: uvicorn filename:app --reload --port 8000 ---
