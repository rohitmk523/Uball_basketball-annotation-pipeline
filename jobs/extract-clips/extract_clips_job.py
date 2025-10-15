"""
Cloud Run Job implementation for video clip extraction.
Adapted from the original extract_clips.py script.
"""

import os
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.cloud import storage
from tqdm import tqdm
import logging

logger = logging.getLogger(__name__)


class ClipExtractorJob:
    """Extract video clips for training in Cloud Run Job environment."""
    
    def __init__(self, game_id: str, plays_file_gcs: str, training_bucket: str, max_workers: int = 4):
        """
        Initialize clip extractor for Cloud Run Job.
        
        Args:
            game_id: Game UUID
            plays_file_gcs: GCS URI to plays JSON file
            training_bucket: GCS bucket name for training data
            max_workers: Maximum number of parallel workers
        """
        self.game_id = game_id
        self.plays_file_gcs = plays_file_gcs
        self.training_bucket_name = training_bucket
        self.max_workers = max_workers
        
        # Initialize GCS client
        self.storage_client = storage.Client()
        self.training_bucket = self.storage_client.bucket(training_bucket)
        
        # Create local working directories
        self.temp_dir = Path("/tmp/clips_job")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Download and load plays data
        self.plays = self._download_and_load_plays()
        
        logger.info(f"✓ Initialized ClipExtractorJob for game {game_id}")
        logger.info(f"✓ Loaded {len(self.plays)} plays from {plays_file_gcs}")
        logger.info(f"✓ Using {max_workers} parallel workers")
    
    def _download_and_load_plays(self) -> List[Dict[str, Any]]:
        """Download plays file from GCS and load JSON data."""
        try:
            # Parse GCS URI
            if not self.plays_file_gcs.startswith("gs://"):
                raise ValueError(f"Invalid GCS URI: {self.plays_file_gcs}")
            
            # Extract bucket and blob path
            path_parts = self.plays_file_gcs[5:].split("/", 1)  # Remove "gs://"
            bucket_name = path_parts[0]
            blob_path = path_parts[1]
            
            # Download from GCS
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            plays_local_path = self.temp_dir / "plays.json"
            blob.download_to_filename(plays_local_path)
            
            logger.info(f"✓ Downloaded plays file to {plays_local_path}")
            
            # Load JSON data
            with open(plays_local_path, 'r') as f:
                plays_data = json.load(f)
            
            return plays_data
            
        except Exception as e:
            logger.error(f"✗ Failed to download plays file: {e}")
            raise
    
    def _get_video_gcs_path(self, game_id: str, angle: str) -> str:
        """Get GCS path for game video based on angle."""
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
        
        return blob_path
    
    def _download_video_if_needed(self, game_id: str, angle: str) -> Path:
        """Download video from GCS if not already cached locally."""
        try:
            # Check if already downloaded
            video_filename = f"{game_id}_{angle}.mp4"
            local_video_path = self.temp_dir / video_filename
            
            if local_video_path.exists():
                logger.debug(f"✓ Using cached video: {local_video_path}")
                return local_video_path
            
            # Download from GCS
            blob_path = self._get_video_gcs_path(game_id, angle)
            
            # Try training bucket first, then video bucket
            try:
                blob = self.training_bucket.blob(blob_path)
                blob.download_to_filename(local_video_path)
                logger.info(f"✓ Downloaded video from training bucket: {blob_path}")
            except Exception:
                # Fallback to video bucket
                video_bucket_name = os.environ.get("GCS_VIDEO_BUCKET", "uball-videos-production")
                video_bucket = self.storage_client.bucket(video_bucket_name)
                blob = video_bucket.blob(blob_path)
                blob.download_to_filename(local_video_path)
                logger.info(f"✓ Downloaded video from video bucket: {blob_path}")
            
            return local_video_path
            
        except Exception as e:
            logger.error(f"✗ Failed to download video {game_id}_{angle}: {e}")
            raise
    
    def _extract_clip(self, input_video: Path, start_timestamp: float, end_timestamp: float, output_path: Path):
        """Extract clip using ffmpeg."""
        duration = end_timestamp - start_timestamp
        
        if duration <= 0:
            raise ValueError(f"Invalid duration: {duration}s")
        
        # ffmpeg command
        cmd = [
            "ffmpeg",
            "-i", str(input_video),
            "-ss", str(start_timestamp),
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-strict", "experimental",
            "-y",  # Overwrite output
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"✓ Extracted clip: {output_path} ({duration:.1f}s)")
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ ffmpeg failed: {e.stderr.decode()}")
            raise
    
    def _upload_clip_to_gcs(self, local_path: Path, gcs_path: str):
        """Upload clip to GCS training bucket."""
        try:
            blob = self.training_bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)
            logger.debug(f"✓ Uploaded to gs://{self.training_bucket_name}/{gcs_path}")
        except Exception as e:
            logger.error(f"✗ Upload failed: {e}")
            raise
    
    def _get_training_angles(self, play_angle: str) -> List[str]:
        """Get camera angles to use for training based on play's detected angle."""
        angle_mapping = {
            "LEFT": ["FAR_LEFT", "NEAR_RIGHT"],
            "RIGHT": ["FAR_RIGHT", "NEAR_LEFT"]
        }
        
        if play_angle not in angle_mapping:
            logger.warning(f"⚠ Unknown play angle: {play_angle}. Using single angle.")
            return [play_angle]
        
        return angle_mapping[play_angle]
    
    def _process_single_play(self, play: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single play and extract clips from multiple angles."""
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
            training_angles = self._get_training_angles(play_angle)
            
            for training_angle in training_angles:
                try:
                    # Download video if needed
                    video_path = self._download_video_if_needed(game_id, training_angle)
                    
                    # Create unique clip filename
                    clip_filename = f"{play_id}_{training_angle}_{os.getpid()}_{threading.get_ident()}.mp4"
                    local_clip_path = self.temp_dir / clip_filename
                    
                    # Extract clip
                    self._extract_clip(video_path, start_timestamp, end_timestamp, local_clip_path)
                    
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
    
    def extract_all_clips(self) -> Dict[str, Any]:
        """Extract clips for all plays using parallel processing."""
        logger.info(f"🚀 Starting parallel clip extraction for {len(self.plays)} plays")
        
        success_count = 0
        fail_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all play processing tasks
            future_to_play = {
                executor.submit(self._process_single_play, play): play
                for play in self.plays
            }
            
            # Process results with progress bar
            for future in tqdm(as_completed(future_to_play), total=len(self.plays), desc="Extracting clips"):
                play = future_to_play[future]
                try:
                    result = future.result()
                    success_count += result["success_count"]
                    fail_count += len(result["failed_angles"])
                    
                    if result["success_count"] > 0:
                        logger.debug(f"✓ Play {result['play_id']}: {result['clips_created']}")
                        
                except Exception as e:
                    logger.error(f"✗ Play processing failed: {e}")
                    training_angles = self._get_training_angles(play["angle"])
                    fail_count += len(training_angles)
        
        # Calculate total clips needed
        total_clips_needed = 0
        for play in self.plays:
            training_angles = self._get_training_angles(play["angle"])
            total_clips_needed += len(training_angles)
        
        # Final summary
        logger.info(f"🎉 CLIP EXTRACTION COMPLETE")
        logger.info(f"📊 Total plays processed: {len(self.plays)}")
        logger.info(f"📊 Total clips needed: {total_clips_needed}")
        logger.info(f"📊 Successfully extracted: {success_count} clips")
        logger.info(f"📊 Failed: {fail_count} clips")
        if total_clips_needed > 0:
            success_rate = (success_count / total_clips_needed) * 100
            logger.info(f"📊 Success rate: {success_rate:.1f}%")
        
        return {
            "success": True,
            "game_id": self.game_id,
            "total_plays": len(self.plays),
            "total_clips_needed": total_clips_needed,
            "clips_extracted": success_count,
            "clips_failed": fail_count,
            "success_rate": (success_count / total_clips_needed * 100) if total_clips_needed > 0 else 0,
            "clips_location": f"gs://{self.training_bucket_name}/clips/{self.game_id}/"
        }