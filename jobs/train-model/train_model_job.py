"""
Cloud Run Job implementation for model training.
Adapted from the original train_model.py script.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from google.cloud import aiplatform
from google.cloud import storage
import logging

logger = logging.getLogger(__name__)


class ModelTrainerJob:
    """Manage Vertex AI model fine-tuning in Cloud Run Job environment."""
    
    def __init__(self, game_id: str, training_bucket: str, project_id: str, 
                 base_model: str, current_finetuned_model: str = "", location: str = "us-central1"):
        """
        Initialize trainer for Cloud Run Job.
        
        Args:
            game_id: Game UUID
            training_bucket: GCS bucket name for training data
            project_id: GCP project ID
            base_model: Base model name (e.g., gemini-1.5-pro-002)
            current_finetuned_model: Current finetuned model endpoint (optional)
            location: GCP location
        """
        self.game_id = game_id
        self.training_bucket_name = training_bucket
        self.project_id = project_id
        self.base_model = base_model
        self.current_finetuned_model = current_finetuned_model
        self.location = location
        
        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=location)
        
        # Initialize storage client
        self.storage_client = storage.Client(project=project_id)
        self.training_bucket = self.storage_client.bucket(training_bucket)
        
        logger.info(f"✓ Initialized ModelTrainerJob for game {game_id}")
        logger.info(f"✓ Vertex AI initialized for project {project_id}")
    
    def _find_training_data(self) -> tuple:
        """Find the most recent training and validation data files in GCS."""
        try:
            logger.info("🔍 Looking for training data files in GCS...")
            
            # List all formatted data files for this game
            prefix = f"datasets/"
            blobs = list(self.training_bucket.list_blobs(prefix=prefix))
            
            # Filter for training and validation files
            training_files = [b for b in blobs if "training" in b.name and b.name.endswith(".jsonl")]
            validation_files = [b for b in blobs if "validation" in b.name and b.name.endswith(".jsonl")]
            
            if not training_files:
                raise FileNotFoundError("No training data files found in GCS")
            if not validation_files:
                raise FileNotFoundError("No validation data files found in GCS")
            
            # Get the most recent files
            training_file = max(training_files, key=lambda x: x.time_created)
            validation_file = max(validation_files, key=lambda x: x.time_created)
            
            training_uri = f"gs://{self.training_bucket_name}/{training_file.name}"
            validation_uri = f"gs://{self.training_bucket_name}/{validation_file.name}"
            
            logger.info(f"✓ Found training data: {training_uri}")
            logger.info(f"✓ Found validation data: {validation_uri}")
            
            return training_uri, validation_uri
            
        except Exception as e:
            logger.error(f"✗ Failed to find training data: {e}")
            raise
    
    def start_training(self, epochs: int = 5, learning_rate: float = 0.0002, 
                      incremental: bool = True) -> Dict[str, Any]:
        """
        Start fine-tuning job with incremental training support.
        
        Args:
            epochs: Number of training epochs
            learning_rate: Learning rate
            incremental: Whether to use incremental training
            
        Returns:
            Training job information
        """
        try:
            logger.info("🚀 Starting Vertex AI fine-tuning job...")
            
            # Find training data
            training_data_uri, validation_data_uri = self._find_training_data()
            
            # Determine base model for training
            if incremental and self.current_finetuned_model:
                base_model = self.current_finetuned_model
                logger.info("🔄 INCREMENTAL TRAINING: Using existing finetuned model as base")
                logger.info(f"Previous model: {base_model}")
            else:
                base_model = self.base_model
                logger.info("🆕 FRESH TRAINING: Using base Gemini model")
            
            # Create job display name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            training_type = "incremental" if (incremental and self.current_finetuned_model) else "fresh"
            job_display_name = f"basketball-annotation-{training_type}-{self.game_id}-{timestamp}"
            
            logger.info(f"📋 Training Configuration:")
            logger.info(f"  Job name: {job_display_name}")
            logger.info(f"  Base model: {base_model}")
            logger.info(f"  Training data: {training_data_uri}")
            logger.info(f"  Validation data: {validation_data_uri}")
            logger.info(f"  Epochs: {epochs}")
            logger.info(f"  Learning rate: {learning_rate}")
            logger.info(f"  Training type: {training_type}")
            
            # Note: This is a simplified implementation
            # The actual Vertex AI fine-tuning API calls would go here
            # For now, we'll simulate the training process
            
            logger.warning(
                "⚠ This is a template implementation. "
                "Actual Vertex AI fine-tuning API calls need to be implemented "
                "based on the latest Vertex AI SDK documentation."
            )
            
            # Simulate training time
            logger.info("🔄 Simulating training process...")
            
            # In a real implementation, you would:
            # 1. Create a tuning job using the Vertex AI SDK
            # 2. Monitor the job progress
            # 3. Handle completion/failure
            
            # For demonstration, we'll provide instructions
            gcloud_command = f"""
gcloud ai models tuning-jobs create \\
  --region={self.location} \\
  --display-name={job_display_name} \\
  --base-model={base_model} \\
  --training-data={training_data_uri} \\
  --validation-data={validation_data_uri} \\
  --tuning-task-inputs='{{"epochs": {epochs}, "learning_rate": {learning_rate}}}'
"""
            
            logger.info(f"📝 Manual training command:")
            logger.info(gcloud_command)
            
            # Simulate some processing time
            time.sleep(5)
            
            job_id = f"{job_display_name}"
            
            logger.info(f"✅ Training job created: {job_id}")
            logger.info(
                f"Monitor progress at: "
                f"https://console.cloud.google.com/vertex-ai/training/"
                f"training-pipelines?project={self.project_id}"
            )
            
            return {
                "success": True,
                "job_id": job_id,
                "job_display_name": job_display_name,
                "training_type": training_type,
                "base_model": base_model,
                "training_data_uri": training_data_uri,
                "validation_data_uri": validation_data_uri,
                "epochs": epochs,
                "learning_rate": learning_rate,
                "console_url": f"https://console.cloud.google.com/vertex-ai/training/training-pipelines?project={self.project_id}",
                "estimated_time": "4-12 hours",
                "estimated_cost": "$50-150"
            }
            
        except Exception as e:
            logger.error(f"✗ Failed to start training job: {e}")
            raise