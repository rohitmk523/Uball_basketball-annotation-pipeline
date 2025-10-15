"""
Plays service for database operations on plays table.
"""

import logging
from typing import List, Optional
from supabase import Client

from app.models.schemas import Play, PlayCreate, CameraAngle

logger = logging.getLogger(__name__)


class PlaysService:
    """Service for plays database operations."""
    
    def __init__(self, supabase: Client):
        """
        Initialize plays service.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
    
    async def get_plays_for_game(
        self,
        game_id: str,
        angle: Optional[CameraAngle] = None
    ) -> List[Play]:
        """
        Get all plays for a game.
        
        Args:
            game_id: Game UUID
            angle: Optional camera angle filter
            
        Returns:
            List of plays
        """
        try:
            query = (
                self.supabase.table("plays")
                .select("*")
                .eq("game_id", game_id)
            )
            
            if angle:
                query = query.eq("angle", angle.value)
            
            response = query.order("timestamp_seconds").execute()
            
            plays = [Play(**play_data) for play_data in response.data]
            logger.info(f"✓ Retrieved {len(plays)} plays for game {game_id}")
            
            return plays
            
        except Exception as e:
            logger.error(f"✗ Error fetching plays: {e}")
            raise
    
    async def create_play(self, play: PlayCreate) -> Play:
        """
        Create a new play in the database.
        
        Args:
            play: Play creation data
            
        Returns:
            Created play
        """
        try:
            # Convert play to dict for insertion
            play_data = play.model_dump()
            
            # Convert enums to strings
            if "angle" in play_data and hasattr(play_data["angle"], "value"):
                play_data["angle"] = play_data["angle"].value
            if "classification" in play_data and hasattr(play_data["classification"], "value"):
                play_data["classification"] = play_data["classification"].value
            
            # Convert events to list of dicts
            if "events" in play_data:
                play_data["events"] = [
                    event.model_dump() if hasattr(event, "model_dump") else event
                    for event in play_data["events"]
                ]
            
            response = (
                self.supabase.table("plays")
                .insert(play_data)
                .execute()
            )
            
            if response.data and len(response.data) > 0:
                created_play = Play(**response.data[0])
                logger.info(f"✓ Created play: {created_play.id}")
                return created_play
            else:
                raise Exception("No data returned from insert")
                
        except Exception as e:
            logger.error(f"✗ Error creating play: {e}")
            raise
    
    async def create_plays_batch(self, plays: List[PlayCreate]) -> List[Play]:
        """
        Create multiple plays in a batch.
        
        Args:
            plays: List of play creation data
            
        Returns:
            List of created plays
        """
        try:
            # Convert plays to dicts
            plays_data = []
            for play in plays:
                play_data = play.model_dump()
                
                # Convert enums
                if "angle" in play_data and hasattr(play_data["angle"], "value"):
                    play_data["angle"] = play_data["angle"].value
                if "classification" in play_data and hasattr(play_data["classification"], "value"):
                    play_data["classification"] = play_data["classification"].value
                
                # Convert events
                if "events" in play_data:
                    play_data["events"] = [
                        event.model_dump() if hasattr(event, "model_dump") else event
                        for event in play_data["events"]
                    ]
                
                plays_data.append(play_data)
            
            response = (
                self.supabase.table("plays")
                .insert(plays_data)
                .execute()
            )
            
            created_plays = [Play(**play_data) for play_data in response.data]
            logger.info(f"✓ Created {len(created_plays)} plays in batch")
            
            return created_plays
            
        except Exception as e:
            logger.error(f"✗ Error creating plays batch: {e}")
            raise
    
    async def delete_plays_for_game(
        self,
        game_id: str,
        angle: CameraAngle
    ) -> int:
        """
        Delete all plays for a game and angle.
        
        Args:
            game_id: Game UUID
            angle: Camera angle
            
        Returns:
            Number of plays deleted
        """
        try:
            # First, get count
            existing = await self.get_plays_for_game(game_id, angle)
            count = len(existing)
            
            if count > 0:
                # Delete plays
                self.supabase.table("plays").delete().eq("game_id", game_id).eq("angle", angle.value).execute()
                logger.info(f"✓ Deleted {count} plays for game {game_id}, angle {angle}")
            else:
                logger.info(f"No plays to delete for game {game_id}, angle {angle}")
            
            return count
            
        except Exception as e:
            logger.error(f"✗ Error deleting plays: {e}")
            raise

