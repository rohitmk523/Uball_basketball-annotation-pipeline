"""
Cloud Function for exporting plays from Supabase.

This function:
1. Receives HTTP request with game_id
2. Connects to Supabase 
3. Exports plays for the game
4. Uploads results to GCS
5. Returns file paths for next steps
"""

import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import functions_framework
from flask import Request
from supabase import create_client, Client
from google.cloud import storage
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") 
GCS_TRAINING_BUCKET = os.environ.get("GCS_TRAINING_BUCKET")
TRAINING_SPLIT = 0.8  # 80% training, 20% validation


class PlaysExporter:
    """Export plays from Supabase for training."""
    
    def __init__(self, game_id: str = None):
        """Initialize exporter."""
        self.game_id = game_id
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(GCS_TRAINING_BUCKET)
        
        logger.info(f"✓ Initialized PlaysExporter for game: {game_id}")

    def export_plays(self) -> Dict[str, Any]:
        """Export plays and return file information."""
        try:
            # Query plays from Supabase
            query = self.supabase.table("plays").select("*")
            
            if self.game_id:
                query = query.eq("game_id", self.game_id)
                logger.info(f"📊 Filtering plays for game: {self.game_id}")
            
            # Execute query with filters for valid plays
            response = (query
                       .not_.is_("start_timestamp", "null")
                       .not_.is_("end_timestamp", "null")
                       .not_.is_("events", "null")
                       .execute())
            
            plays = response.data
            logger.info(f"📊 Found {len(plays)} plays")
            
            if not plays:
                raise ValueError(f"No plays found for game {self.game_id}")
            
            # Filter valid plays
            valid_plays = []
            for play in plays:
                if (play.get("events") and 
                    len(play.get("events", [])) > 0 and
                    play.get("start_timestamp") is not None and 
                    play.get("end_timestamp") is not None and
                    play.get("start_timestamp") < play.get("end_timestamp")):
                    valid_plays.append(play)
            
            logger.info(f"📊 Found {len(valid_plays)} valid plays after filtering")
            
            # Create train/validation split
            split_idx = int(len(valid_plays) * TRAINING_SPLIT)
            training_plays = valid_plays[:split_idx]
            validation_plays = valid_plays[split_idx:]
            
            logger.info(f"📊 Split: {len(training_plays)} training, {len(validation_plays)} validation")
            
            # Upload to GCS
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            game_suffix = f"_{self.game_id}" if self.game_id else ""
            
            files_uploaded = {}
            
            # Upload all plays
            all_plays_path = f"exports/all_plays{game_suffix}_{timestamp}.json"
            files_uploaded["all_plays"] = self._upload_json_to_gcs(valid_plays, all_plays_path)
            
            # Upload training plays
            training_path = f"exports/training_plays{game_suffix}_{timestamp}.json"
            files_uploaded["training_plays"] = self._upload_json_to_gcs(training_plays, training_path)
            
            # Upload validation plays  
            validation_path = f"exports/validation_plays{game_suffix}_{timestamp}.json"
            files_uploaded["validation_plays"] = self._upload_json_to_gcs(validation_plays, validation_path)
            
            logger.info("✅ Successfully exported plays to GCS")
            
            return {
                "success": True,
                "game_id": self.game_id,
                "total_plays": len(valid_plays),
                "training_plays": len(training_plays),
                "validation_plays": len(validation_plays),
                "files": files_uploaded,
                "timestamp": timestamp
            }
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            raise
    
    def _upload_json_to_gcs(self, data: List[Dict], gcs_path: str) -> str:
        """Upload JSON data to GCS and return public URL."""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(data, f, indent=2, default=str)
                temp_path = f.name
            
            # Upload to GCS
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            gcs_uri = f"gs://{GCS_TRAINING_BUCKET}/{gcs_path}"
            logger.info(f"✓ Uploaded {len(data)} items to {gcs_uri}")
            
            return gcs_uri
            
        except Exception as e:
            logger.error(f"❌ GCS upload failed: {e}")
            raise


@functions_framework.http
def export_plays_cf(request: Request) -> Dict[str, Any]:
    """
    Cloud Function entry point for exporting plays.
    
    Expected request body:
    {
        "game_id": "uuid-string"  # Optional
    }
    
    Returns:
    {
        "success": true,
        "game_id": "uuid-string",
        "total_plays": 213,
        "files": {
            "all_plays": "gs://bucket/path/to/all_plays.json",
            "training_plays": "gs://bucket/path/to/training.json",
            "validation_plays": "gs://bucket/path/to/validation.json"
        }
    }
    """
    try:
        # Handle CORS preflight
        if request.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '3600'
            }
            return ('', 204, headers)
        
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json:
            request_json = {}
        
        game_id = request_json.get('game_id')
        
        logger.info(f"🚀 Starting export for game: {game_id}")
        
        # Validate environment variables
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise ValueError("Missing Supabase configuration")
        
        if not GCS_TRAINING_BUCKET:
            raise ValueError("Missing GCS bucket configuration")
        
        # Export plays
        exporter = PlaysExporter(game_id)
        result = exporter.export_plays()
        
        logger.info(f"✅ Export completed successfully")
        
        # Return success response
        headers = {'Access-Control-Allow-Origin': '*'}
        return (result, 200, headers)
        
    except Exception as e:
        logger.error(f"❌ Export function failed: {e}")
        
        error_response = {
            "success": False,
            "error": str(e),
            "game_id": request_json.get('game_id') if 'request_json' in locals() else None
        }
        
        headers = {'Access-Control-Allow-Origin': '*'}
        return (error_response, 500, headers)