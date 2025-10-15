"""
Format training data as Vertex AI JSONL format.

This script:
1. Loads exported plays
2. Creates training examples in Vertex AI format
3. Outputs JSONL files for training and validation

Usage:
    python scripts/training/format_training_data.py <plays_json_file>
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration
GCS_TRAINING_BUCKET = os.getenv("GCS_TRAINING_BUCKET")
OUTPUT_DIR = project_root / "output" / "training_data"


class TrainingDataFormatter:
    """Format plays into Vertex AI training format."""
    
    def __init__(self, training_plays_file: str, validation_plays_file: str):
        """
        Initialize formatter.
        
        Args:
            training_plays_file: Path to training plays JSON
            validation_plays_file: Path to validation plays JSON
        """
        self.training_plays = self._load_json(training_plays_file)
        self.validation_plays = self._load_json(validation_plays_file)
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Loaded {len(self.training_plays)} training plays")
        logger.info(f"Loaded {len(self.validation_plays)} validation plays")
    
    def _load_json(self, filepath: str) -> List[Dict[str, Any]]:
        """Load JSON file."""
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def _build_prompt(self) -> str:
        """Build the instruction prompt for the model."""
        return """Analyze these basketball game videos from multiple camera angles and identify all plays with their events.

You are provided with multiple camera angles of the same play to give you better context:
- Far camera angles provide wide court view and team formation context
- Near camera angles provide close-up details of player numbers and jerseys

For each play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FOUL, REBOUND, ASSIST, etc.)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type (same options as classification)
   - playerA: Player identifier (format: "Player #X (Color Team)")
   - playerB: Secondary player if applicable

Use information from all provided camera angles to accurately identify player numbers and team colors. Return a JSON array of plays. Be precise with timestamps and identify all basketball events."""
    
    def _get_training_angles(self, play_angle: str) -> List[str]:
        """
        Get the camera angles used for training based on the play's detected angle.
        Must match the extract_clips.py logic.
        """
        angle_mapping = {
            "LEFT": ["FAR_LEFT", "NEAR_RIGHT"],
            "RIGHT": ["FAR_RIGHT", "NEAR_LEFT"]
        }
        return angle_mapping.get(play_angle, [play_angle])

    def _create_training_example(self, play: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a single training example in Vertex AI format with multi-angle clips.
        
        Args:
            play: Play data
            
        Returns:
            Training example dict
        """
        game_id = play["game_id"]
        play_id = play["id"]
        play_angle = play["angle"]
        
        # Get the training angles for this play
        training_angles = self._get_training_angles(play_angle)
        
        # Build video content list for all angles
        video_content = []
        for angle in training_angles:
            clip_uri = f"gs://{GCS_TRAINING_BUCKET}/clips/{game_id}/{play_id}/{angle}.mp4"
            video_content.append({
                "type": "video",
                "video_uri": clip_uri
            })
        
        # Build expected output (assistant response)
        assistant_content = {
            "timestamp_seconds": play["timestamp_seconds"],
            "classification": play["classification"],
            "note": play["note"],
            "player_a": play.get("player_a"),
            "player_b": play.get("player_b"),
            "events": play.get("events", [])
        }
        
        # Create user content with multiple videos + prompt
        user_content = video_content + [
            {
                "type": "text", 
                "text": self._build_prompt()
            }
        ]
        
        # Create training example in Vertex AI format
        example = {
            "messages": [
                {
                    "role": "user",
                    "content": user_content
                },
                {
                    "role": "assistant",
                    "content": json.dumps([assistant_content])  # Array with single play
                }
            ]
        }
        
        return example
    
    def format_dataset(self) -> tuple:
        """
        Format both training and validation datasets.
        
        Returns:
            Tuple of (training_examples, validation_examples)
        """
        logger.info("Formatting training dataset...")
        training_examples = []
        for play in self.training_plays:
            try:
                example = self._create_training_example(play)
                training_examples.append(example)
            except Exception as e:
                logger.warning(f"Failed to format play {play.get('id')}: {e}")
                continue
        
        logger.info("Formatting validation dataset...")
        validation_examples = []
        for play in self.validation_plays:
            try:
                example = self._create_training_example(play)
                validation_examples.append(example)
            except Exception as e:
                logger.warning(f"Failed to format play {play.get('id')}: {e}")
                continue
        
        logger.info(f"✓ Formatted {len(training_examples)} training examples")
        logger.info(f"✓ Formatted {len(validation_examples)} validation examples")
        
        return training_examples, validation_examples
    
    def save_jsonl(self, examples: List[Dict], filename: str):
        """
        Save examples as JSONL file.
        
        Args:
            examples: List of training examples
            filename: Output filename
        """
        output_path = OUTPUT_DIR / filename
        
        with open(output_path, 'w') as f:
            for example in examples:
                f.write(json.dumps(example) + '\n')
        
        logger.info(f"✓ Saved {len(examples)} examples to {output_path}")
    
    def format_and_save(self):
        """Main process: format and save datasets."""
        training_examples, validation_examples = self.format_dataset()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.save_jsonl(training_examples, f"training_data_{timestamp}.jsonl")
        self.save_jsonl(validation_examples, f"validation_data_{timestamp}.jsonl")
        
        logger.info(f"\n{'='*60}")
        logger.info("TRAINING DATA FORMATTING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Training examples: {len(training_examples)}")
        logger.info(f"Validation examples: {len(validation_examples)}")
        logger.info(f"Output directory: {OUTPUT_DIR}")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        logger.error("Usage: python format_training_data.py <training_plays.json> <validation_plays.json>")
        sys.exit(1)
    
    training_file = sys.argv[1]
    validation_file = sys.argv[2]
    
    formatter = TrainingDataFormatter(training_file, validation_file)
    formatter.format_and_save()

