"""
Cloud Run Job entry point for video clip extraction.

This job:
1. Reads environment variables for configuration
2. Downloads plays data from GCS
3. Extracts video clips using ffmpeg
4. Uploads clips back to GCS
5. Reports progress and completion status
"""

import os
import sys
import json
import logging
from pathlib import Path

# Setup logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Import the clip extraction logic
from extract_clips_job import ClipExtractorJob


def main():
    """Main entry point for the clip extraction job."""
    try:
        logger.info("🚀 Starting extract-clips Cloud Run Job")
        
        # Get configuration from environment
        game_id = os.environ.get("GAME_ID")
        gcs_training_bucket = os.environ.get("GCS_TRAINING_BUCKET")
        skip_if_exists = os.environ.get("SKIP_IF_EXISTS", "true").lower() == "true"
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not game_id:
            raise ValueError("GAME_ID environment variable is required")
        if not gcs_training_bucket:
            raise ValueError("GCS_TRAINING_BUCKET environment variable is required")
        if not supabase_url:
            raise ValueError("SUPABASE_URL environment variable is required")
        if not supabase_key:
            raise ValueError("SUPABASE_SERVICE_KEY environment variable is required")
        
        logger.info(f"📋 Job Configuration:")
        logger.info(f"  Game ID: {game_id}")
        logger.info(f"  Training Bucket: {gcs_training_bucket}")
        logger.info(f"  Skip if exists: {skip_if_exists}")
        logger.info(f"  Supabase URL: {supabase_url}")
        
        # Initialize and run the job
        extractor = ClipExtractorJob(
            game_id=game_id,
            training_bucket=gcs_training_bucket,
            skip_if_exists=skip_if_exists
        )
        
        # Execute the extraction
        result = extractor.extract_all_clips()
        
        logger.info(f"✅ Job completed successfully!")
        logger.info(f"📊 Results: {result}")
        
        # Return success exit code
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Job failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()