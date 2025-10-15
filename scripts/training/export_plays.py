"""
Export all annotated plays from Supabase for training data preparation.

This script:
1. Connects to Supabase
2. Queries all plays with complete annotations
3. Exports to structured JSON format
4. Creates training/validation split

Usage:
    python scripts/training/export_plays.py
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from supabase import create_client, Client
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
OUTPUT_DIR = project_root / "output" / "training_data"
TRAINING_SPLIT = 0.8  # 80% training, 20% validation


class PlaysExporter:
    """Export plays from Supabase for training."""
    
    def __init__(self, game_id: str = None):
        """Initialize Supabase client."""
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("Missing Supabase credentials in environment variables")
        
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self.game_id = game_id
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized PlaysExporter. Output directory: {self.output_dir}")
        if game_id:
            logger.info(f"Filtering for game_id: {game_id}")
    
    def fetch_all_plays(self) -> List[Dict[str, Any]]:
        """
        Fetch plays with complete annotations from Supabase.
        Optionally filter by game_id if provided.
        
        Returns:
            List of play dictionaries
        """
        logger.info("Fetching plays from Supabase...")
        
        try:
            query = (
                self.client.table("plays")
                .select("*")
                .not_.is_("classification", "null")
                .not_.is_("events", "null")
                .not_.is_("start_timestamp", "null")
                .not_.is_("end_timestamp", "null")
            )
            
            # Filter by game_id if provided
            if self.game_id:
                query = query.eq("game_id", self.game_id)
            
            response = query.execute()
            
            plays = response.data
            logger.info(f"✓ Fetched {len(plays)} plays from Supabase")
            
            # Filter out plays with empty events array or invalid timestamps
            filtered_plays = []
            for play in plays:
                if (play.get("events") and len(play["events"]) > 0 and 
                    play.get("start_timestamp") is not None and 
                    play.get("end_timestamp") is not None and
                    play.get("start_timestamp") < play.get("end_timestamp")):
                    filtered_plays.append(play)
            
            logger.info(f"✓ Filtered to {len(filtered_plays)} plays with valid data")
            
            if self.game_id:
                logger.info(f"✓ All plays are for game: {self.game_id}")
            
            return filtered_plays
            
        except Exception as e:
            logger.error(f"✗ Error fetching plays: {e}")
            raise
    
    def create_train_val_split(self, plays: List[Dict[str, Any]]) -> tuple:
        """Split plays into training and validation sets."""
        import random
        random.seed(42)
        shuffled_plays = plays.copy()
        random.shuffle(shuffled_plays)
        
        split_index = int(len(shuffled_plays) * TRAINING_SPLIT)
        training_plays = shuffled_plays[:split_index]
        validation_plays = shuffled_plays[split_index:]
        
        logger.info(f"✓ Split created: {len(training_plays)} training, {len(validation_plays)} validation")
        
        return training_plays, validation_plays
    
    def save_export(self, plays, training_plays, validation_plays):
        """Save exported data to JSON files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save all plays
        all_plays_file = self.output_dir / f"all_plays_{timestamp}.json"
        with open(all_plays_file, 'w') as f:
            json.dump(plays, f, indent=2, default=str)
        logger.info(f"✓ Saved all plays to: {all_plays_file}")
        
        # Save training set
        training_file = self.output_dir / f"training_plays_{timestamp}.json"
        with open(training_file, 'w') as f:
            json.dump(training_plays, f, indent=2, default=str)
        logger.info(f"✓ Saved training plays to: {training_file}")
        
        # Save validation set
        validation_file = self.output_dir / f"validation_plays_{timestamp}.json"
        with open(validation_file, 'w') as f:
            json.dump(validation_plays, f, indent=2, default=str)
        logger.info(f"✓ Saved validation plays to: {validation_file}")
    
    def export(self):
        """Main export process."""
        try:
            plays = self.fetch_all_plays()
            if not plays:
                logger.warning("⚠ No plays found. Exiting.")
                return
            
            training_plays, validation_plays = self.create_train_val_split(plays)
            self.save_export(plays, training_plays, validation_plays)
            
            logger.info("✅ Export process completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Export process failed: {e}")
            raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Export plays for training")
    parser.add_argument("--game-id", help="Filter by specific game ID")
    args = parser.parse_args()
    
    exporter = PlaysExporter(game_id=args.game_id)
    exporter.export()

