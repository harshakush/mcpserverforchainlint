from datetime import datetime
from pydantic import BaseModel, validator


class EventCreate(BaseModel):
    title: str
    date: str
    description: str = ""
    time: str = ""
    location: str = ""
    
    @validator('date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        return v
    
    @validator('time')
    def validate_time(cls, v):
        if v and v.strip():
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                raise ValueError("Invalid time format. Use HH:MM")
        return v


class ConfigUpdate(BaseModel):
    setting: str
    value: str
    
    @validator('setting')
    def validate_setting(cls, v):
        allowed_settings = [
            "default_country", "default_language", "max_articles", 
            "api_timeout", "max_concurrent_requests"
        ]
        if v not in allowed_settings:
            raise ValueError(f"Invalid setting. Allowed: {allowed_settings}")
        return v


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    services: dict
