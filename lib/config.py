import os
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger("news-search-rest")

CONFIG_FILE = "config.json"
EVENTS_FILE = "events.json"


def get_default_config() -> Dict[str, Any]:
    return {
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


def load_config() -> Dict[str, Any]:
    default_config = get_default_config()
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
