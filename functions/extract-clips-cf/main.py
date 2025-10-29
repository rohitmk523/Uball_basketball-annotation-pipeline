"""
Cloud Function (2nd Gen) for extracting video clips and creating training data.

This function:
1. Receives a game_id via HTTP POST
2. Queries Supabase for all plays in that game
3. Streams videos from GCS and extracts clips using ffmpeg
4. Uploads clips to training bucket
5. Creates JSONL training files

Trigger: HTTP
Memory: 8GB (configurable)
Timeout: 60 minutes
"""

import os
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import functions_framework
from google.cloud import storage
from supabase import create_client, Client
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClipExtractor:
    """Extract video clips for a single game."""

    def __init__(self, game_id: str):
        """Initialize clip extractor for a specific game."""
        self.game_id = game_id

        # Initialize GCS client
        self.storage_client = storage.Client()
        self.video_bucket_name = os.getenv("GCS_VIDEO_BUCKET", "uball-videos-production")
        self.training_bucket_name = os.getenv("GCS_TRAINING_BUCKET", "uball-training-data")
        self.video_bucket = self.storage_client.bucket(self.video_bucket_name)
        self.training_bucket = self.storage_client.bucket(self.training_bucket_name)

        # Initialize Supabase client
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY required")

        self.supabase: Client = create_client(supabase_url, supabase_key)

        # Paths
        self.game_dir = f"games/{game_id}"
        self.clips_dir = f"{self.game_dir}/clips"

        # Temp directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="clips_"))

        logger.info(f"✓ Initialized ClipExtractor for game {game_id}")
        logger.info(f"✓ Temp dir: {self.temp_dir}")

    def load_plays(self) -> List[Dict[str, Any]]:
        """Load plays from Supabase for this game."""
        logger.info(f"📡 Querying Supabase for plays (game_id={self.game_id})")

        try:
            response = self.supabase.table("plays")\
                .select("*")\
                .eq("game_id", self.game_id)\
                .execute()

            if not response.data:
                logger.warning(f"⚠️ No plays found for game_id: {self.game_id}")
                return []

            plays = response.data
            logger.info(f"✅ Retrieved {len(plays)} plays from Supabase")

            # Save plays to GCS for reference
            self._save_plays_to_gcs(plays)

            return plays

        except Exception as e:
            logger.error(f"❌ Failed to load plays from Supabase: {e}")
            raise

    def _save_plays_to_gcs(self, plays: List[Dict[str, Any]]) -> None:
        """Save plays data to GCS for reference."""
        try:
            plays_json_path = f"{self.game_dir}/plays.json"
            blob = self.training_bucket.blob(plays_json_path)
            blob.upload_from_string(
                json.dumps(plays, indent=2),
                content_type="application/json"
            )
            logger.info(f"✅ Saved plays to gs://{self.training_bucket_name}/{plays_json_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save plays to GCS: {e}")

    def _get_training_angles(self, play_angle: str) -> List[str]:
        """Get camera angles for training based on play angle."""
        angle_mapping = {
            "LEFT": ["FAR_LEFT", "NEAR_RIGHT"],
            "RIGHT": ["FAR_RIGHT", "NEAR_LEFT"]
        }

        if play_angle not in angle_mapping:
            raise ValueError(f"Invalid play angle: {play_angle}")

        return angle_mapping[play_angle]

    def _find_video_in_gcs(self, game_id: str, angle: str) -> Optional[str]:
        """Find video file in GCS bucket using flexible naming patterns."""
        angle_suffix_map = {
            "FAR_LEFT": "farleft",
            "FAR_RIGHT": "farright",
            "NEAR_LEFT": "nearleft",
            "NEAR_RIGHT": "nearright"
        }

        if angle not in angle_suffix_map:
            raise ValueError(f"Unknown angle: {angle}")

        angle_suffix = angle_suffix_map[angle]

        # Try different naming patterns
        naming_patterns = [
            f"game1_{angle_suffix}.mp4",
            f"game2_{angle_suffix}.mp4",
            f"game3_{angle_suffix}.mp4",
            f"test_{angle_suffix}.mp4",
            f"{angle_suffix}.mp4",
            f"{angle}.mp4"
        ]

        base_path = f"Games/{game_id}"

        for pattern in naming_patterns:
            blob_path = f"{base_path}/{pattern}"
            blob = self.video_bucket.blob(blob_path)

            if blob.exists():
                blob.reload()  # Get metadata
                logger.debug(f"✅ Found video: gs://{self.video_bucket_name}/{blob_path} ({blob.size} bytes)")
                return blob_path

        # Not found
        logger.error(f"❌ No video found for {angle} in gs://{self.video_bucket_name}/{base_path}/")
        logger.error(f"Tried patterns: {naming_patterns}")
        return None

    def _extract_clip_streaming(
        self,
        video_gcs_path: str,
        start_timestamp: float,
        end_timestamp: float,
        output_gcs_path: str
    ) -> bool:
        """Extract clip using ffmpeg with GCS streaming (no full download)."""
        duration = end_timestamp - start_timestamp

        if duration <= 0:
            logger.error(f"❌ Invalid duration: {duration}s")
            return False

        # Create temp files
        temp_video = self.temp_dir / f"temp_video_{os.getpid()}.mp4"
        temp_clip = self.temp_dir / f"temp_clip_{os.getpid()}.mp4"

        try:
            # Download video using GCS Python client
            logger.debug(f"⬇️ Downloading gs://{self.video_bucket_name}/{video_gcs_path}")
            blob = self.video_bucket.blob(video_gcs_path)
            blob.download_to_filename(str(temp_video))

            # Extract clip using ffmpeg
            cmd = [
                "ffmpeg",
                "-ss", str(start_timestamp),  # Seek before input (faster)
                "-i", str(temp_video),
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "ultrafast",  # Fast encoding
                "-crf", "23",  # Good quality
                "-c:a", "aac",
                "-y",
                str(temp_clip)
            ]

            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            logger.debug(f"✅ Extracted clip ({duration:.1f}s)")

            # Upload to GCS
            blob = self.training_bucket.blob(output_gcs_path)
            blob.upload_from_filename(str(temp_clip))
            logger.debug(f"✅ Uploaded to gs://{self.training_bucket_name}/{output_gcs_path}")

            return True

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Timeout while processing clip")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Command failed: {e.stderr.decode() if e.stderr else e}")
            return False
        except Exception as e:
            logger.error(f"❌ Clip extraction failed: {e}")
            return False
        finally:
            # Cleanup temp files
            if temp_video.exists():
                temp_video.unlink()
            if temp_clip.exists():
                temp_clip.unlink()

    def _extract_clip_from_local_video(
        self,
        local_video_path: str,
        start_timestamp: float,
        end_timestamp: float,
        output_gcs_path: str
    ) -> bool:
        """Extract clip from an already-downloaded local video file."""
        duration = end_timestamp - start_timestamp

        if duration <= 0:
            logger.error(f"❌ Invalid duration: {duration}s")
            return False

        temp_clip = self.temp_dir / f"clip_{os.getpid()}_{start_timestamp}.mp4"

        try:
            # Extract clip using ffmpeg from LOCAL video
            cmd = [
                "ffmpeg",
                "-ss", str(start_timestamp),
                "-i", local_video_path,  # Already local!
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "aac",
                "-y",
                str(temp_clip)
            ]

            subprocess.run(cmd, check=True, capture_output=True, timeout=60)

            # Upload clip to GCS
            blob = self.training_bucket.blob(output_gcs_path)
            blob.upload_from_filename(str(temp_clip))

            return True

        except subprocess.TimeoutExpired:
            logger.error(f"❌ ffmpeg timeout after 60s")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ ffmpeg failed: {e.stderr.decode() if e.stderr else str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Clip extraction error: {e}")
            return False
        finally:
            if temp_clip.exists():
                temp_clip.unlink()

    def extract_all_clips(self, plays: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract clips for all plays - OPTIMIZED to download each video only ONCE."""
        logger.info(f"🎬 Starting OPTIMIZED clip extraction for {len(plays)} plays")

        success_count = 0
        fail_count = 0
        total_clips_needed = 0

        # Step 1: Find all required videos and validate they exist
        required_videos = {}
        for play in plays:
            training_angles = self._get_training_angles(play["angle"])
            for angle in training_angles:
                if angle not in required_videos:
                    video_path = self._find_video_in_gcs(self.game_id, angle)
                    if not video_path:
                        raise FileNotFoundError(f"Missing video for {angle}")
                    required_videos[angle] = video_path

        logger.info(f"✅ All required videos found: {list(required_videos.keys())}")

        # Step 2: Group clips by source video (KEY OPTIMIZATION!)
        clips_by_video = {}  # {angle: [(play_id, start_ts, end_ts, output_path), ...]}

        for play in plays:
            play_id = play["id"]
            start_ts = play["start_timestamp"]
            end_ts = play["end_timestamp"]

            if start_ts is None or end_ts is None:
                logger.warning(f"⚠️ Play {play_id} missing timestamps, skipping")
                continue

            training_angles = self._get_training_angles(play["angle"])

            for angle in training_angles:
                if angle not in clips_by_video:
                    clips_by_video[angle] = []

                output_gcs_path = f"{self.clips_dir}/{play_id}_{angle}.mp4"
                clips_by_video[angle].append((play_id, start_ts, end_ts, output_gcs_path))
                total_clips_needed += 1

        logger.info(f"📊 Organized {total_clips_needed} clips across {len(clips_by_video)} videos")

        # Step 3: Process each video ONCE and extract ALL clips from it
        for video_idx, (angle, clips) in enumerate(clips_by_video.items(), 1):
            video_gcs_path = required_videos[angle]
            logger.info(f"🎥 [{video_idx}/{len(clips_by_video)}] Processing {angle}: {len(clips)} clips to extract")

            # Download video ONCE
            temp_video = self.temp_dir / f"{angle}_{os.getpid()}.mp4"
            try:
                logger.info(f"⬇️  Downloading gs://{self.video_bucket_name}/{video_gcs_path}")
                blob = self.video_bucket.blob(video_gcs_path)
                blob.download_to_filename(str(temp_video))
                video_size_mb = temp_video.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Downloaded {angle} ({video_size_mb:.1f} MB)")

                # Extract ALL clips from this video
                for clip_idx, (play_id, start_ts, end_ts, output_gcs_path) in enumerate(clips, 1):
                    success = self._extract_clip_from_local_video(
                        str(temp_video),
                        start_ts,
                        end_ts,
                        output_gcs_path
                    )

                    if success:
                        success_count += 1
                    else:
                        fail_count += 1

                    # Log progress every 20 clips
                    if clip_idx % 20 == 0:
                        logger.info(f"  📊 {clip_idx}/{len(clips)} clips from {angle} | ✅ {success_count} total")

                logger.info(f"✅ Completed {angle}: {len(clips)} clips extracted")

            except Exception as e:
                logger.error(f"❌ Failed to process {angle}: {e}")
                fail_count += len(clips)
            finally:
                # Delete temp video
                if temp_video.exists():
                    temp_video.unlink()
                    logger.info(f"🗑️  Deleted temp video: {angle}")

        logger.info(f"🎉 OPTIMIZED extraction complete: ✅ {success_count} ❌ {fail_count} / {total_clips_needed}")

        return {
            "total_clips_needed": total_clips_needed,
            "success_count": success_count,
            "fail_count": fail_count,
            "success_rate": (success_count / total_clips_needed * 100) if total_clips_needed > 0 else 0
        }

    def create_jsonl_files(self, plays: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create Vertex AI training JSONL files."""
        logger.info("📝 Creating JSONL training files")

        try:
            import datetime

            # Split plays into training (80%) and validation (20%)
            random.seed(42)
            shuffled_plays = plays.copy()
            random.shuffle(shuffled_plays)

            split_idx = int(len(shuffled_plays) * 0.8)
            training_plays = shuffled_plays[:split_idx]
            validation_plays = shuffled_plays[split_idx:]

            logger.info(f"📊 Split: {len(training_plays)} training, {len(validation_plays)} validation")

            # Create examples
            training_examples = self._create_jsonl_examples(training_plays)
            validation_examples = self._create_jsonl_examples(validation_plays)

            # Upload to GCS
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            training_file = f"video_training_{self.game_id}_{timestamp}.jsonl"
            validation_file = f"video_validation_{self.game_id}_{timestamp}.jsonl"

            training_path = f"{self.game_dir}/{training_file}"
            validation_path = f"{self.game_dir}/{validation_file}"

            self._upload_jsonl(training_examples, training_path)
            self._upload_jsonl(validation_examples, validation_path)

            logger.info(f"✅ Created JSONL files: {len(training_examples)} + {len(validation_examples)} examples")

            return {
                "success": True,
                "training_file": f"gs://{self.training_bucket_name}/{training_path}",
                "validation_file": f"gs://{self.training_bucket_name}/{validation_path}",
                "training_examples": len(training_examples),
                "validation_examples": len(validation_examples)
            }

        except Exception as e:
            logger.error(f"❌ Failed to create JSONL files: {e}")
            return {"success": False, "error": str(e)}

    def _create_jsonl_examples(self, plays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create JSONL examples for given plays."""
        examples = []

        for play in plays:
            try:
                play_examples = self._create_single_play_examples(play)
                examples.extend(play_examples)
            except Exception as e:
                logger.warning(f"⚠️ Failed to create example for play {play.get('id')}: {e}")

        return examples

    def _create_single_play_examples(self, play: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create JSONL examples for a single play (one per camera angle)."""
        play_id = play["id"]
        play_angle = play["angle"]
        training_angles = self._get_training_angles(play_angle)

        examples = []

        for angle in training_angles:
            clip_uri = f"gs://{self.training_bucket_name}/{self.clips_dir}/{play_id}_{angle}.mp4"

            # Create prompt
            angle_context = "wide court view and team formation context" if "FAR" in angle else "close-up details of player numbers and jerseys"

            prompt_text = f"""Analyze this basketball game video from {angle} camera angle and identify the play with its events.

This is a {angle} camera view that provides {angle_context}.

For the play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FREE_THROW_MAKE, FREE_THROW_MISS, REBOUND, ASSIST, STEAL, BLOCK, TURNOVER, FOUL, TIMEOUT, SUB)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type (same options as classification)
   - playerA: Player identifier (format: "Player #X (Color Team)")
   - playerB: Secondary player if applicable

Return a JSON array with the single play. Be precise with timestamps and identify all basketball events."""

            # Build expected output from play data
            expected_response = {
                "timestamp_seconds": play.get("timestamp_seconds"),
                "classification": play.get("classification"),
                "note": play.get("note"),
                "player_a": play.get("player_a"),
                "player_b": play.get("player_b"),
                "events": play.get("events", [])
            }

            # Create Vertex AI format example
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
                                "text": json.dumps([expected_response])
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

    def _upload_jsonl(self, examples: List[Dict[str, Any]], gcs_path: str):
        """Upload JSONL examples to GCS."""
        temp_file = self.temp_dir / "temp.jsonl"

        with open(temp_file, 'w') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')

        blob = self.training_bucket.blob(gcs_path)
        blob.upload_from_filename(str(temp_file))

        temp_file.unlink()

    def cleanup(self):
        """Cleanup temporary directory."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"🗑️ Cleaned up temp dir: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup temp dir: {e}")


@functions_framework.http
def extract_clips_game(request):
    """
    Cloud Function entry point.

    Expected request body:
    {
        "game_id": "uuid-string"
    }

    Returns:
    {
        "success": true,
        "game_id": "uuid",
        "clips_extracted": 150,
        "clips_failed": 5,
        "training_file": "gs://...",
        "validation_file": "gs://..."
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json or 'game_id' not in request_json:
            return {
                "success": False,
                "error": "Missing 'game_id' in request body"
            }, 400

        game_id = request_json['game_id']

        logger.info(f"🚀 Starting clip extraction for game: {game_id}")

        # Initialize extractor
        extractor = ClipExtractor(game_id)

        # Load plays from Supabase
        plays = extractor.load_plays()

        if not plays:
            return {
                "success": False,
                "error": f"No plays found for game_id: {game_id}"
            }, 404

        # Extract clips
        clip_results = extractor.extract_all_clips(plays)

        # Create JSONL files
        jsonl_results = extractor.create_jsonl_files(plays)

        # Cleanup
        extractor.cleanup()

        # Build response
        response = {
            "success": True,
            "game_id": game_id,
            "total_plays": len(plays),
            "clips_extracted": clip_results["success_count"],
            "clips_failed": clip_results["fail_count"],
            "clips_needed": clip_results["total_clips_needed"],
            "success_rate": clip_results["success_rate"]
        }

        if jsonl_results.get("success"):
            response["training_file"] = jsonl_results["training_file"]
            response["validation_file"] = jsonl_results["validation_file"]
            response["training_examples"] = jsonl_results["training_examples"]
            response["validation_examples"] = jsonl_results["validation_examples"]
        else:
            response["jsonl_error"] = jsonl_results.get("error")

        logger.info(f"✅ Completed extraction for game {game_id}")

        return response, 200

    except Exception as e:
        logger.error(f"❌ Function failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }, 500
