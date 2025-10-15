"""
Annotation parser to convert AI model output to database-ready plays.
"""

import logging
from typing import List
from supabase import Client

from app.models.schemas import (
    VertexAIAnnotation,
    PlayCreate,
    Event,
    CameraAngle,
    EventLabel
)
from app.services.player_matcher_service import PlayerMatcherService

logger = logging.getLogger(__name__)


class AnnotationParser:
    """Parser for converting AI annotations to database plays."""
    
    def __init__(self, supabase: Client):
        """
        Initialize annotation parser.
        
        Args:
            supabase: Supabase client
        """
        self.player_matcher = PlayerMatcherService(supabase)
    
    async def parse_annotations_to_plays(
        self,
        annotations: List[VertexAIAnnotation],
        game_id: str,
        angle: CameraAngle
    ) -> List[PlayCreate]:
        """
        Convert AI annotations to PlayCreate objects ready for database insertion.
        
        Args:
            annotations: Raw annotations from AI model
            game_id: Game UUID
            angle: Camera angle
            
        Returns:
            List of PlayCreate objects
        """
        if not annotations:
            logger.warning("⚠ No annotations to parse")
            return []
        
        logger.info(f"Parsing {len(annotations)} annotations for game {game_id}")
        
        # Load players for this game
        players = await self.player_matcher.load_players_for_game(game_id)
        logger.info(f"✓ Loaded {len(players)} players for matching")
        
        plays = []
        
        for annotation in annotations:
            try:
                play = await self._parse_single_annotation(
                    annotation,
                    game_id,
                    angle,
                    players
                )
                plays.append(play)
            except Exception as e:
                logger.error(f"✗ Failed to parse annotation: {e}")
                logger.debug(f"Problematic annotation: {annotation}")
                continue
        
        logger.info(f"✓ Successfully parsed {len(plays)} plays")
        
        return plays
    
    async def _parse_single_annotation(
        self,
        annotation: VertexAIAnnotation,
        game_id: str,
        angle: CameraAngle,
        players: List
    ) -> PlayCreate:
        """
        Parse a single annotation into a PlayCreate object.
        
        Args:
            annotation: Single AI annotation
            game_id: Game UUID
            angle: Camera angle
            players: List of players for matching
            
        Returns:
            PlayCreate object
        """
        # Match players to IDs
        player_a_id = None
        player_b_id = None
        
        if annotation.player_a:
            player_a_id = self.player_matcher.match_player(
                annotation.player_a,
                players
            )
        
        if annotation.player_b:
            player_b_id = self.player_matcher.match_player(
                annotation.player_b,
                players
            )
        
        # Parse events and enrich with player IDs
        events = []
        for event_data in annotation.events:
            # Match players in events
            event_player_a_id = None
            event_player_b_id = None
            
            if event_data.get("playerA"):
                event_player_a_id = self.player_matcher.match_player(
                    event_data["playerA"],
                    players
                )
            
            if event_data.get("playerB"):
                event_player_b_id = self.player_matcher.match_player(
                    event_data["playerB"],
                    players
                )
            
            # Create Event object
            try:
                event = Event(
                    label=EventLabel(event_data["label"]),
                    playerA=event_data.get("playerA"),
                    playerAId=event_player_a_id,
                    playerB=event_data.get("playerB"),
                    playerBId=event_player_b_id
                )
                events.append(event)
            except Exception as e:
                logger.warning(f"⚠ Failed to parse event: {e}")
                logger.debug(f"Event data: {event_data}")
                continue
        
        # Convert classification string to EventLabel enum
        try:
            classification = EventLabel(annotation.classification)
        except ValueError:
            logger.warning(
                f"⚠ Unknown classification: {annotation.classification}, "
                f"defaulting to FG_MAKE"
            )
            classification = EventLabel.FG_MAKE
        
        # Create PlayCreate object
        play = PlayCreate(
            game_id=game_id,
            angle=angle,
            timestamp_seconds=annotation.timestamp_seconds,
            classification=classification,
            note=annotation.note,
            player_a=annotation.player_a,
            player_a_id=player_a_id,
            player_b=annotation.player_b,
            player_b_id=player_b_id,
            events=events
        )
        
        return play

