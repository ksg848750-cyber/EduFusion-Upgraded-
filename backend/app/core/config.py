import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "EduFusion API"
    API_V1_STR: str = "/api/v1"
    
    # Security / Auth
    JWT_ALGORITHM: str = "RS256"
    JWKS_URL: str  # Required from env
    
    # MongoDB Atlas
    MONGODB_URI: str = "mongodb://localhost:27017"  # Default fallback, overridden by env
    MONGODB_DB_NAME: str = "edufusion_db"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
