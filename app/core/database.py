"""
Supabase database client.
"""

from supabase import create_client, Client
from functools import lru_cache
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_supabase_client() -> Client:
    """
    Get Supabase client instance (cached).
    
    Returns:
        Supabase client
    """
    try:
        # Simple client initialization - compatible with supabase 2.3.0
        client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
        logger.info("✓ Supabase client initialized")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        raise


def get_supabase() -> Client:
    """
    Dependency for getting Supabase client in routes.
    
    Returns:
        Supabase client
    """
    return get_supabase_client()

