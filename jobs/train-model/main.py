"""
Cloud Run Job entry point for model training.

This job:
1. Reads environment variables for configuration
2. Finds training and validation data in GCS
3. Submits Vertex AI fine-tuning job
4. Monitors training progress
5. Reports completion status
"""

import os
import sys
import logging

# Setup logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Import the training logic
from train_model_job import ModelTrainerJob


def main():
    """Main entry point for the model training job."""
    try:
        logger.info("🚀 Starting train-model Cloud Run Job")
        
        # Get configuration from environment
        game_id = os.environ.get("GAME_ID")
        gcs_training_bucket = os.environ.get("GCS_TRAINING_BUCKET")
        gcp_project_id = os.environ.get("GCP_PROJECT_ID")
        base_model = os.environ.get("VERTEX_AI_BASE_MODEL", "gemini-1.5-pro-002")
        current_model = os.environ.get("VERTEX_AI_FINETUNED_ENDPOINT", "")
        
        if not game_id:
            raise ValueError("GAME_ID environment variable is required")
        if not gcs_training_bucket:
            raise ValueError("GCS_TRAINING_BUCKET environment variable is required")
        if not gcp_project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        logger.info(f"📋 Job Configuration:")
        logger.info(f"  Game ID: {game_id}")
        logger.info(f"  Training Bucket: {gcs_training_bucket}")
        logger.info(f"  Project ID: {gcp_project_id}")
        logger.info(f"  Base Model: {base_model}")
        logger.info(f"  Current Model: {current_model or 'None'}")
        
        # Initialize and run the job
        trainer = ModelTrainerJob(
            game_id=game_id,
            training_bucket=gcs_training_bucket,
            project_id=gcp_project_id,
            base_model=base_model,
            current_finetuned_model=current_model
        )
        
        # Execute the training
        result = trainer.start_training()
        
        logger.info(f"✅ Job completed successfully!")
        logger.info(f"📊 Results: {result}")
        
        # Return success exit code
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Job failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()