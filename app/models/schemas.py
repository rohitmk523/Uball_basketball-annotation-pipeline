"""
Pydantic models for request/response validation and data structures.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class CameraAngle(str, Enum):
    """Camera angle options."""
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CENTER = "CENTER"
    BASELINE = "BASELINE"


class EventLabel(str, Enum):
    """Basketball event types."""
    FG_MAKE = "FG_MAKE"
    FG_MISS = "FG_MISS"
    THREE_PT_MAKE = "3PT_MAKE"
    THREE_PT_MISS = "3PT_MISS"
    FREE_THROW_MAKE = "FREE_THROW_MAKE"
    FREE_THROW_MISS = "FREE_THROW_MISS"
    ASSIST = "ASSIST"
    REBOUND = "REBOUND"
    OFFENSIVE_REBOUND = "OFFENSIVE_REBOUND"
    DEFENSIVE_REBOUND = "DEFENSIVE_REBOUND"
    STEAL = "STEAL"
    BLOCK = "BLOCK"
    TURNOVER = "TURNOVER"
    FOUL = "FOUL"
    TIMEOUT = "TIMEOUT"
    SUBSTITUTION = "SUBSTITUTION"


class JobStatus(str, Enum):
    """Job processing status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Event Models ====================

class EventBase(BaseModel):
    """Base event model."""
    label: EventLabel
    playerA: Optional[str] = None
    playerAId: Optional[str] = None
    playerB: Optional[str] = None
    playerBId: Optional[str] = None


class Event(EventBase):
    """Event with all fields."""
    pass


# ==================== Play Models ====================

class PlayBase(BaseModel):
    """Base play model."""
    game_id: str
    angle: CameraAngle
    timestamp_seconds: float
    classification: EventLabel
    note: str
    player_a: Optional[str] = None
    player_a_id: Optional[str] = None
    player_b: Optional[str] = None
    player_b_id: Optional[str] = None
    events: List[Event] = []


class PlayCreate(PlayBase):
    """Play creation model."""
    pass


class Play(PlayBase):
    """Play model with database fields."""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Video Metadata Models ====================

class VideoMetadata(BaseModel):
    """Video metadata from Supabase."""
    id: str
    game_id: str
    angle: CameraAngle
    filename: str
    gcs_uri: str
    duration_seconds: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== AI Model Response Models ====================

class VertexAIAnnotation(BaseModel):
    """Raw annotation from Vertex AI model."""
    timestamp_seconds: float
    classification: str
    note: str
    player_a: Optional[str] = None
    player_a_id: Optional[str] = None
    player_b: Optional[str] = None
    player_b_id: Optional[str] = None
    events: List[Dict[str, Any]] = []


# ==================== API Request/Response Models ====================

class AnnotationRequest(BaseModel):
    """Request to annotate a game video."""
    game_id: str = Field(..., description="Game UUID")
    angle: CameraAngle = Field(..., description="Camera angle")
    force_reprocess: bool = Field(default=False, description="Force reprocessing if plays already exist")


class AnnotationResponse(BaseModel):
    """Response for annotation request."""
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    """Job status response."""
    job_id: str
    status: JobStatus
    message: str
    plays_created: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PlaysResponse(BaseModel):
    """Response containing plays for a game."""
    game_id: str
    angle: CameraAngle
    total_plays: int
    plays: List[Play]


# ==================== Player Models ====================

class Player(BaseModel):
    """Player model."""
    id: str
    name: Optional[str] = None
    jersey_number: Optional[int] = None
    jersey_color: Optional[str] = None
    team_id: Optional[str] = None

    class Config:
        from_attributes = True

