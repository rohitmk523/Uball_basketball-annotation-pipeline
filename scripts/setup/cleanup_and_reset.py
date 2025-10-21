#!/usr/bin/env python3
"""
Cleanup script to delete all deployed models and endpoints, and reset for fresh start.

This script:
1. Lists all endpoints and models
2. Allows selective or complete cleanup
3. Resets the games count metadata
4. Provides options for fresh start

Usage:
    python scripts/setup/cleanup_and_reset.py [--confirm] [--keep-models] [--dry-run]
"""

import os
import sys
import json
import argparse
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
TRAINING_BUCKET = "uball-training-data"

class CleanupManager:
    """Manage cleanup of Vertex AI resources."""
    
    def __init__(self, dry_run=False):
        """Initialize cleanup manager."""
        if not GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID environment variable not set")
        
        aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        self.storage_client = storage.Client(project=GCP_PROJECT_ID)
        self.dry_run = dry_run
        logger.info(f"✓ Initialized cleanup for project {GCP_PROJECT_ID}")
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No actual deletions will occur")
    
    def list_endpoints(self):
        """List all endpoints."""
        try:
            endpoints = aiplatform.Endpoint.list()
            logger.info(f"📍 Found {len(endpoints)} endpoints:")
            
            for i, endpoint in enumerate(endpoints, 1):
                logger.info(f"  {i}. {endpoint.display_name}")
                logger.info(f"     ID: {endpoint.resource_name}")
                logger.info(f"     Created: {endpoint.create_time}")
                
                # Check deployed models
                try:
                    deployed_models = endpoint.list_models()
                    if deployed_models:
                        logger.info(f"     Deployed models: {len(deployed_models)}")
                        for model in deployed_models:
                            logger.info(f"       - {model.display_name}")
                    else:
                        logger.info(f"     Deployed models: None")
                except Exception as e:
                    logger.warning(f"     Could not list deployed models: {e}")
                logger.info("")
            
            return endpoints
            
        except Exception as e:
            logger.error(f"✗ Failed to list endpoints: {e}")
            return []
    
    def list_models(self):
        """List all custom models."""
        try:
            models = aiplatform.Model.list(filter='display_name:"basketball"')
            logger.info(f"🤖 Found {len(models)} basketball models:")
            
            for i, model in enumerate(models, 1):
                logger.info(f"  {i}. {model.display_name}")
                logger.info(f"     ID: {model.resource_name}")
                logger.info(f"     Created: {model.create_time}")
                logger.info("")
            
            return models
            
        except Exception as e:
            logger.error(f"✗ Failed to list models: {e}")
            return []
    
    def delete_endpoint(self, endpoint, force=False):
        """Delete a specific endpoint."""
        try:
            if self.dry_run:
                logger.info(f"🔍 [DRY RUN] Would delete endpoint: {endpoint.display_name}")
                return True
            
            if not force:
                confirm = input(f"Delete endpoint '{endpoint.display_name}'? (y/N): ")
                if confirm.lower() != 'y':
                    logger.info("⏭️  Skipped")
                    return False
            
            logger.info(f"🗑️  Deleting endpoint: {endpoint.display_name}")
            endpoint.delete(force=True)  # Force delete even with deployed models
            logger.info("✅ Endpoint deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to delete endpoint: {e}")
            return False
    
    def delete_model(self, model, force=False):
        """Delete a specific model."""
        try:
            if self.dry_run:
                logger.info(f"🔍 [DRY RUN] Would delete model: {model.display_name}")
                return True
            
            if not force:
                confirm = input(f"Delete model '{model.display_name}'? (y/N): ")
                if confirm.lower() != 'y':
                    logger.info("⏭️  Skipped")
                    return False
            
            logger.info(f"🗑️  Deleting model: {model.display_name}")
            model.delete()
            logger.info("✅ Model deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to delete model: {e}")
            return False
    
    def reset_games_metadata(self, force=False):
        """Reset the games count metadata."""
        try:
            if self.dry_run:
                logger.info("🔍 [DRY RUN] Would reset games metadata")
                return True
            
            if not force:
                confirm = input("Reset games count metadata to 0? (y/N): ")
                if confirm.lower() != 'y':
                    logger.info("⏭️  Skipped metadata reset")
                    return False
            
            bucket = self.storage_client.bucket(TRAINING_BUCKET)
            metadata_blob = bucket.blob("metadata/games_count.json")
            
            # Create fresh metadata
            fresh_metadata = {
                "total": 0,
                "games": [],
                "last_updated": None,
                "reset_at": str(int(os.path.getmtime(__file__))),
                "note": "Reset for fresh start"
            }
            
            metadata_blob.upload_from_string(
                json.dumps(fresh_metadata, indent=2),
                content_type="application/json"
            )
            
            logger.info("✅ Games metadata reset to 0")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to reset metadata: {e}")
            return False
    
    def cleanup_all(self, confirm=False, keep_models=False):
        """Perform complete cleanup."""
        logger.info("🧹 Starting complete cleanup...")
        
        # List everything first
        endpoints = self.list_endpoints()
        models = self.list_models()
        
        if not endpoints and not models:
            logger.info("✨ Nothing to clean up!")
            return
        
        if not confirm and not self.dry_run:
            logger.warning("⚠️  This will delete ALL basketball endpoints and models!")
            confirm_all = input("Are you absolutely sure? Type 'DELETE' to confirm: ")
            if confirm_all != 'DELETE':
                logger.info("❌ Cleanup cancelled")
                return
        
        # Delete endpoints
        deleted_endpoints = 0
        for endpoint in endpoints:
            if self.delete_endpoint(endpoint, force=True):
                deleted_endpoints += 1
        
        # Delete models (if requested)
        deleted_models = 0
        if not keep_models:
            for model in models:
                if self.delete_model(model, force=True):
                    deleted_models += 1
        else:
            logger.info("📦 Keeping models as requested")
        
        # Reset metadata
        self.reset_games_metadata(force=True)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("🧹 CLEANUP COMPLETE")
        logger.info("="*60)
        logger.info(f"🗑️  Endpoints deleted: {deleted_endpoints}/{len(endpoints)}")
        if not keep_models:
            logger.info(f"🗑️  Models deleted: {deleted_models}/{len(models)}")
        logger.info("📊 Games metadata: Reset to 0")
        logger.info("\n✨ Ready for fresh start!")
        logger.info("="*60)
    
    def cleanup_selective(self):
        """Interactive selective cleanup."""
        logger.info("🎯 Selective cleanup mode")
        
        # Endpoints
        endpoints = self.list_endpoints()
        if endpoints:
            logger.info("📍 Endpoints cleanup:")
            for endpoint in endpoints:
                self.delete_endpoint(endpoint, force=False)
        
        # Models
        models = self.list_models()
        if models:
            logger.info("🤖 Models cleanup:")
            for model in models:
                self.delete_model(model, force=False)
        
        # Metadata
        self.reset_games_metadata(force=False)

def main():
    """Main cleanup function."""
    parser = argparse.ArgumentParser(description="Cleanup Vertex AI resources")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--keep-models", action="store_true", help="Keep trained models, only delete endpoints")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--all", action="store_true", help="Delete everything")
    parser.add_argument("--selective", action="store_true", help="Interactive selective cleanup")
    
    args = parser.parse_args()
    
    try:
        cleanup = CleanupManager(dry_run=args.dry_run)
        
        if args.all:
            cleanup.cleanup_all(confirm=args.confirm, keep_models=args.keep_models)
        elif args.selective:
            cleanup.cleanup_selective()
        else:
            # Default: show what exists and provide options
            logger.info("🔍 Current Vertex AI resources:")
            endpoints = cleanup.list_endpoints()
            models = cleanup.list_models()
            
            if not endpoints and not models:
                logger.info("✨ No resources found!")
                return
            
            print("\nOptions:")
            print("  --all           Delete everything")
            print("  --selective     Interactive cleanup")
            print("  --keep-models   Keep models, delete only endpoints")
            print("  --dry-run       Preview what would be deleted")
            print()
            print("Example: python scripts/setup/cleanup_and_reset.py --all --confirm")
        
    except Exception as e:
        logger.error(f"✗ Cleanup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()