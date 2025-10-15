"""
Deploy trained model to persistent Vertex AI endpoint.

This script:
1. Takes a trained model
2. Deploys it to the existing endpoint (or creates one)
3. Updates traffic to route 100% to the new model
4. Keeps the same endpoint URL for the API

Usage:
    python scripts/training/deploy_model.py --model-id <model_id>
"""

import os
import sys
import argparse
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from google.cloud import aiplatform
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
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
PERSISTENT_ENDPOINT_NAME = "basketball-annotation-endpoint"

class ModelDeployer:
    """Deploy models to persistent endpoint."""
    
    def __init__(self):
        """Initialize AI Platform."""
        aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        self.endpoint = None
        logger.info(f"✓ Initialized AI Platform for project {GCP_PROJECT_ID}")
    
    def get_or_create_endpoint(self) -> aiplatform.Endpoint:
        """Get existing endpoint or create new one."""
        try:
            # Try to find existing endpoint
            endpoints = aiplatform.Endpoint.list(
                filter=f'display_name="{PERSISTENT_ENDPOINT_NAME}"'
            )
            
            if endpoints:
                endpoint = endpoints[0]
                logger.info(f"✓ Found existing endpoint: {endpoint.resource_name}")
                return endpoint
            
            # Create new endpoint
            logger.info(f"Creating new endpoint: {PERSISTENT_ENDPOINT_NAME}")
            endpoint = aiplatform.Endpoint.create(
                display_name=PERSISTENT_ENDPOINT_NAME,
                description="Persistent endpoint for basketball annotation models"
            )
            
            logger.info(f"✓ Created new endpoint: {endpoint.resource_name}")
            return endpoint
            
        except Exception as e:
            logger.error(f"✗ Failed to get/create endpoint: {e}")
            raise
    
    def deploy_model(self, model_resource_name: str) -> str:
        """
        Deploy model to the persistent endpoint.
        
        Args:
            model_resource_name: Full model resource name
            
        Returns:
            Endpoint resource name
        """
        try:
            logger.info(f"Deploying model: {model_resource_name}")
            
            # Get or create endpoint
            endpoint = self.get_or_create_endpoint()
            
            # Get the model
            model = aiplatform.Model(model_resource_name)
            
            # Deploy to endpoint
            logger.info("Deploying model to endpoint...")
            deployed_model = model.deploy(
                endpoint=endpoint,
                deployed_model_display_name=f"basketball-model-{int(time.time())}",
                machine_type="n1-standard-2",  # Adjust as needed
                min_replica_count=1,
                max_replica_count=3,
                traffic_percentage=100,  # Route all traffic to new model
                sync=True  # Wait for deployment to complete
            )
            
            logger.info(f"✅ Model deployed successfully!")
            logger.info(f"Endpoint: {endpoint.resource_name}")
            logger.info(f"Deployed model: {deployed_model.resource_name}")
            
            # Clean up old models (keep only latest)
            self._cleanup_old_models(endpoint, deployed_model)
            
            return endpoint.resource_name
            
        except Exception as e:
            logger.error(f"✗ Model deployment failed: {e}")
            raise
    
    def _cleanup_old_models(self, endpoint: aiplatform.Endpoint, new_model):
        """Remove old models from endpoint to save costs."""
        try:
            deployed_models = endpoint.list_models()
            
            for deployed_model in deployed_models:
                if deployed_model.id != new_model.id:
                    logger.info(f"Undeploying old model: {deployed_model.display_name}")
                    endpoint.undeploy(deployed_model_id=deployed_model.id)
            
            logger.info("✓ Cleaned up old models")
            
        except Exception as e:
            logger.warning(f"⚠ Failed to cleanup old models: {e}")
    
    def get_endpoint_url(self) -> str:
        """Get the persistent endpoint URL."""
        endpoint = self.get_or_create_endpoint()
        
        # Format as endpoint resource name for API usage
        endpoint_id = endpoint.resource_name.split('/')[-1]
        endpoint_url = f"projects/{GCP_PROJECT_ID}/locations/{GCP_LOCATION}/endpoints/{endpoint_id}"
        
        logger.info(f"📍 Persistent endpoint URL: {endpoint_url}")
        return endpoint_url

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Deploy model to persistent endpoint")
    parser.add_argument("--model-id", required=True, help="Trained model resource name")
    parser.add_argument("--get-endpoint-only", action="store_true", help="Just get endpoint URL")
    
    args = parser.parse_args()
    
    deployer = ModelDeployer()
    
    if args.get_endpoint_only:
        # Just get the endpoint URL
        endpoint_url = deployer.get_endpoint_url()
        print(f"VERTEX_AI_FINETUNED_ENDPOINT={endpoint_url}")
        return
    
    # Deploy the model
    endpoint_resource_name = deployer.deploy_model(args.model_id)
    
    logger.info("\n" + "="*60)
    logger.info("MODEL DEPLOYMENT COMPLETE")
    logger.info("="*60)
    logger.info(f"Endpoint: {endpoint_resource_name}")
    logger.info("🎯 Your API will automatically use the latest model!")
    logger.info("No need to update .env - the endpoint URL stays the same.")
    logger.info("="*60)

if __name__ == "__main__":
    main()