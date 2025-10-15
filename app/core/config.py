"""
Application configuration using Pydantic settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000"
    
    # Training Configuration
    TRAINING_MODE: str = "local"  # local or hybrid (cloud uses hybrid)
    TRAINING_WORKFLOW_NAME: str = "hybrid-training-pipeline"  # hybrid workflow
    TRAINING_WORKFLOW_LOCATION: str = "us-central1"
    
    # GCP
    GCP_PROJECT_ID: str
    GCP_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    
    # GCS Buckets
    GCS_VIDEO_BUCKET: str = "uball-videos-production"
    GCS_TRAINING_BUCKET: str = "uball-training-data"
    GCS_MODEL_BUCKET: str = "uball-models"
    
    # Vertex AI
    VERTEX_AI_BASE_MODEL: str = "gemini-1.5-pro-002"
    VERTEX_AI_FINETUNED_ENDPOINT: str = ""
    VERTEX_AI_TRAINING_PIPELINE: str = ""
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str
    
    # Processing Configuration
    MAX_CONCURRENT_ANNOTATIONS: int = 3
    VIDEO_PROCESSING_TIMEOUT_SECONDS: int = 1800
    CLIP_EXTRACTION_PADDING_SECONDS: int = 10
    DEFAULT_CLIP_DURATION_SECONDS: int = 20
    
    # Feature Flags
    ENABLE_PLAYER_MATCHING: bool = True
    ENABLE_AUTO_RETRAINING: bool = False
    
    # Monitoring
    ENABLE_CLOUD_LOGGING: bool = True
    ENABLE_ERROR_REPORTING: bool = True
    SENTRY_DSN: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

