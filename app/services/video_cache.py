"""
Video caching service for efficient video management.

Reduces video downloads by caching frequently accessed videos
and managing temporary storage efficiently.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict
import tempfile
import threading
from google.cloud import storage

logger = logging.getLogger(__name__)

class VideoCache:
    """Thread-safe video caching system."""
    
    def __init__(self, cache_dir: Optional[Path] = None, max_cache_size_gb: int = 10):
        """
        Initialize video cache.
        
        Args:
            cache_dir: Directory for cache storage (default: temp dir)
            max_cache_size_gb: Maximum cache size in GB
        """
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "uball_video_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_cache_size = max_cache_size_gb * 1024 * 1024 * 1024  # Convert to bytes
        self.cache_index: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        # Initialize cache index
        self._scan_existing_cache()
        
        logger.info(f"VideoCache initialized: {self.cache_dir}, max size: {max_cache_size_gb}GB")
    
    def _scan_existing_cache(self):
        """Scan existing cached files and build index."""
        try:
            for file_path in self.cache_dir.glob("*.mp4"):
                cache_key = file_path.stem
                file_size = file_path.stat().st_size
                modified_time = file_path.stat().st_mtime
                
                self.cache_index[cache_key] = {
                    "path": file_path,
                    "size": file_size,
                    "last_accessed": modified_time
                }
            
            logger.info(f"Found {len(self.cache_index)} cached videos")
            
        except Exception as e:
            logger.warning(f"Failed to scan cache: {e}")
    
    def _generate_cache_key(self, game_id: str, angle: str) -> str:
        """Generate unique cache key for game video."""
        key_string = f"{game_id}_{angle}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _cleanup_cache_if_needed(self, required_space: int):
        """Remove old files if cache is too large."""
        current_size = sum(entry["size"] for entry in self.cache_index.values())
        
        if current_size + required_space > self.max_cache_size:
            logger.info("Cache cleanup needed")
            
            # Sort by last accessed time (oldest first)
            sorted_entries = sorted(
                self.cache_index.items(),
                key=lambda x: x[1]["last_accessed"]
            )
            
            for cache_key, entry in sorted_entries:
                if current_size + required_space <= self.max_cache_size:
                    break
                
                try:
                    entry["path"].unlink()
                    current_size -= entry["size"]
                    del self.cache_index[cache_key]
                    logger.info(f"Removed cached video: {cache_key}")
                except Exception as e:
                    logger.warning(f"Failed to remove cache file: {e}")
    
    def get_cached_video(self, game_id: str, angle: str) -> Optional[Path]:
        """
        Get cached video path if available.
        
        Args:
            game_id: Game UUID
            angle: Camera angle
            
        Returns:
            Path to cached video or None if not cached
        """
        cache_key = self._generate_cache_key(game_id, angle)
        
        with self._lock:
            if cache_key in self.cache_index:
                cached_path = self.cache_index[cache_key]["path"]
                
                if cached_path.exists():
                    # Update last accessed time
                    self.cache_index[cache_key]["last_accessed"] = cached_path.stat().st_mtime
                    logger.debug(f"Cache HIT: {game_id}_{angle}")
                    return cached_path
                else:
                    # File was deleted externally, remove from index
                    del self.cache_index[cache_key]
                    logger.warning(f"Cached file missing: {cache_key}")
            
            logger.debug(f"Cache MISS: {game_id}_{angle}")
            return None
    
    def cache_video(
        self, 
        game_id: str, 
        angle: str, 
        source_blob: storage.Blob,
        progress_callback=None
    ) -> Path:
        """
        Download and cache video from GCS.
        
        Args:
            game_id: Game UUID
            angle: Camera angle
            source_blob: GCS blob to download
            progress_callback: Optional progress callback function
            
        Returns:
            Path to cached video
        """
        cache_key = self._generate_cache_key(game_id, angle)
        cache_path = self.cache_dir / f"{cache_key}.mp4"
        
        # Check if already cached
        existing_path = self.get_cached_video(game_id, angle)
        if existing_path:
            return existing_path
        
        with self._lock:
            # Double-check after acquiring lock
            existing_path = self.get_cached_video(game_id, angle)
            if existing_path:
                return existing_path
            
            try:
                # Get blob size for cleanup check
                blob_size = source_blob.size
                self._cleanup_cache_if_needed(blob_size)
                
                logger.info(f"Downloading video to cache: {game_id}_{angle}")
                
                # Download with progress tracking
                if progress_callback:
                    # For simple implementation, we'll download directly
                    # In a more advanced version, you could implement chunked download with progress
                    source_blob.download_to_filename(cache_path)
                    progress_callback(100)  # Mark as complete
                else:
                    source_blob.download_to_filename(cache_path)
                
                # Update cache index
                self.cache_index[cache_key] = {
                    "path": cache_path,
                    "size": cache_path.stat().st_size,
                    "last_accessed": cache_path.stat().st_mtime
                }
                
                logger.info(f"✓ Video cached: {cache_path}")
                return cache_path
                
            except Exception as e:
                # Clean up partial download
                if cache_path.exists():
                    cache_path.unlink()
                logger.error(f"Failed to cache video: {e}")
                raise
    
    def clear_cache(self):
        """Clear all cached videos."""
        with self._lock:
            for cache_key, entry in list(self.cache_index.items()):
                try:
                    entry["path"].unlink()
                    del self.cache_index[cache_key]
                except Exception as e:
                    logger.warning(f"Failed to delete cache file: {e}")
            
            logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total_size = sum(entry["size"] for entry in self.cache_index.values())
            return {
                "cached_videos": len(self.cache_index),
                "total_size_gb": total_size / (1024 ** 3),
                "max_size_gb": self.max_cache_size / (1024 ** 3),
                "cache_usage_percent": (total_size / self.max_cache_size) * 100 if self.max_cache_size > 0 else 0
            }

# Global cache instance
_video_cache = None

def get_video_cache() -> VideoCache:
    """Get global video cache instance."""
    global _video_cache
    if _video_cache is None:
        _video_cache = VideoCache()
    return _video_cache