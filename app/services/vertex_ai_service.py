"""
Vertex AI service for calling fine-tuned Gemini model.
"""

import logging
from typing import List, Optional, Dict, Any
import json
from google.cloud import aiplatform
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

from app.core.config import settings
from app.models.schemas import VertexAIAnnotation

logger = logging.getLogger(__name__)


class VertexAIService:
    """Service for interacting with fine-tuned Vertex AI model."""
    
    def __init__(self):
        """Initialize Vertex AI client."""
        aiplatform.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION
        )
        self.endpoint_name = settings.VERTEX_AI_FINETUNED_ENDPOINT
        logger.info(f"✓ Vertex AI service initialized for project {settings.GCP_PROJECT_ID}")
    
    def _build_prompt(self) -> str:
        """
        Build prompt for the AI model (multi-angle version).
        
        Returns:
            Prompt string
        """
        prompt = """Analyze these basketball game videos from multiple camera angles and identify all plays with their events.

You are provided with multiple camera angles of the same play to give you better context:
- Far camera angles provide wide court view and team formation context  
- Near camera angles provide close-up details of player numbers and jerseys

For each play, provide:
1. timestamp_seconds: The time in the video when the play occurs
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FOUL, etc.)
3. note: A detailed description of what happened
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable
6. events: Array of all events in the play, each with:
   - label: Event type
   - playerA: Player identifier
   - playerB: Secondary player if applicable

Return a JSON array of plays. Example format:
[
  {
    "timestamp_seconds": 45.2,
    "classification": "FG_MAKE",
    "note": "Player #5 (Yellow A) made a two-point shot, assisted by Player #3 (Yellow A)",
    "player_a": "Player #5 (Yellow A)",
    "player_b": "Player #3 (Yellow A)",
    "events": [
      {
        "label": "ASSIST",
        "playerA": "Player #3 (Yellow A)"
      },
      {
        "label": "FG_MAKE", 
        "playerA": "Player #5 (Yellow A)"
      }
    ]
  }
]

Use information from all provided camera angles to accurately identify player numbers and team colors. Be precise with timestamps and identify all basketball events including shots, fouls, rebounds, assists, steals, blocks, and turnovers."""
        
        return prompt
    
    async def annotate_video(self, gcs_uri: str) -> List[VertexAIAnnotation]:
        """
        Send video to Vertex AI model for annotation.
        
        Args:
            gcs_uri: GCS URI of the video (gs://bucket/path/video.mp4)
            
        Returns:
            List of annotations from the model
            
        Raises:
            Exception if model call fails
        """
        if not self.endpoint_name:
            raise Exception(
                "VERTEX_AI_FINETUNED_ENDPOINT not configured. "
                "Please complete model training and update .env file."
            )
        
        try:
            logger.info(f"Calling Vertex AI model for video: {gcs_uri}")
            
            # Get endpoint
            endpoint = aiplatform.Endpoint(self.endpoint_name)
            
            # Build request with video and prompt
            # Format for Gemini multimodal input
            instances = [
                {
                    "video": {
                        "gcsUri": gcs_uri
                    },
                    "prompt": self._build_prompt(gcs_uri)
                }
            ]
            
            # Call endpoint
            response = endpoint.predict(instances=instances)
            
            logger.info("✓ Received response from Vertex AI model")
            
            # Parse response
            annotations = self._parse_response(response)
            
            logger.info(f"✓ Parsed {len(annotations)} annotations from model response")
            
            return annotations
            
        except Exception as e:
            logger.error(f"✗ Error calling Vertex AI model: {e}")
            raise
    
    def _parse_response(self, response) -> List[VertexAIAnnotation]:
        """
        Parse Vertex AI response into structured annotations.
        
        Args:
            response: Vertex AI prediction response
            
        Returns:
            List of VertexAIAnnotation objects
        """
        try:
            # Extract predictions from response
            predictions = response.predictions
            
            if not predictions:
                logger.warning("⚠ No predictions in model response")
                return []
            
            # The model should return JSON array of plays
            # Parse the first prediction (assuming single video input)
            result = predictions[0]
            
            # Handle different response formats
            if isinstance(result, str):
                # If response is string, parse as JSON
                plays_data = json.loads(result)
            elif isinstance(result, dict):
                # If response is dict, use directly
                plays_data = result if isinstance(result, list) else [result]
            elif isinstance(result, list):
                # If response is already list
                plays_data = result
            else:
                logger.error(f"Unexpected response type: {type(result)}")
                return []
            
            # Convert to VertexAIAnnotation objects
            annotations = []
            for play_data in plays_data:
                try:
                    annotation = VertexAIAnnotation(**play_data)
                    annotations.append(annotation)
                except Exception as e:
                    logger.warning(f"⚠ Failed to parse annotation: {e}")
                    logger.debug(f"Problematic data: {play_data}")
                    continue
            
            return annotations
            
        except json.JSONDecodeError as e:
            logger.error(f"✗ Failed to parse JSON response: {e}")
            logger.debug(f"Response: {response}")
            return []
        except Exception as e:
            logger.error(f"✗ Error parsing response: {e}")
            return []
    
    async def annotate_video_with_retry(
        self,
        gcs_uri: str,
        max_retries: int = 3
    ) -> List[VertexAIAnnotation]:
        """
        Annotate video with retry logic.
        
        Args:
            gcs_uri: GCS URI of the video
            max_retries: Maximum number of retry attempts
            
        Returns:
            List of annotations
        """
        import asyncio
        
        for attempt in range(max_retries):
            try:
                annotations = await self.annotate_video(gcs_uri)
                return annotations
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(
                        f"⚠ Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"✗ All {max_retries} attempts failed")
                    raise

