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
    
    def __init__(self, game_id: str, plays_file_gcs: str, training_bucket: str, max_workers: int = 4, skip_if_exists: bool = True):
        """
        Initialize clip extractor for Cloud Run Job.
        
        Args:
            game_id: Game UUID
            plays_file_gcs: GCS URI to plays JSON file
            training_bucket: GCS bucket name for training data
            max_workers: Maximum number of parallel workers
            skip_if_exists: Skip extraction if clips already exist
        """
        self.game_id = game_id
        self.plays_file_gcs = plays_file_gcs
        self.training_bucket_name = training_bucket
        self.max_workers = max_workers
        self.skip_if_exists = skip_if_exists
        
        # Initialize GCS client
        self.storage_client = storage.Client()
        self.training_bucket = self.storage_client.bucket(training_bucket)
        
        # Game-based directory structure
        self.game_dir = f"games/{game_id}"
        self.clips_dir = f"{self.game_dir}/clips"
        
        # Create local working directories
        self.temp_dir = Path("/tmp/clips_job")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Download and load plays data
        self.plays = self._download_and_load_plays()
        
        logger.info(f"✓ Initialized ClipExtractorJob for game {game_id}")
        logger.info(f"✓ Loaded {len(self.plays)} plays from {plays_file_gcs}")
        logger.info(f"✓ Using {max_workers} parallel workers")
        logger.info(f"✓ Clips will be saved to: gs://{training_bucket}/{self.clips_dir}/")
        
        # Validate that required videos exist
        self._validate_required_videos()
    
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
        """Get GCS path for game video based on angle using Games/{game_id}/ structure."""
        # Try different naming patterns in order of preference
        angle_suffix_map = {
            "FAR_LEFT": "farleft",
            "FAR_RIGHT": "farright", 
            "NEAR_LEFT": "nearleft",
            "NEAR_RIGHT": "nearright"
        }
        
        if angle not in angle_suffix_map:
            raise Exception(f"Unknown angle: {angle}. Expected: {list(angle_suffix_map.keys())}")
        
        angle_suffix = angle_suffix_map[angle]
        
        # Get video bucket to check which naming pattern exists
        video_bucket_name = os.getenv("GCS_VIDEO_BUCKET", "uball-videos-production")
        video_bucket = self.storage_client.bucket(video_bucket_name)
        
        # Try different naming patterns
        naming_patterns = [
            f"test_{angle_suffix}.mp4",      # test_farleft.mp4
            f"game1_{angle_suffix}.mp4",     # game1_farleft.mp4  
            f"game2_{angle_suffix}.mp4",     # game2_farleft.mp4
            f"game3_{angle_suffix}.mp4",     # game3_farleft.mp4
            f"{angle_suffix}.mp4",           # farleft.mp4
            f"{angle}.mp4",                  # FAR_LEFT.mp4
        ]
        
        for pattern in naming_patterns:
            blob_path = f"Games/{game_id}/{pattern}"
            blob = video_bucket.blob(blob_path)
            if blob.exists():
                logger.debug(f"✓ Found video with pattern: {pattern}")
                return blob_path
        
        # If no pattern found, return the first pattern for error reporting
        return f"Games/{game_id}/{naming_patterns[0]}"
    
    def _download_video_if_needed(self, game_id: str, angle: str) -> Path:
        """Download video from GCS if not already cached locally."""
        try:
            # Check if already downloaded
            video_filename = f"{game_id}_{angle}.mp4"
            local_video_path = self.temp_dir / video_filename
            
            if local_video_path.exists():
                logger.debug(f"✓ Using cached video: {local_video_path}")
                return local_video_path
            
            # Download from GCS video bucket
            blob_path = self._get_video_gcs_path(game_id, angle)
            
            # Get video bucket from environment
            video_bucket_name = os.getenv("GCS_VIDEO_BUCKET", "uball-videos-production") 
            video_bucket = self.storage_client.bucket(video_bucket_name)
            
            try:
                blob = video_bucket.blob(blob_path)
                blob.download_to_filename(local_video_path)
                logger.info(f"✓ Downloaded video: gs://{video_bucket_name}/{blob_path}")
            except Exception as e:
                logger.error(f"✗ Failed to download video gs://{video_bucket_name}/{blob_path}: {e}")
                raise
            
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
    
    def _save_game_metadata(self, success_count: int, fail_count: int, total_needed: int):
        """Save game metadata and plays list to GCS."""
        import datetime
        
        metadata = {
            "game_id": self.game_id,
            "extraction_timestamp": datetime.datetime.utcnow().isoformat(),
            "total_plays": len(self.plays),
            "total_clips_needed": total_needed,
            "clips_extracted": success_count,
            "clips_failed": fail_count,
            "success_rate": (success_count / total_needed * 100) if total_needed > 0 else 0,
            "plays": self.plays
        }
        
        try:
            # Save metadata
            metadata_path = f"{self.game_dir}/metadata.json"
            blob = self.training_bucket.blob(metadata_path)
            blob.upload_from_string(json.dumps(metadata, indent=2))
            logger.info(f"✓ Saved game metadata to gs://{self.training_bucket_name}/{metadata_path}")
            
            # Save plays list separately for easy access
            plays_path = f"{self.game_dir}/plays.json"
            blob = self.training_bucket.blob(plays_path)
            blob.upload_from_string(json.dumps(self.plays, indent=2))
            logger.info(f"✓ Saved plays data to gs://{self.training_bucket_name}/{plays_path}")
            
        except Exception as e:
            logger.error(f"✗ Failed to save game metadata: {e}")

    def _validate_required_videos(self):
        """Validate that all required video files exist in GCS before starting extraction."""
        logger.info("🔍 Validating video files exist in GCS...")
        
        # Get video bucket from env
        video_bucket_name = os.getenv("GCS_VIDEO_BUCKET", "uball-videos-production")
        video_bucket = self.storage_client.bucket(video_bucket_name)
        
        # Get all unique angles from plays
        required_angles = set()
        for play in self.plays:
            training_angles = self._get_training_angles(play["angle"])
            required_angles.update(training_angles)
        
        logger.info(f"🎯 Required video angles for this game: {sorted(required_angles)}")
        
        missing_videos = []
        found_videos = []
        
        for angle in required_angles:
            try:
                video_path = self._get_video_gcs_path(self.game_id, angle)
                blob = video_bucket.blob(video_path)
                
                if blob.exists():
                    # Check if file is not empty
                    blob.reload()
                    if blob.size > 0:
                        found_videos.append(f"gs://{video_bucket_name}/{video_path}")
                        logger.info(f"✓ Found video: gs://{video_bucket_name}/{video_path} ({blob.size} bytes)")
                    else:
                        missing_videos.append(f"gs://{video_bucket_name}/{video_path} (empty file)")
                        logger.error(f"✗ Empty video file: gs://{video_bucket_name}/{video_path}")
                else:
                    missing_videos.append(f"gs://{video_bucket_name}/{video_path}")
                    logger.error(f"✗ Missing video: gs://{video_bucket_name}/{video_path}")
                    
            except Exception as e:
                missing_videos.append(f"gs://{video_bucket_name}/{video_path} (error: {e})")
                logger.error(f"✗ Error checking video {angle}: {e}")
        
        # Report results
        logger.info(f"📊 Video validation results:")
        logger.info(f"  ✅ Found videos: {len(found_videos)}")
        logger.info(f"  ❌ Missing videos: {len(missing_videos)}")
        
        if missing_videos:
            error_msg = f"Missing required video files:\n" + "\n".join([f"  - {video}" for video in missing_videos])
            error_msg += f"\n\nExpected path structure: gs://{video_bucket_name}/Games/{self.game_id}/{{angle}}.mp4"
            error_msg += f"\nRequired angles: {sorted(required_angles)}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        logger.info("✅ All required videos found and validated!")

    
    def _get_training_angles(self, play_angle: str) -> List[str]:
        """Get camera angles to use for training based on play's detected angle."""
        angle_mapping = {
            "LEFT": ["FAR_LEFT", "NEAR_RIGHT"],
            "RIGHT": ["FAR_RIGHT", "NEAR_LEFT"]
        }
        
        if play_angle not in angle_mapping:
            raise ValueError(f"Invalid play angle: {play_angle}. Expected: {list(angle_mapping.keys())}")
        
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
                    
                    # Upload to GCS using game-based structure
                    gcs_clip_path = f"{self.clips_dir}/{play_id}_{training_angle}.mp4"
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
    
    def _check_existing_clips(self) -> Dict[str, Any]:
        """Check if clips already exist for this game."""
        logger.info(f"🔍 Checking for existing clips for game: {self.game_id}")
        
        try:
            # List all blobs in the clips directory
            clips_prefix = f"{self.clips_dir}/"
            blobs = list(self.training_bucket.list_blobs(prefix=clips_prefix))
            
            # Filter out directories (blobs ending with /)
            clip_files = [blob for blob in blobs if not blob.name.endswith('/') and blob.name.endswith('.mp4')]
            
            clips_count = len(clip_files)
            total_needed = 0
            
            # Calculate how many clips we should have
            for play in self.plays:
                training_angles = self._get_training_angles(play["angle"])
                total_needed += len(training_angles)
            
            logger.info(f"📊 Found {clips_count} existing clips, need {total_needed} total clips")
            
            # Check if we have enough clips (allowing for some tolerance)
            clips_exist = clips_count >= total_needed * 0.9  # 90% threshold
            
            if clips_exist:
                logger.info(f"✅ Sufficient clips already exist ({clips_count}/{total_needed})")
                return {
                    "clips_exist": True,
                    "existing_count": clips_count,
                    "needed_count": total_needed,
                    "clip_files": [blob.name for blob in clip_files[:10]]  # Show first 10
                }
            else:
                logger.info(f"⚠️ Not enough clips exist ({clips_count}/{total_needed}), will extract")
                return {
                    "clips_exist": False,
                    "existing_count": clips_count,
                    "needed_count": total_needed
                }
                
        except Exception as e:
            logger.warning(f"Could not check existing clips: {e}, proceeding with extraction")
            return {"clips_exist": False, "existing_count": 0, "needed_count": 0}

    def _create_vertex_ai_jsonl_files(self) -> Dict[str, Any]:
        """Create Vertex AI training JSONL files from clips and plays data."""
        logger.info("📝 Creating Vertex AI training JSONL files from clips...")
        
        try:
            import datetime
            import random
            
            # Split plays into training (80%) and validation (20%)
            random.seed(42)  # For reproducible splits
            shuffled_plays = self.plays.copy()
            random.shuffle(shuffled_plays)
            
            split_idx = int(len(shuffled_plays) * 0.8)
            training_plays = shuffled_plays[:split_idx]
            validation_plays = shuffled_plays[split_idx:]
            
            logger.info(f"📊 Split: {len(training_plays)} training plays, {len(validation_plays)} validation plays")
            
            # Create training and validation datasets
            training_examples = self._create_jsonl_examples(training_plays, "training")
            validation_examples = self._create_jsonl_examples(validation_plays, "validation")
            
            # Upload JSONL files to GCS
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            training_file = f"video_training_{self.game_id}_{timestamp}.jsonl"
            validation_file = f"video_validation_{self.game_id}_{timestamp}.jsonl"
            
            training_path = f"{self.game_dir}/{training_file}"
            validation_path = f"{self.game_dir}/{validation_file}"
            
            # Upload training file
            self._upload_jsonl_to_gcs(training_examples, training_path)
            logger.info(f"✅ Uploaded training file: gs://{self.training_bucket_name}/{training_path}")
            
            # Upload validation file  
            self._upload_jsonl_to_gcs(validation_examples, validation_path)
            logger.info(f"✅ Uploaded validation file: gs://{self.training_bucket_name}/{validation_path}")
            
            return {
                "success": True,
                "training_file": f"gs://{self.training_bucket_name}/{training_path}",
                "validation_file": f"gs://{self.training_bucket_name}/{validation_path}",
                "training_examples": len(training_examples),
                "validation_examples": len(validation_examples)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create JSONL files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_jsonl_examples(self, plays: List[Dict[str, Any]], dataset_type: str) -> List[Dict[str, Any]]:
        """Create JSONL examples in Vertex AI format for given plays."""
        examples = []
        
        for play in plays:
            try:
                play_examples = self._create_single_jsonl_example(play)
                if play_examples:
                    examples.extend(play_examples)  # Add all examples from this play
            except Exception as e:
                logger.warning(f"⚠️ Failed to create JSONL example for play {play.get('id')}: {e}")
                continue
        
        logger.info(f"✅ Created {len(examples)} {dataset_type} examples")
        return examples
    
    def _create_single_jsonl_example(self, play: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create JSONL examples in Vertex AI format (one per camera angle)."""
        play_id = play["id"]
        play_angle = play["angle"]
        
        # Get training angles for this play
        training_angles = self._get_training_angles(play_angle)
        
        examples = []
        
        # Create separate example for each camera angle (Vertex AI limit: 1 video per example)
        for angle in training_angles:
            clip_uri = f"gs://{self.training_bucket_name}/{self.clips_dir}/{play_id}_{angle}.mp4"
        
            # Basketball-specific prompt based on your classification system
            prompt_text = f"""Analyze this basketball game video from {angle} camera angle and identify the play with its events.

This is a {angle} camera view that provides {'wide court view and team formation context' if 'FAR' in angle else 'close-up details of player numbers and jerseys'}.

For the play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FOUL, REBOUND, ASSIST, etc.)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type (same options as classification)
   - playerA: Player identifier (format: "Player #X (Color Team)")
   - playerB: Secondary player if applicable

Return a JSON array with the single play. Be precise with timestamps and identify all basketball events."""

            # Build expected output (model response) from play data
            expected_response = {
                "timestamp_seconds": play.get("timestamp_seconds"),
                "classification": play.get("classification"),
                "note": play.get("note"),
                "player_a": play.get("player_a"),
                "player_b": play.get("player_b"),
                "events": play.get("events", [])
            }
            
            # Create Vertex AI format example with single video
            example = {
                "contents": [
                    {
                        "role": "user", 
                        "parts": [
                            {
                                "fileData": {
                                    "fileUri": clip_uri,
                                    "mimeType": "video/mp4"
                                }
                            },
                            {"text": prompt_text}
                        ]
                    },
                    {
                        "role": "model",
                        "parts": [
                            {
                                "text": json.dumps([expected_response])  # Array with single play
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "mediaResolution": "MEDIA_RESOLUTION_MEDIUM"
                }
            }
            
            examples.append(example)
        
        return examples
    
    def _upload_jsonl_to_gcs(self, examples: List[Dict[str, Any]], gcs_path: str):
        """Upload JSONL examples to GCS.""" 
        import tempfile
        
        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as temp_file:
            for example in examples:
                temp_file.write(json.dumps(example) + '\n')
            temp_file_path = temp_file.name
        
        try:
            # Upload to GCS
            blob = self.training_bucket.blob(gcs_path)
            blob.upload_from_filename(temp_file_path)
            logger.debug(f"✅ Uploaded JSONL file: gs://{self.training_bucket_name}/{gcs_path}")
        finally:
            # Clean up temporary file
            Path(temp_file_path).unlink()

    def extract_all_clips(self) -> Dict[str, Any]:
        """Extract clips for all plays using parallel processing with smart skipping."""
        logger.info(f"🚀 Starting intelligent clip extraction for {len(self.plays)} plays")
        
        # Check if clips already exist (if enabled)
        if self.skip_if_exists:
            clip_check = self._check_existing_clips()
            
            if clip_check.get("clips_exist", False):
                logger.info(f"🎯 Clips already exist, skipping extraction and creating training JSONL files")
                
                # Create training data files from existing clips
                jsonl_result = self._create_vertex_ai_jsonl_files()
                
                # Return summary of existing clips + JSONL creation
                result = {
                    "success": True,
                    "game_id": self.game_id,
                    "total_plays": len(self.plays),
                    "total_clips_needed": clip_check["needed_count"],
                    "clips_extracted": 0,  # None extracted this run
                    "clips_existing": clip_check["existing_count"],
                    "clips_failed": 0,
                    "success_rate": 100.0,
                    "clips_location": f"gs://{self.training_bucket_name}/{self.clips_dir}/",
                    "skipped_extraction": True,
                    "message": "Clips already exist, skipped extraction"
                }
                
                # Add JSONL creation results
                if jsonl_result.get("success"):
                    result["training_file"] = jsonl_result["training_file"]
                    result["validation_file"] = jsonl_result["validation_file"]
                    result["training_examples"] = jsonl_result["training_examples"]
                    result["validation_examples"] = jsonl_result["validation_examples"]
                    result["message"] = "Clips existed, created training JSONL files"
                else:
                    result["jsonl_error"] = jsonl_result.get("error")
                    result["message"] = "Clips existed, but JSONL creation failed"
                
                return result
            
            logger.info(f"🎬 Proceeding with clip extraction ({clip_check['existing_count']} existing)")
        else:
            logger.info(f"🎬 Skip check disabled, proceeding with extraction")
            clip_check = {"existing_count": 0}
        
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
        
        # Save game metadata
        self._save_game_metadata(success_count, fail_count, total_clips_needed)
        
        # Create Vertex AI training JSONL files if we have successful clips
        jsonl_result = None
        if success_count > 0:
            logger.info(f"🔄 Creating Vertex AI training JSONL files...")
            jsonl_result = self._create_vertex_ai_jsonl_files()
        
        # Final summary
        logger.info(f"🎉 CLIP EXTRACTION COMPLETE")
        logger.info(f"📊 Total plays processed: {len(self.plays)}")
        logger.info(f"📊 Total clips needed: {total_clips_needed}")
        logger.info(f"📊 Successfully extracted: {success_count} clips")
        logger.info(f"📊 Failed: {fail_count} clips")
        if total_clips_needed > 0:
            success_rate = (success_count / total_clips_needed) * 100
            logger.info(f"📊 Success rate: {success_rate:.1f}%")
        
        # Build result
        result = {
            "success": True,
            "game_id": self.game_id,
            "total_plays": len(self.plays),
            "total_clips_needed": total_clips_needed,
            "clips_extracted": success_count,
            "clips_failed": fail_count,
            "success_rate": (success_count / total_clips_needed * 100) if total_clips_needed > 0 else 0,
            "clips_location": f"gs://{self.training_bucket_name}/{self.clips_dir}/"
        }
        
        # Add JSONL creation results
        if jsonl_result:
            if jsonl_result.get("success"):
                result["training_file"] = jsonl_result["training_file"]
                result["validation_file"] = jsonl_result["validation_file"]
                result["training_examples"] = jsonl_result["training_examples"]
                result["validation_examples"] = jsonl_result["validation_examples"]
                logger.info(f"✅ Created training files: {jsonl_result['training_examples']} + {jsonl_result['validation_examples']} examples")
            else:
                result["jsonl_error"] = jsonl_result.get("error")
                logger.warning(f"⚠️ JSONL creation failed: {jsonl_result.get('error')}")
        
        return result