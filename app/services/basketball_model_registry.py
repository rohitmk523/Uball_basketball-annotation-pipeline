"""
Basketball Model Registry - Track and manage tuned model versions for incremental training.

This registry system tracks:
- Model versions and their corresponding game count
- Tuned model IDs for use as base models in incremental training
- Model cleanup logic (every 5 games)
- Model performance metrics
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
from google.cloud import storage
from google.cloud import aiplatform

from app.core.config import settings

logger = logging.getLogger(__name__)


class BasketballModelRegistry:
    """
    Registry for tracking basketball annotation model versions and incremental training.
    
    This class manages:
    - Model version tracking (v1, v2, v3, etc.)
    - Game count tracking (how many games trained)
    - Tuned model ID storage for incremental training
    - Model cleanup strategy (every 5 games create new version)
    """
    
    METADATA_BUCKET = "uball-training-data"
    REGISTRY_FILE = "metadata/model_registry.json"
    GAMES_COUNT_FILE = "metadata/games_count.json"
    CLEANUP_INTERVAL = 5  # Create new version every 5 games
    
    def __init__(self):
        """Initialize the model registry with GCS storage."""
        self.storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bucket = self.storage_client.bucket(self.METADATA_BUCKET)
        
        # Initialize Vertex AI
        aiplatform.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION
        )
        
        logger.info("✓ Basketball Model Registry initialized")
    
    def get_latest_tuned_model(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent basketball tuned model ID for incremental training.
        
        This checks the registry for the latest successfully tuned model
        that can be used as a base model for the next training run.
        
        Returns:
            Dict with model info:
            {
                "model_id": "projects/.../locations/.../models/...",
                "model_name": "basketball-model-v1-5games",
                "version": 1,
                "games_trained": 5,
                "tuned_at": "2025-10-27T...",
                "base_model": "gemini-2.5-pro"
            }
            or None if no models exist yet
        """
        try:
            registry = self._load_registry()
            
            if not registry or "models" not in registry or len(registry["models"]) == 0:
                logger.info("🎯 No previous tuned models found - will use base Gemini 2.5 Pro")
                return None
            
            # Get the latest model (models are sorted by timestamp)
            latest_model = registry["models"][-1]
            
            # Validate the model still exists in Vertex AI
            if self._validate_model_exists(latest_model["model_id"]):
                logger.info(
                    f"🔄 Found latest tuned model: {latest_model['model_name']} "
                    f"(trained on {latest_model['games_trained']} games)"
                )
                return latest_model
            else:
                logger.warning(
                    f"⚠️ Latest model {latest_model['model_id']} not found in Vertex AI. "
                    "Will use base Gemini model."
                )
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting latest tuned model: {e}")
            return None
    
    def register_new_model(
        self,
        game_id: str,
        tuned_model_id: str,
        model_display_name: str,
        base_model: str,
        training_metrics: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Register a newly tuned model in the registry.
        
        Args:
            game_id: The game ID this model was trained on
            tuned_model_id: Full Vertex AI model resource name
            model_display_name: Display name for the model
            base_model: The base model used (either "gemini-2.5-pro" or a tuned model ID)
            training_metrics: Optional training performance metrics
            
        Returns:
            Dict with the registered model info
        """
        try:
            registry = self._load_registry()
            
            # Get current games count
            games_count = self._get_games_count()
            total_games = games_count["total"] + 1
            
            # Determine version
            version = self._calculate_version(total_games)
            
            # Create model entry
            model_entry = {
                "model_id": tuned_model_id,
                "model_name": model_display_name,
                "version": version,
                "games_trained": total_games,
                "game_id": game_id,
                "base_model": base_model,
                "tuned_at": datetime.utcnow().isoformat(),
                "metrics": training_metrics or {}
            }
            
            # Add to registry
            if "models" not in registry:
                registry["models"] = []
            
            registry["models"].append(model_entry)
            registry["last_updated"] = datetime.utcnow().isoformat()
            
            # Save registry
            self._save_registry(registry)
            
            # Update games count
            self._update_games_count(game_id, model_display_name)
            
            logger.info(
                f"✅ Registered new model: {model_display_name} "
                f"(version {version}, {total_games} games trained)"
            )
            
            # Check if cleanup is needed
            if self.should_cleanup_models(total_games):
                logger.info(
                    f"📊 Reached {self.CLEANUP_INTERVAL} games - "
                    "consider cleaning up old model versions"
                )
            
            return model_entry
            
        except Exception as e:
            logger.error(f"❌ Error registering new model: {e}")
            raise
    
    def should_cleanup_models(self, total_games: Optional[int] = None) -> bool:
        """
        Check if we should cleanup old models (every 5 games).
        
        Args:
            total_games: Optional total games count (will fetch if not provided)
            
        Returns:
            True if cleanup should be performed
        """
        if total_games is None:
            games_count = self._get_games_count()
            total_games = games_count["total"]
        
        # Cleanup every CLEANUP_INTERVAL games
        return total_games > 0 and total_games % self.CLEANUP_INTERVAL == 0
    
    def get_model_history(self) -> List[Dict[str, Any]]:
        """
        Get the full history of trained models.
        
        Returns:
            List of model entries, sorted by training date
        """
        try:
            registry = self._load_registry()
            return registry.get("models", [])
        except Exception as e:
            logger.error(f"❌ Error getting model history: {e}")
            return []
    
    def determine_base_model(self) -> Dict[str, Any]:
        """
        Determine which base model to use for the next training run.
        
        This implements the incremental training logic:
        - If no models exist: Use base Gemini 2.5 Pro
        - If models exist: Use the latest tuned model
        
        Returns:
            Dict with base model info:
            {
                "model_id": "gemini-2.5-pro" or "projects/.../models/...",
                "is_base_model": True/False,
                "games_trained": 0 or N
            }
        """
        latest_model = self.get_latest_tuned_model()
        
        if latest_model is None:
            logger.info("🎯 First training - using base Gemini 2.5 Pro")
            return {
                "model_id": "gemini-2.5-pro",
                "model_name": "gemini-2.5-pro",
                "is_base_model": True,
                "games_trained": 0
            }
        else:
            logger.info(
                f"🔄 Incremental training - using {latest_model['model_name']} "
                f"({latest_model['games_trained']} games)"
            )
            return {
                "model_id": latest_model["model_id"],
                "model_name": latest_model["model_name"],
                "is_base_model": False,
                "games_trained": latest_model["games_trained"]
            }
    
    def _validate_model_exists(self, model_id: str) -> bool:
        """
        Validate that a model exists in Vertex AI.
        
        Args:
            model_id: Full Vertex AI model resource name
            
        Returns:
            True if model exists, False otherwise
        """
        try:
            # Try to get the model
            model = aiplatform.Model(model_id)
            model.display_name  # Access a property to verify it exists
            return True
        except Exception as e:
            logger.warning(f"⚠️ Model validation failed for {model_id}: {e}")
            return False
    
    def _calculate_version(self, total_games: int) -> int:
        """
        Calculate model version based on total games trained.
        
        Version increments every CLEANUP_INTERVAL games:
        - Games 1-4: v1
        - Games 5-9: v2
        - Games 10-14: v3
        etc.
        
        Args:
            total_games: Total number of games trained
            
        Returns:
            Version number
        """
        return (total_games - 1) // self.CLEANUP_INTERVAL + 1
    
    def _load_registry(self) -> Dict[str, Any]:
        """
        Load the model registry from GCS.
        
        Returns:
            Registry dict or empty dict if file doesn't exist
        """
        try:
            blob = self.bucket.blob(self.REGISTRY_FILE)
            
            if not blob.exists():
                logger.info("📝 No registry file found, creating new registry")
                return {
                    "models": [],
                    "created_at": datetime.utcnow().isoformat(),
                    "last_updated": datetime.utcnow().isoformat()
                }
            
            content = blob.download_as_string()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"❌ Error loading registry: {e}")
            return {
                "models": [],
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat()
            }
    
    def _save_registry(self, registry: Dict[str, Any]):
        """
        Save the model registry to GCS.
        
        Args:
            registry: Registry dict to save
        """
        try:
            blob = self.bucket.blob(self.REGISTRY_FILE)
            blob.upload_from_string(
                json.dumps(registry, indent=2),
                content_type="application/json"
            )
            logger.info("✅ Registry saved to GCS")
        except Exception as e:
            logger.error(f"❌ Error saving registry: {e}")
            raise
    
    def _get_games_count(self) -> Dict[str, Any]:
        """
        Get the current games count from GCS.
        
        Returns:
            Games count dict with total and games list
        """
        try:
            blob = self.bucket.blob(self.GAMES_COUNT_FILE)
            
            if not blob.exists():
                return {"total": 0, "games": []}
            
            content = blob.download_as_string()
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"❌ Error getting games count: {e}")
            return {"total": 0, "games": []}
    
    def _update_games_count(self, game_id: str, model_name: str):
        """
        Update the games count in GCS.
        
        Args:
            game_id: Game ID to add
            model_name: Model name for this game
        """
        try:
            count_data = self._get_games_count()
            
            # Add new game entry
            count_data["games"].append({
                "game_id": game_id,
                "model_name": model_name,
                "timestamp": datetime.utcnow().isoformat()
            })
            count_data["total"] = len(count_data["games"])
            count_data["last_updated"] = datetime.utcnow().isoformat()
            
            # Save updated count
            blob = self.bucket.blob(self.GAMES_COUNT_FILE)
            blob.upload_from_string(
                json.dumps(count_data, indent=2),
                content_type="application/json"
            )
            
            logger.info(f"✅ Updated games count: {count_data['total']} total games")
            
        except Exception as e:
            logger.error(f"❌ Error updating games count: {e}")
            raise
    
    def cleanup_old_models(self, keep_latest: int = 2):
        """
        Cleanup old model versions from Vertex AI (keep only latest N).
        
        This should be called periodically to reduce storage costs.
        
        Args:
            keep_latest: Number of latest models to keep
        """
        try:
            registry = self._load_registry()
            models = registry.get("models", [])
            
            if len(models) <= keep_latest:
                logger.info(f"✅ Only {len(models)} models exist, no cleanup needed")
                return
            
            # Models to delete (all except latest N)
            models_to_delete = models[:-keep_latest]
            
            logger.info(
                f"🧹 Cleaning up {len(models_to_delete)} old model versions "
                f"(keeping latest {keep_latest})"
            )
            
            for model_info in models_to_delete:
                try:
                    model = aiplatform.Model(model_info["model_id"])
                    model.delete()
                    logger.info(f"✅ Deleted model: {model_info['model_name']}")
                except Exception as e:
                    logger.warning(
                        f"⚠️ Failed to delete model {model_info['model_name']}: {e}"
                    )
            
            # Update registry to remove deleted models
            registry["models"] = models[-keep_latest:]
            registry["last_cleanup"] = datetime.utcnow().isoformat()
            self._save_registry(registry)
            
            logger.info("✅ Model cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during model cleanup: {e}")
            raise


# Global registry instance
_registry_instance: Optional[BasketballModelRegistry] = None


def get_model_registry() -> BasketballModelRegistry:
    """
    Get or create the global model registry instance.
    
    Returns:
        BasketballModelRegistry instance
    """
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = BasketballModelRegistry()
    
    return _registry_instance

