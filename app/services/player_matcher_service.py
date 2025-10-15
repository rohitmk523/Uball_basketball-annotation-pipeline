"""
Player matching service to match AI-identified players to Supabase player IDs.
"""

import logging
import re
from typing import Optional, Dict, List
from supabase import Client

from app.models.schemas import Player

logger = logging.getLogger(__name__)


class PlayerMatcherService:
    """Service for matching player strings to player IDs."""
    
    def __init__(self, supabase: Client):
        """
        Initialize player matcher service.
        
        Args:
            supabase: Supabase client
        """
        self.supabase = supabase
        self._player_cache: Dict[str, List[Player]] = {}
    
    async def load_players_for_game(self, game_id: str) -> List[Player]:
        """
        Load all players for a game (from both teams).
        
        Args:
            game_id: Game UUID
            
        Returns:
            List of players
        """
        # Check cache first
        if game_id in self._player_cache:
            logger.debug(f"Using cached players for game {game_id}")
            return self._player_cache[game_id]
        
        try:
            # Get game to find team IDs
            game_response = (
                self.supabase.table("games")
                .select("team_a_id, team_b_id")
                .eq("id", game_id)
                .execute()
            )
            
            if not game_response.data:
                logger.warning(f"⚠ Game not found: {game_id}")
                return []
            
            game = game_response.data[0]
            team_a_id = game.get("team_a_id")
            team_b_id = game.get("team_b_id")
            
            # Load players from both teams
            players = []
            
            for team_id in [team_a_id, team_b_id]:
                if team_id:
                    team_players_response = (
                        self.supabase.table("players")
                        .select("*")
                        .eq("team_id", team_id)
                        .execute()
                    )
                    
                    for player_data in team_players_response.data:
                        players.append(Player(**player_data))
            
            # Cache for future use
            self._player_cache[game_id] = players
            
            logger.info(f"✓ Loaded {len(players)} players for game {game_id}")
            
            return players
            
        except Exception as e:
            logger.error(f"✗ Error loading players for game: {e}")
            return []
    
    def _extract_jersey_and_color(self, player_string: str) -> tuple[Optional[int], Optional[str]]:
        """
        Extract jersey number and color from player string.
        
        Args:
            player_string: String like "Player #5 (Yellow A)" or "#23 Blue"
            
        Returns:
            Tuple of (jersey_number, color)
        """
        if not player_string:
            return None, None
        
        # Extract jersey number
        jersey_match = re.search(r'#(\d+)', player_string)
        jersey_number = int(jersey_match.group(1)) if jersey_match else None
        
        # Extract color
        colors = ['yellow', 'blue', 'red', 'green', 'white', 'black', 'gray', 'grey', 'orange', 'purple']
        color = None
        
        player_lower = player_string.lower()
        for c in colors:
            if c in player_lower:
                color = c
                break
        
        return jersey_number, color
    
    def match_player(
        self,
        player_string: Optional[str],
        players: List[Player]
    ) -> Optional[str]:
        """
        Match a player string to a player ID.
        
        Args:
            player_string: String like "Player #5 (Yellow A)"
            players: List of available players
            
        Returns:
            Player UUID if match found, None otherwise
        """
        if not player_string or not players:
            return None
        
        # Extract jersey and color
        jersey_number, color = self._extract_jersey_and_color(player_string)
        
        if not jersey_number:
            logger.debug(f"Could not extract jersey number from: {player_string}")
            return None
        
        # Try to find exact match by jersey number
        matches = [p for p in players if p.jersey_number == jersey_number]
        
        if len(matches) == 1:
            # Only one player with this number
            logger.debug(f"✓ Matched {player_string} → {matches[0].name} (#{matches[0].jersey_number})")
            return matches[0].id
        elif len(matches) > 1:
            # Multiple players with same number - use color to disambiguate
            if color:
                color_matches = [
                    p for p in matches
                    if p.jersey_color and color.lower() in p.jersey_color.lower()
                ]
                
                if len(color_matches) == 1:
                    logger.debug(
                        f"✓ Matched {player_string} → {color_matches[0].name} "
                        f"(#{color_matches[0].jersey_number}, {color_matches[0].jersey_color})"
                    )
                    return color_matches[0].id
                elif len(color_matches) > 1:
                    # Still ambiguous - return first match
                    logger.warning(
                        f"⚠ Ambiguous match for {player_string}, using first match"
                    )
                    return color_matches[0].id
            
            # No color or couldn't disambiguate - return first match
            logger.warning(f"⚠ Multiple matches for {player_string}, using first")
            return matches[0].id
        else:
            # No matches found
            logger.debug(f"⚠ No match found for: {player_string}")
            return None
    
    def clear_cache(self):
        """Clear the player cache."""
        self._player_cache.clear()
        logger.debug("Player cache cleared")

