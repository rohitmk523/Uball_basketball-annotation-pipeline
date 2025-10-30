#!/usr/bin/env python3
"""
Cloud Run Job entry point for clip extraction.

This is the main entry point for the Cloud Run Job that extracts video clips
and creates training data for basketball game analysis.

Environment Variables Required:
- GAME_ID: The game UUID to process
- SUPABASE_URL: Supabase project URL
- SUPABASE_SERVICE_KEY: Supabase service role key (from Secret Manager)
- GCS_VIDEO_BUCKET: GCS bucket containing source videos
- GCS_TRAINING_BUCKET: GCS bucket for training data output
"""

import os
import sys
import logging
from extract_clips_job import ClipExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for Cloud Run Job."""
    try:
        # Get game_id from environment variable
        game_id = os.environ.get("GAME_ID")
        if not game_id:
            logger.error("GAME_ID environment variable not set")
            sys.exit(1)

        logger.info(f"Starting clip extraction job for game: {game_id}")

        # Initialize processor
        processor = ClipExtractor(game_id=game_id)

        # Load plays from Supabase
        plays = processor.load_plays()

        if not plays:
            logger.error(f"No plays found for game_id: {game_id}")
            sys.exit(1)

        logger.info(f"Loaded {len(plays)} plays from Supabase")

        # Check if clips already exist (skip logic)
        existing_check = processor.check_existing_clips(plays)
        
        if existing_check["all_exist"]:
            logger.info("🎯 All clips already exist! Skipping extraction, creating JSONL files only.")
            clip_results = {
                "success_count": existing_check["existing_count"],
                "fail_count": 0,
                "total_clips_needed": existing_check["expected_count"],
                "success_rate": 100.0,
                "skipped": True
            }
        else:
            # Extract clips (only if some are missing)
            logger.info(f"🔨 Extracting {len(existing_check['missing_clips'])} missing clips...")
            clip_results = processor.extract_all_clips(plays)
            clip_results["skipped"] = False

        # Create JSONL files
        jsonl_results = processor.create_jsonl_files(plays)

        # Cleanup
        processor.cleanup()

        # Log final results
        logger.info("=" * 70)
        logger.info("Job completed successfully!")
        logger.info(f"Game ID: {game_id}")
        logger.info(f"Total Plays: {len(plays)}")
        
        if clip_results.get("skipped"):
            logger.info(f"✅ Clips: {clip_results['success_count']} (ALL EXISTED - SKIPPED EXTRACTION)")
        else:
            logger.info(f"Clips Extracted: {clip_results['success_count']}")
            logger.info(f"Clips Failed: {clip_results['fail_count']}")
            logger.info(f"Success Rate: {clip_results['success_rate']:.1f}%")

        if jsonl_results.get("success"):
            logger.info(f"Training Examples: {jsonl_results['training_examples']}")
            logger.info(f"Validation Examples: {jsonl_results['validation_examples']}")
            logger.info(f"Training File: {jsonl_results['training_file']}")
            logger.info(f"Validation File: {jsonl_results['validation_file']}")
        else:
            logger.warning(f"JSONL creation failed: {jsonl_results.get('error')}")

        logger.info("=" * 70)

        # Return success
        sys.exit(0)

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
