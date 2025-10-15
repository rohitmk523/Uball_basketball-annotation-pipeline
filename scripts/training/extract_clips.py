"""
Extract video clips for each play from full game videos.

This script:
1. Loads exported plays
2. Downloads full game videos from GCS
3. Extracts clips around each play timestamp
4. Uploads clips to GCS training bucket

Usage:
    python scripts/training/extract_clips.py <plays_json_file>
"""

import os
import sys
import json
import subprocess
import asyncio
import aiofiles
import threading
from pathlib import Path
from typing import Dict, Any, List
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from google.cloud import storage
from supabase import create_client
from tqdm import tqdm
import logging

# Import video cache and retry utilities
try:
    from app.services.video_cache import VideoCache
    from app.utils.retry import exponential_backoff, retry_on_gcs_errors, retry_on_network_errors
except ImportError:
    # Fallback if running from scripts directory
    sys.path.insert(0, str(project_root / "app"))
    from services.video_cache import VideoCache
    from utils.retry import exponential_backoff, retry_on_gcs_errors, retry_on_network_errors

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration
GCS_VIDEO_BUCKET = os.getenv("GCS_VIDEO_BUCKET")
GCS_TRAINING_BUCKET = os.getenv("GCS_TRAINING_BUCKET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
CLIP_PADDING_SECONDS = int(os.getenv("CLIP_EXTRACTION_PADDING_SECONDS", "10"))
OUTPUT_DIR = project_root / "output" / "training_data" / "clips"


class VideoClipExtractor:
    """Extract video clips for training with caching and parallel processing."""
    
    def __init__(self, plays_file: str, max_workers: int = 4):
        """
        Initialize clip extractor.
        
        Args:
            plays_file: Path to plays JSON file
            max_workers: Maximum number of parallel workers
        """
        self.plays_file = Path(plays_file)
        self.plays = self._load_plays()
        self.max_workers = max_workers
        
        # Initialize clients
        self.storage_client = storage.Client()
        self.source_bucket = self.storage_client.bucket(GCS_TRAINING_BUCKET)  # Videos are in training bucket
        self.training_bucket = self.storage_client.bucket(GCS_TRAINING_BUCKET)
        self.supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        
        # Initialize video cache
        self.video_cache = VideoCache(max_cache_size_gb=20)  # 20GB cache
        
        # Create output directory
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Loaded {len(self.plays)} plays from {plays_file}")
        logger.info(f"Parallel workers: {max_workers}")
        
        # Print cache stats
        cache_stats = self.video_cache.get_cache_stats()
        logger.info(f"Video cache: {cache_stats['cached_videos']} videos, {cache_stats['total_size_gb']:.1f}GB")
    
    def _load_plays(self) -> List[Dict[str, Any]]:
        """Load plays from JSON file."""
        with open(self.plays_file, 'r') as f:
            return json.load(f)
    
    def _get_video_gcs_path(self, game_id: str, angle: str) -> str:
        """
        Get GCS path for game video based on the new structure.
        
        Args:
            game_id: Game UUID
            angle: Camera angle (FAR_LEFT, FAR_RIGHT, NEAR_LEFT, NEAR_RIGHT)
            
        Returns:
            GCS blob path
        """
        # Map angle to filename convention
        angle_to_filename = {
            "FAR_LEFT": "game3_farleft.mp4",
            "FAR_RIGHT": "game3_farright.mp4", 
            "NEAR_LEFT": "game3_nearleft.mp4",
            "NEAR_RIGHT": "game3_nearright.mp4"
        }
        
        if angle not in angle_to_filename:
            raise Exception(f"Unknown angle: {angle}. Expected: {list(angle_to_filename.keys())}")
        
        filename = angle_to_filename[angle]
        blob_path = f"{game_id}/{filename}"
        
        logger.debug(f"Video path for {game_id}, {angle}: {blob_path}")
        return blob_path
    
    @retry_on_gcs_errors
    def _get_cached_video(self, game_id: str, angle: str) -> Path:
        """
        Get video from cache or download if needed.
        
        Args:
            game_id: Game UUID
            angle: Camera angle
            
        Returns:
            Path to video file
        """
        # Check cache first
        cached_path = self.video_cache.get_cached_video(game_id, angle)
        if cached_path:
            logger.debug(f"Using cached video: {game_id}_{angle}")
            return cached_path
        
        try:
            blob_path = self._get_video_gcs_path(game_id, angle)
            blob = self.source_bucket.blob(blob_path)
            
            logger.info(f"Downloading and caching video: {blob_path}")
            
            # Download to cache
            cached_path = self.video_cache.cache_video(game_id, angle, blob)
            
            logger.info(f"✓ Video cached: {cached_path}")
            return cached_path
            
        except Exception as e:
            logger.error(f"✗ Failed to get video: {e}")
            raise
    
    @exponential_backoff(max_retries=2, base_delay=1.0, retry_on=(subprocess.CalledProcessError, OSError))
    def _extract_clip(
        self,
        input_video: Path,
        start_timestamp: float,
        end_timestamp: float,
        output_path: Path
    ):
        """
        Extract clip using ffmpeg with start and end timestamps.
        
        Args:
            input_video: Path to input video
            start_timestamp: Start time in seconds
            end_timestamp: End time in seconds
            output_path: Path to save clip
        """
        # Calculate duration
        duration = end_timestamp - start_timestamp
        
        if duration <= 0:
            raise ValueError(f"Invalid duration: {duration}s (start: {start_timestamp}, end: {end_timestamp})")
        
        # ffmpeg command
        cmd = [
            "ffmpeg",
            "-i", str(input_video),
            "-ss", str(start_timestamp),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-strict", "experimental",
            "-y",  # Overwrite output file
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"✓ Extracted clip: {output_path} ({duration:.1f}s)")
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ ffmpeg failed: {e.stderr.decode()}")
            raise
    
    @retry_on_gcs_errors
    def _upload_clip_to_gcs(self, local_path: Path, gcs_path: str):
        """
        Upload clip to GCS training bucket.
        
        Args:
            local_path: Local clip path
            gcs_path: Destination GCS path
        """
        blob = self.training_bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        logger.debug(f"✓ Uploaded to gs://{GCS_TRAINING_BUCKET}/{gcs_path}")
    
    def _process_single_play(self, play: Dict[str, Any], temp_dir: Path) -> Dict[str, Any]:
        """
        Process a single play and extract clips from multiple angles.
        
        Args:
            play: Play data
            temp_dir: Temporary directory for processing
            
        Returns:
            Processing result with success/failure info
        """
        play_id = play["id"]
        play_angle = play["angle"]
        game_id = play["game_id"]
        start_timestamp = play["start_timestamp"]
        end_timestamp = play["end_timestamp"]
        
        result = {
            "play_id": play_id,
            "game_id": game_id,
            "success_count": 0,
            "failed_angles": [],
            "clips_created": []
        }
        
        try:
            # Get training angles for this play
            training_angles = self._get_training_angles(play_angle)
            
            for training_angle in training_angles:
                try:
                    # Get cached video (thread-safe)
                    video_path = self._get_cached_video(game_id, training_angle)
                    
                    # Create unique clip filename
                    clip_filename = f"{play_id}_{training_angle}_{os.getpid()}_{threading.get_ident()}.mp4"
                    local_clip_path = temp_dir / clip_filename
                    
                    # Extract clip
                    self._extract_clip(
                        video_path,
                        start_timestamp,
                        end_timestamp,
                        local_clip_path
                    )
                    
                    # Upload to GCS
                    gcs_clip_path = f"clips/{game_id}/{play_id}/{training_angle}.mp4"
                    self._upload_clip_to_gcs(local_clip_path, gcs_clip_path)
                    
                    # Clean up local clip
                    local_clip_path.unlink()
                    
                    result["success_count"] += 1
                    result["clips_created"].append(f"{training_angle}.mp4")
                    
                except Exception as e:
                    logger.error(f"✗ Failed to extract {training_angle} clip for play {play_id}: {e}")
                    result["failed_angles"].append(training_angle)
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"✗ Failed to process play {play_id}: {e}")
            result["failed_angles"] = ["ALL"]
            return result
    
    def _get_training_angles(self, play_angle: str) -> List[str]:
        """
        Get the camera angles to use for training based on the play's detected angle.
        
        Args:
            play_angle: The angle where the play was detected (LEFT/RIGHT)
            
        Returns:
            List of camera angles to extract clips from
        """
        angle_mapping = {
            "LEFT": ["FAR_LEFT", "NEAR_RIGHT"],    # Opposite perspectives for full court view
            "RIGHT": ["FAR_RIGHT", "NEAR_LEFT"]    # Opposite perspectives for full court view
        }
        
        if play_angle not in angle_mapping:
            logger.warning(f"⚠ Unknown play angle: {play_angle}. Using single angle.")
            return [play_angle]
        
        return angle_mapping[play_angle]

    def extract_all_clips(self):
        """Extract clips for all plays using parallel processing and caching."""
        logger.info("🚀 Starting PARALLEL multi-angle clip extraction...")
        logger.info("Strategy: LEFT → FAR_LEFT + NEAR_RIGHT, RIGHT → FAR_RIGHT + NEAR_LEFT")
        logger.info(f"Parallel workers: {self.max_workers}")
        
        # Group plays by game
        game_plays = {}
        for play in self.plays:
            game_id = play["game_id"]
            if game_id not in game_plays:
                game_plays[game_id] = []
            game_plays[game_id].append(play)
        
        logger.info(f"Processing {len(game_plays)} unique games")
        
        # Calculate total clips needed
        total_clips_needed = 0
        for plays in game_plays.values():
            for play in plays:
                training_angles = self._get_training_angles(play["angle"])
                total_clips_needed += len(training_angles)
        
        logger.info(f"Total clips to extract: {total_clips_needed}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            success_count = 0
            fail_count = 0
            
            for game_id, plays in game_plays.items():
                logger.info(f"\n🎮 Processing game {game_id} ({len(plays)} plays)")
                
                try:
                    # Pre-cache all videos for this game (parallel download)
                    self._precache_game_videos(game_id, plays)
                    
                    # Process plays in parallel
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        # Submit all play processing tasks
                        future_to_play = {
                            executor.submit(self._process_single_play, play, temp_path): play
                            for play in plays
                        }
                        
                        # Process results as they complete
                        for future in tqdm(as_completed(future_to_play), 
                                         total=len(plays), 
                                         desc=f"Extracting clips for {game_id[:8]}"):
                            play = future_to_play[future]
                            try:
                                result = future.result()
                                success_count += result["success_count"]
                                fail_count += len(result["failed_angles"])
                                
                                if result["success_count"] > 0:
                                    logger.debug(f"✓ Play {result['play_id']}: {result['clips_created']}")
                                    
                            except Exception as e:
                                logger.error(f"✗ Play processing failed: {e}")
                                # Count all angles as failed for this play
                                training_angles = self._get_training_angles(play["angle"])
                                fail_count += len(training_angles)
                    
                except Exception as e:
                    logger.error(f"✗ Failed to process game {game_id}: {e}")
                    # Count all clips as failed for this game
                    for play in plays:
                        training_angles = self._get_training_angles(play["angle"])
                        fail_count += len(training_angles)
                    continue
        
        # Print final summary after all games
        logger.info(f"\n{'='*60}")
        logger.info("🚀 PARALLEL MULTI-ANGLE CLIP EXTRACTION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total plays processed: {len(self.plays)}")
        logger.info(f"Total clips needed: {total_clips_needed}")
        logger.info(f"Successfully extracted: {success_count} clips")
        logger.info(f"Failed: {fail_count} clips")
        if total_clips_needed > 0:
            logger.info(f"Success rate: {success_count / total_clips_needed * 100:.1f}%")
        logger.info(f"Strategy: LEFT → FAR_LEFT + NEAR_RIGHT, RIGHT → FAR_RIGHT + NEAR_LEFT")
        logger.info(f"Clips organized in: gs://{GCS_TRAINING_BUCKET}/clips/{{game_id}}/{{play_id}}/{{angle}}.mp4")
        
        # Print cache stats
        cache_stats = self.video_cache.get_cache_stats()
        logger.info(f"Cache efficiency: {cache_stats['cached_videos']} videos, {cache_stats['total_size_gb']:.1f}GB")
        logger.info(f"{'='*60}")
    
    def _precache_game_videos(self, game_id: str, plays: List[Dict[str, Any]]):
        """Pre-cache all required videos for a game in parallel."""
        # Determine all unique angles needed for this game
        required_angles = set()
        for play in plays:
            training_angles = self._get_training_angles(play["angle"])
            required_angles.update(training_angles)
        
        logger.info(f"Pre-caching {len(required_angles)} videos for game {game_id}: {required_angles}")
        
        # Download all videos in parallel
        with ThreadPoolExecutor(max_workers=min(4, len(required_angles))) as executor:
            cache_futures = {
                executor.submit(self._get_cached_video, game_id, angle): angle
                for angle in required_angles
            }
            
            for future in as_completed(cache_futures):
                angle = cache_futures[future]
                try:
                    video_path = future.result()
                    logger.debug(f"✓ Cached video: {game_id}_{angle}")
                except Exception as e:
                    logger.error(f"✗ Failed to cache video {game_id}_{angle}: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract multi-angle video clips with parallel processing")
    parser.add_argument("plays_file", help="Path to plays JSON file")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--cache-size", type=int, default=20, help="Cache size in GB (default: 20)")
    
    args = parser.parse_args()
    
    # Check ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        logger.error("ffmpeg not found. Please install ffmpeg first.")
        sys.exit(1)
    
    logger.info(f"🚀 Starting parallel clip extraction with {args.workers} workers")
    
    # Create extractor with custom settings
    extractor = VideoClipExtractor(args.plays_file, max_workers=args.workers)
    extractor.video_cache.max_cache_size = args.cache_size * 1024 * 1024 * 1024  # Convert to bytes
    
    extractor.extract_all_clips()

