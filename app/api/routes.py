"""
API routes for basketball annotation.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict
import logging
import uuid
from datetime import datetime

from app.models.schemas import (
    AnnotationRequest,
    AnnotationResponse,
    JobStatusResponse,
    PlaysResponse,
    JobStatus,
    CameraAngle
)
from app.core.database import get_supabase
from app.core.storage import get_storage
from app.services.plays_service import PlaysService

logger = logging.getLogger(__name__)

router = APIRouter()

# Import training routes
from app.api.training_routes import router as training_router
router.include_router(training_router)

# In-memory job tracking (TODO: Replace with Redis or database in production)
jobs: Dict[str, Dict] = {}


async def process_annotation_job(
    job_id: str,
    game_id: str,
    angle: CameraAngle,
    force_reprocess: bool
):
    """
    Background task to process annotation job.
    
    Args:
        job_id: Job ID
        game_id: Game UUID
        angle: Camera angle
        force_reprocess: Whether to force reprocessing
    """
    try:
        # Update job status
        jobs[job_id]["status"] = JobStatus.PROCESSING
        jobs[job_id]["message"] = "Starting annotation workflow..."
        jobs[job_id]["started_at"] = datetime.now()
        
        # Initialize services
        from app.services.orchestrator_service import AnnotationOrchestrator
        
        supabase = get_supabase()
        storage = get_storage()
        
        orchestrator = AnnotationOrchestrator(supabase, storage)
        
        # Run complete annotation workflow
        jobs[job_id]["message"] = "Processing video with AI model..."
        created_plays = await orchestrator.annotate_game(
            game_id,
            angle,
            force_reprocess
        )
        
        # Complete
        jobs[job_id]["status"] = JobStatus.COMPLETED
        jobs[job_id]["message"] = "Annotation completed successfully"
        jobs[job_id]["plays_created"] = len(created_plays)
        jobs[job_id]["completed_at"] = datetime.now()
        
    except Exception as e:
        logger.error(f"Annotation job {job_id} failed: {e}")
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["message"] = "Annotation failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.now()


@router.post("/annotate", response_model=AnnotationResponse)
async def annotate_video(
    request: AnnotationRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger annotation for a game video.
    
    Args:
        request: Annotation request
        background_tasks: FastAPI background tasks
        
    Returns:
        Annotation response with job ID
    """
    try:
        # Generate job ID
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        
        # Initialize job tracking
        jobs[job_id] = {
            "job_id": job_id,
            "status": JobStatus.QUEUED,
            "message": "Job queued",
            "game_id": request.game_id,
            "angle": request.angle,
            "plays_created": 0,
            "error": None,
            "started_at": None,
            "completed_at": None
        }
        
        # Add background task
        background_tasks.add_task(
            process_annotation_job,
            job_id,
            request.game_id,
            request.angle,
            request.force_reprocess
        )
        
        logger.info(f"✓ Created annotation job: {job_id}")
        
        return AnnotationResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            message="Annotation job started"
        )
        
    except Exception as e:
        logger.error(f"Error creating annotation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get status of an annotation job.
    
    Args:
        job_id: Job ID
        
    Returns:
        Job status
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    
    return JobStatusResponse(**job_data)


@router.get("/plays/{game_id}", response_model=PlaysResponse)
async def get_plays(
    game_id: str,
    angle: CameraAngle,
    supabase = Depends(get_supabase)
):
    """
    Get all plays for a game.
    
    Args:
        game_id: Game UUID
        angle: Camera angle
        supabase: Supabase client
        
    Returns:
        Plays response
    """
    try:
        plays_service = PlaysService(supabase)
        plays = await plays_service.get_plays_for_game(game_id, angle)
        
        return PlaysResponse(
            game_id=game_id,
            angle=angle,
            total_plays=len(plays),
            plays=plays
        )
        
    except Exception as e:
        logger.error(f"Error fetching plays: {e}")
        raise HTTPException(status_code=500, detail=str(e))

