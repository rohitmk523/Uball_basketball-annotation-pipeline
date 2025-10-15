"""
Video service for fetching video metadata and GCS URIs.
"""

import logging
from typing import Optional
from supabase import Client

from app.models.schemas import VideoMetadata, CameraAngle

logger = logging.getLogger(__name__)


class VideoService:
    """Service for video operations."""
    
    def __init__(self, supabase: Client):
        """
        Initialize video service.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
    
    async def get_video_metadata(
        self,
        game_id: str,
        angle: CameraAngle
    ) -> Optional[VideoMetadata]:
        """
        Fetch video metadata from Supabase.
        
        Args:
            game_id: Game UUID
            angle: Camera angle
            
        Returns:
            Video metadata or None if not found
        """
        try:
            response = (
                self.supabase.table("video_metadata")
                .select("*")
                .eq("game_id", game_id)
                .eq("angle", angle.value)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                video_data = response.data[0]
                logger.info(f"✓ Found video metadata for game {game_id}, angle {angle}")
                return VideoMetadata(**video_data)
            else:
                logger.warning(f"⚠ No video metadata found for game {game_id}, angle {angle}")
                return None
                
        except Exception as e:
            logger.error(f"✗ Error fetching video metadata: {e}")
            raise
    
    def get_gcs_uri(self, video_metadata: VideoMetadata) -> str:
        """
        Get GCS URI from video metadata.
        
        Args:
            video_metadata: Video metadata
            
        Returns:
            GCS URI string
        """
        return video_metadata.gcs_uri
    
    async def verify_video_exists(self, gcs_uri: str, storage_client) -> bool:
        """
        Verify that video exists in GCS.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            storage_client: GCS storage client
            
        Returns:
            True if video exists, False otherwise
        """
        try:
            # Parse GCS URI
            if not gcs_uri.startswith("gs://"):
                logger.error(f"Invalid GCS URI format: {gcs_uri}")
                return False
            
            # Extract bucket and path
            parts = gcs_uri.replace("gs://", "").split("/", 1)
            if len(parts) != 2:
                logger.error(f"Invalid GCS URI structure: {gcs_uri}")
                return False
            
            bucket_name, blob_path = parts
            
            # Check if blob exists
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            exists = blob.exists()
            
            if exists:
                logger.info(f"✓ Video exists: {gcs_uri}")
            else:
                logger.warning(f"⚠ Video not found: {gcs_uri}")
            
            return exists
            
        except Exception as e:
            logger.error(f"✗ Error checking video existence: {e}")
            return False

