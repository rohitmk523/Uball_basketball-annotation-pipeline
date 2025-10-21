#!/usr/bin/env python3
"""
Setup script for continuous training with persistent endpoint.

This script:
1. Creates the persistent endpoint if it doesn't exist
2. Gets the endpoint URL and updates environment configuration
3. Initializes the games count metadata
4. Provides setup instructions

Usage:
    python scripts/setup/setup_continuous_training.py
"""

import os
import sys
import json
from pathlib import Path
from google.cloud import aiplatform
from google.cloud import storage
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
PERSISTENT_ENDPOINT_NAME = "basketball-annotation-endpoint"
TRAINING_BUCKET = "uball-training-data"

class ContinuousTrainingSetup:
    """Setup continuous training infrastructure."""
    
    def __init__(self):
        """Initialize clients."""
        if not GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID environment variable not set")
        
        aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        self.storage_client = storage.Client(project=GCP_PROJECT_ID)
        logger.info(f"✓ Initialized for project {GCP_PROJECT_ID}")
    
    def create_persistent_endpoint(self) -> str:
        """Create or get persistent endpoint."""
        try:
            # Check if endpoint already exists
            endpoints = aiplatform.Endpoint.list(
                filter=f'display_name="{PERSISTENT_ENDPOINT_NAME}"'
            )
            
            if endpoints:
                endpoint = endpoints[0]
                logger.info(f"✓ Found existing persistent endpoint: {endpoint.resource_name}")
                return endpoint.resource_name
            
            # Create new endpoint
            logger.info(f"Creating persistent endpoint: {PERSISTENT_ENDPOINT_NAME}")
            endpoint = aiplatform.Endpoint.create(
                display_name=PERSISTENT_ENDPOINT_NAME,
                description="Persistent endpoint for basketball annotation models with continuous training"
            )
            
            logger.info(f"✅ Created persistent endpoint: {endpoint.resource_name}")
            return endpoint.resource_name
            
        except Exception as e:
            logger.error(f"✗ Failed to create/get endpoint: {e}")
            raise
    
    def get_endpoint_url(self, endpoint_resource_name: str) -> str:
        """Format endpoint URL for API usage."""
        endpoint_id = endpoint_resource_name.split('/')[-1]
        endpoint_url = f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}/endpoints/{endpoint_id}"
        return endpoint_url
    
    def initialize_games_metadata(self):
        """Initialize games count metadata in GCS."""
        try:
            bucket = self.storage_client.bucket(TRAINING_BUCKET)
            
            # Check if metadata already exists
            metadata_blob = bucket.blob("metadata/games_count.json")
            
            if metadata_blob.exists():
                existing_data = json.loads(metadata_blob.download_as_text())
                logger.info(f"✓ Found existing metadata: {existing_data['total']} games trained")
                return existing_data
            
            # Create initial metadata
            initial_metadata = {
                "total": 0,
                "games": [],
                "last_updated": None,
                "created_at": str(int(os.path.getmtime(__file__)))
            }
            
            metadata_blob.upload_from_string(
                json.dumps(initial_metadata, indent=2),
                content_type="application/json"
            )
            
            logger.info("✅ Initialized games count metadata")
            return initial_metadata
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize metadata: {e}")
            raise
    
    def update_environment_config(self, endpoint_url: str):
        """Update environment configuration with persistent endpoint."""
        try:
            env_file = project_root / ".env"
            
            if not env_file.exists():
                logger.warning("⚠️ .env file not found, creating new one")
                env_content = ""
            else:
                env_content = env_file.read_text()
            
            # Update or add VERTEX_AI_FINETUNED_ENDPOINT
            lines = env_content.split('\n')
            updated_lines = []
            endpoint_updated = False
            
            for line in lines:
                if line.startswith('VERTEX_AI_FINETUNED_ENDPOINT='):
                    updated_lines.append(f'VERTEX_AI_FINETUNED_ENDPOINT={endpoint_url}')
                    endpoint_updated = True
                    logger.info("✓ Updated existing VERTEX_AI_FINETUNED_ENDPOINT")
                else:
                    updated_lines.append(line)
            
            if not endpoint_updated:
                updated_lines.append(f'VERTEX_AI_FINETUNED_ENDPOINT={endpoint_url}')
                logger.info("✓ Added VERTEX_AI_FINETUNED_ENDPOINT to .env")
            
            # Write back to .env
            env_file.write_text('\n'.join(updated_lines))
            
        except Exception as e:
            logger.error(f"✗ Failed to update environment config: {e}")
            raise
    
    def setup_continuous_training(self):
        """Complete setup for continuous training."""
        logger.info("🚀 Setting up continuous training infrastructure...")
        
        # 1. Create persistent endpoint
        endpoint_resource_name = self.create_persistent_endpoint()
        endpoint_url = self.get_endpoint_url(endpoint_resource_name)
        
        # 2. Initialize games metadata
        metadata = self.initialize_games_metadata()
        
        # 3. Update environment configuration
        self.update_environment_config(endpoint_url)
        
        # 4. Print setup summary
        self.print_setup_summary(endpoint_resource_name, endpoint_url, metadata)
    
    def print_setup_summary(self, endpoint_resource_name: str, endpoint_url: str, metadata: dict):
        """Print setup summary and instructions."""
        print("\n" + "="*80)
        print("🎉 CONTINUOUS TRAINING SETUP COMPLETE")
        print("="*80)
        print(f"📍 Persistent Endpoint: {PERSISTENT_ENDPOINT_NAME}")
        print(f"🔗 Endpoint URL: {endpoint_url}")
        print(f"📊 Games Trained: {metadata['total']}")
        print()
        print("🎯 HOW IT WORKS:")
        print("  • Each training run automatically deploys to the same endpoint")
        print("  • API always uses the latest model without URL changes")
        print("  • Models are versioned by game count (v2@5games, v3@10games...)")
        print("  • Incremental training builds on previous models")
        print()
        print("🚀 NEXT STEPS:")
        print("  1. Run training: gcloud workflows run hybrid-training-pipeline --data='{\"game_id\": \"your-game-id\"}'")
        print("  2. Your API will automatically use the latest model!")
        print("  3. Keep training more games to improve the model")
        print()
        print("💡 BENEFITS:")
        print("  ✅ Single endpoint URL - never changes")
        print("  ✅ Automatic deployment after training")
        print("  ✅ Progressive model improvement")
        print("  ✅ Version tracking by game count")
        print("="*80)

def main():
    """Main setup function."""
    try:
        setup = ContinuousTrainingSetup()
        setup.setup_continuous_training()
        
    except Exception as e:
        logger.error(f"✗ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()