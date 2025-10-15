#!/usr/bin/env python3
"""
Local Training Pipeline Runner
Runs the basketball annotation training pipeline locally without FastAPI or Cloud Build.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent

def run_command(cmd, description):
    """Run a command and handle errors."""
    logger.info(f"🚀 {description}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
        logger.info(f"✅ {description} completed successfully")
        if result.stdout:
            logger.info(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} failed")
        logger.error(f"Error: {e.stderr}")
        return False

def main():
    """Run the complete training pipeline."""
    parser = argparse.ArgumentParser(description="Run basketball annotation training pipeline locally")
    parser.add_argument("game_id", help="Game ID to process")
    parser.add_argument("--skip-export", action="store_true", help="Skip play export step")
    parser.add_argument("--skip-clips", action="store_true", help="Skip clip extraction step")
    parser.add_argument("--skip-format", action="store_true", help="Skip data formatting step")
    parser.add_argument("--skip-training", action="store_true", help="Skip model training step")
    
    args = parser.parse_args()
    game_id = args.game_id
    
    logger.info("="*60)
    logger.info(f"🏀 BASKETBALL ANNOTATION TRAINING PIPELINE")
    logger.info("="*60)
    logger.info(f"Game ID: {game_id}")
    logger.info(f"Project Root: {PROJECT_ROOT}")
    logger.info("="*60)
    
    # Step 1: Export plays
    if not args.skip_export:
        success = run_command([
            "python", "scripts/training/export_plays.py", "--game-id", game_id
        ], "Export plays from database")
        
        if not success:
            logger.error("❌ Pipeline failed at export step")
            return 1
    else:
        logger.info("⏭️ Skipping play export")
    
    # Step 2: Extract clips
    if not args.skip_clips:
        plays_file = f"output/training_data/plays_{game_id}.json"
        if not Path(plays_file).exists():
            logger.error(f"❌ Plays file not found: {plays_file}")
            return 1
            
        success = run_command([
            "python", "scripts/training/extract_clips.py", plays_file
        ], "Extract video clips")
        
        if not success:
            logger.error("❌ Pipeline failed at clip extraction step")
            return 1
    else:
        logger.info("⏭️ Skipping clip extraction")
    
    # Step 3: Format training data
    if not args.skip_format:
        success = run_command([
            "python", "scripts/training/format_training_data.py", game_id
        ], "Format training data")
        
        if not success:
            logger.error("❌ Pipeline failed at data formatting step")
            return 1
    else:
        logger.info("⏭️ Skipping data formatting")
    
    # Step 4: Train model
    if not args.skip_training:
        training_file = f"output/training_data/training_{game_id}.jsonl"
        validation_file = f"output/training_data/validation_{game_id}.jsonl"
        
        # Check if files exist
        if not Path(training_file).exists():
            logger.error(f"❌ Training file not found: {training_file}")
            return 1
        if not Path(validation_file).exists():
            logger.error(f"❌ Validation file not found: {validation_file}")
            return 1
            
        success = run_command([
            "python", "scripts/training/train_model.py",
            "--training-data", training_file,
            "--validation-data", validation_file
        ], "Train model using Vertex AI")
        
        if not success:
            logger.error("❌ Pipeline failed at model training step")
            return 1
    else:
        logger.info("⏭️ Skipping model training")
    
    logger.info("="*60)
    logger.info("🎉 TRAINING PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("="*60)
    logger.info(f"Game ID: {game_id}")
    logger.info("All steps completed successfully")
    logger.info("="*60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())