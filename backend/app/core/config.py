from typing import List, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "EduFusion API"
    API_V1_STR: str = "/api/v1"
    
    # Security / Auth
    JWT_ALGORITHM: Literal["RS256"] = "RS256"
    JWKS_URL: str
    JWT_ISSUER: str = "http://localhost:3000"
    JWT_AUDIENCE: str = "http://localhost:3000"
    
    # MongoDB Atlas
    MONGODB_URI: str = "mongodb://localhost:27017"  # Default fallback, overridden by env
    MONGODB_DB_NAME: str = "edufusion_db"
    MONGODB_TEST_DB_NAME: str = "edufusion_test"
    
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
