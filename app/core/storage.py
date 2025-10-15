"""
Google Cloud Storage client.
"""

from google.cloud import storage
from functools import lru_cache
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_gcs_client() -> storage.Client:
    """
    Get GCS client instance (cached).
    
    Returns:
        GCS storage client
    """
    try:
        client = storage.Client(project=settings.GCP_PROJECT_ID)
        logger.info("✓ GCS client initialized")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize GCS client: {e}")
        raise


def get_storage() -> storage.Client:
    """
    Dependency for getting GCS client in routes.
    
    Returns:
        GCS storage client
    """
    return get_gcs_client()

