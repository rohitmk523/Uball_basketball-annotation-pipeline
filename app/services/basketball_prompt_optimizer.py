"""
Basketball Prompt Optimizer - Basketball-specific prompt engineering for Gemini 2.5 Pro.

This module provides optimized prompts based on Google's AI Basketball Coach implementation,
focusing on:
- Video timestamping for critical events
- Player positioning and movement analysis
- Ball tracking and shot mechanics
- Multi-angle camera processing
- Biomechanical insights
"""

import logging
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class BasketballContext(str, Enum):
    """Basketball game context types."""
    OFFENSIVE_POSSESSION = "offensive_possession"
    DEFENSIVE_POSSESSION = "defensive_possession"
    TRANSITION = "transition"
    FREE_THROW = "free_throw"
    TIMEOUT = "timeout"
    FULL_GAME = "full_game"


class BasketballPromptOptimizer:
    """
    Optimizes prompts for basketball video analysis using Gemini 2.5 Pro.
    
    Based on Google's proven basketball AI implementation, this class
    provides context-aware prompts for maximum annotation accuracy.
    """
    
    def __init__(self):
        """Initialize the prompt optimizer."""
        logger.info("✓ Basketball Prompt Optimizer initialized")
    
    def build_annotation_prompt(
        self,
        context: BasketballContext = BasketballContext.FULL_GAME,
        game_phase: Optional[str] = None,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        Build an optimized prompt for basketball video annotation.
        
        Args:
            context: The basketball context (full game, possession, etc.)
            game_phase: Optional game phase (e.g., "4th quarter", "overtime")
            focus_areas: Optional list of specific areas to focus on
            
        Returns:
            Optimized prompt string for Gemini 2.5 Pro
        """
        base_prompt = self._get_base_basketball_prompt()
        
        # Add context-specific instructions
        if context != BasketballContext.FULL_GAME:
            base_prompt += f"\n\n{self._get_context_instructions(context)}"
        
        # Add game phase context
        if game_phase:
            base_prompt += f"\n\nGame Phase: {game_phase}"
        
        # Add focus areas
        if focus_areas:
            base_prompt += f"\n\nFocus Areas: {', '.join(focus_areas)}"
        
        return base_prompt
    
    def _get_base_basketball_prompt(self) -> str:
        """
        Get the base prompt optimized for basketball annotation.
        
        Returns:
            Base prompt string
        """
        return """You are an expert basketball analyst with deep knowledge of the game. Analyze this basketball video and identify all plays with precise timing and detailed descriptions.

🏀 BASKETBALL EXPERTISE REQUIRED:
- Understand offensive and defensive strategies
- Recognize set plays, pick-and-rolls, fast breaks
- Identify proper basketball terminology
- Analyze player positioning and court spacing
- Track ball movement and possession changes

📹 MULTI-ANGLE VIDEO ANALYSIS:
You may receive multiple camera angles of the same play:
- **Wide Court View (Far Camera)**: Shows full team formations, spacing, and overall strategy
- **Close-Up View (Near Camera)**: Shows player numbers, jersey details, and individual actions
- Use information from ALL angles to create accurate annotations

⏱️ CRITICAL TIMESTAMPS:
For each play, identify key moments with precise timestamps:
1. **Play Initiation**: When the action begins (inbound, dribble start, etc.)
2. **Key Action**: The main event (shot attempt, pass, defensive play)
3. **Resolution**: How the play ends (make/miss, turnover, foul)

📊 REQUIRED OUTPUT FORMAT:
Return a JSON array of plays with this structure:

[
  {
    "timestamp_seconds": 45.2,
    "classification": "FG_MAKE",
    "note": "Detailed play description with player numbers and actions",
    "player_a": "Player #5 (Yellow A)",
    "player_b": "Player #3 (Yellow A)",
    "court_region": "paint",
    "shot_type": "layup",
    "game_context": {
      "offensive_play": "pick and roll",
      "defensive_setup": "man-to-man",
      "ball_movement": "drive and dish"
    },
    "events": [
      {
        "label": "ASSIST",
        "playerA": "Player #3 (Yellow A)",
        "timestamp": 44.8,
        "description": "Point guard penetrates and kicks out"
      },
      {
        "label": "FG_MAKE",
        "playerA": "Player #5 (Yellow A)",
        "timestamp": 45.2,
        "description": "Catch and shoot from corner"
      }
    ]
  }
]

🎯 EVENT TYPES TO IDENTIFY:
**Scoring Events:**
- FG_MAKE, FG_MISS: Two-point field goals
- 3PT_MAKE, 3PT_MISS: Three-point attempts
- FT_MAKE, FT_MISS: Free throws

**Player Actions:**
- ASSIST: Pass leading directly to a score
- REBOUND: Offensive or defensive rebound (specify)
- STEAL: Defensive player takes possession
- BLOCK: Shot rejection
- TURNOVER: Lost possession (type: travel, bad pass, etc.)

**Fouls:**
- FOUL_SHOOTING: Foul during shot attempt
- FOUL_PERSONAL: Standard personal foul
- FOUL_OFFENSIVE: Charging, illegal screen
- FOUL_TECHNICAL: Technical foul

**Other Events:**
- TIMEOUT: Called timeout
- SUBSTITUTION: Player change
- JUMP_BALL: Held ball situation

🏀 BASKETBALL-SPECIFIC ANALYSIS:
1. **Player Identification**: Use jersey numbers and team colors. Format: "Player #XX (Color Team)"
2. **Court Position**: Identify location (paint, perimeter, corner, top of key, etc.)
3. **Shot Types**: Specify (layup, dunk, jump shot, hook shot, fadeaway, etc.)
4. **Play Types**: Recognize and name (pick and roll, isolation, fast break, post-up, etc.)
5. **Defensive Strategy**: Note man-to-man, zone, press, etc.

⚠️ ACCURACY REQUIREMENTS:
- **Timestamp Precision**: Within ±0.5 seconds of actual event
- **Player Numbers**: Must be accurate from close-up angles
- **Event Sequence**: Chronological order with all related sub-events
- **Team Colors**: Consistently identify teams throughout video

💡 BEST PRACTICES:
- Cross-reference multiple camera angles for accuracy
- Include context: "Player #23 drives baseline after pick from #45"
- Note momentum: "Fast break opportunity after defensive rebound"
- Identify impact: "Critical three-pointer extending lead to 8 points"
- Use basketball terminology: "Euro-step layup", "Step-back three", etc.

🔍 ATTENTION TO DETAIL:
- Track assists even on simple plays
- Note defensive contributions (good defense, contests)
- Identify hockey assists (pass before the assist)
- Record screen assists (player setting effective picks)
- Highlight transition defense effectiveness

Return ONLY the JSON array. Be thorough, precise, and use proper basketball knowledge."""
    
    def _get_context_instructions(self, context: BasketballContext) -> str:
        """
        Get context-specific instructions.
        
        Args:
            context: Basketball context type
            
        Returns:
            Context-specific instruction string
        """
        instructions = {
            BasketballContext.OFFENSIVE_POSSESSION: """
**OFFENSIVE POSSESSION FOCUS:**
- Track ball handler decisions and movements
- Identify screening actions and cuts
- Note spacing and player positioning
- Analyze shot selection and quality
- Record assists and hockey assists
            """,
            
            BasketballContext.DEFENSIVE_POSSESSION: """
**DEFENSIVE POSSESSION FOCUS:**
- Identify defensive scheme (man, zone, press)
- Track help defense rotations
- Note defensive communication and switches
- Record steals, blocks, and deflections
- Analyze defensive rebounding positioning
            """,
            
            BasketballContext.TRANSITION: """
**TRANSITION PLAY FOCUS:**
- Track speed of possession change
- Identify fast break opportunities
- Note trailer players and outlets
- Analyze transition defense setup
- Record quick scoring opportunities
            """,
            
            BasketballContext.FREE_THROW: """
**FREE THROW FOCUS:**
- Record shooter and result
- Note lane positioning
- Track rebound attempts
- Identify any lane violations
            """
        }
        
        return instructions.get(context, "")
    
    def enhance_training_data(self, training_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance training data with basketball-specific context.
        
        Args:
            training_data: Original training data dict
            
        Returns:
            Enhanced training data with basketball context
        """
        # Add basketball-specific metadata
        enhanced = training_data.copy()
        
        # Parse game context from the data
        if "context" not in enhanced:
            enhanced["context"] = {}
        
        # Add basketball-specific fields
        enhanced["context"]["sport"] = "basketball"
        enhanced["context"]["analysis_type"] = "multi_angle_annotation"
        enhanced["context"]["model_specialization"] = "gemini_2.5_pro_basketball"
        
        # Enhance the input prompt if present
        if "input_text" in enhanced:
            enhanced["input_text"] = self._enhance_input_prompt(enhanced["input_text"])
        
        return enhanced
    
    def _enhance_input_prompt(self, original_prompt: str) -> str:
        """
        Enhance an input prompt with basketball context.
        
        Args:
            original_prompt: Original prompt text
            
        Returns:
            Enhanced prompt with basketball context
        """
        # Check if prompt already has basketball context
        if "basketball" in original_prompt.lower():
            return original_prompt
        
        # Add basketball context prefix
        enhancement = (
            "As a basketball expert analyzing game footage, focus on:\n"
            "- Player positioning and movement\n"
            "- Shot selection and mechanics\n"
            "- Team strategy and ball movement\n"
            "- Critical game events and their impact\n\n"
        )
        
        return enhancement + original_prompt
    
    def format_training_example(
        self,
        video_uri: str,
        annotations: List[Dict[str, Any]],
        game_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a training example for Gemini 2.5 Pro fine-tuning.
        
        Args:
            video_uri: GCS URI of the video
            annotations: List of annotations for the video
            game_context: Optional game context (quarter, score, etc.)
            
        Returns:
            Formatted training example dict
        """
        # Build the prompt
        prompt = self.build_annotation_prompt(
            context=BasketballContext.FULL_GAME,
            game_phase=game_context.get("game_phase") if game_context else None
        )
        
        # Format the expected output
        output = {
            "plays": annotations,
            "total_plays": len(annotations),
            "video_uri": video_uri
        }
        
        if game_context:
            output["game_context"] = game_context
        
        return {
            "input_text": prompt,
            "output_text": self._format_annotations_as_text(annotations),
            "video_uri": video_uri,
            "context": game_context or {}
        }
    
    def _format_annotations_as_text(self, annotations: List[Dict[str, Any]]) -> str:
        """
        Format annotations as text output for training.
        
        Args:
            annotations: List of annotation dicts
            
        Returns:
            Formatted text representation
        """
        import json
        return json.dumps(annotations, indent=2)
    
    def get_basketball_event_types(self) -> List[str]:
        """
        Get the complete list of basketball event types.
        
        Returns:
            List of event type strings
        """
        return [
            # Scoring
            "FG_MAKE", "FG_MISS",
            "3PT_MAKE", "3PT_MISS",
            "FT_MAKE", "FT_MISS",
            
            # Ball Movement
            "ASSIST", "HOCKEY_ASSIST",
            "PASS", "TURNOVER",
            
            # Rebounds
            "REBOUND_OFFENSIVE", "REBOUND_DEFENSIVE",
            
            # Defense
            "STEAL", "BLOCK", "DEFLECTION",
            "DEFENSIVE_STOP",
            
            # Fouls
            "FOUL_PERSONAL", "FOUL_SHOOTING",
            "FOUL_OFFENSIVE", "FOUL_TECHNICAL",
            "FOUL_FLAGRANT",
            
            # Other
            "TIMEOUT", "SUBSTITUTION",
            "JUMP_BALL", "VIOLATION",
            
            # Advanced
            "SCREEN_ASSIST", "DRAWN_FOUL",
            "PUTBACK", "FASTBREAK_POINTS"
        ]
    
    def get_court_regions(self) -> List[str]:
        """
        Get the list of basketball court regions.
        
        Returns:
            List of court region strings
        """
        return [
            "paint",
            "key",
            "free_throw_line",
            "left_corner_three",
            "right_corner_three",
            "left_wing",
            "right_wing",
            "top_of_key",
            "left_baseline",
            "right_baseline",
            "midcourt",
            "backcourt"
        ]
    
    def get_shot_types(self) -> List[str]:
        """
        Get the list of basketball shot types.
        
        Returns:
            List of shot type strings
        """
        return [
            "layup",
            "dunk",
            "jump_shot",
            "three_pointer",
            "hook_shot",
            "fadeaway",
            "floater",
            "tip_in",
            "putback",
            "free_throw",
            "runner",
            "step_back",
            "pull_up",
            "catch_and_shoot"
        ]


# Global optimizer instance
_optimizer_instance: Optional[BasketballPromptOptimizer] = None


def get_prompt_optimizer() -> BasketballPromptOptimizer:
    """
    Get or create the global prompt optimizer instance.
    
    Returns:
        BasketballPromptOptimizer instance
    """
    global _optimizer_instance
    
    if _optimizer_instance is None:
        _optimizer_instance = BasketballPromptOptimizer()
    
    return _optimizer_instance

