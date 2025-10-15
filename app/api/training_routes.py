"""
Training API routes for basketball annotation.
Supports both local development and cloud production modes.
"""

import os
import uuid
import subprocess
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])

# In-memory job tracking (TODO: Replace with Redis or database in production)
training_jobs: Dict[str, Dict] = {}

# Models
class TrainingRequest(BaseModel):
    game_id: str
    force_retrain: bool = False

class TrainingResponse(BaseModel):
    job_id: str
    message: str
    mode: str  # "local" or "cloud"

class TrainingJobStatus(BaseModel):
    job_id: str
    status: str  # "queued", "running", "completed", "failed"
    message: str
    game_id: str
    mode: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 4
    current_step: str = ""
    progress_percentage: float = 0.0
    video_progress: Optional[Dict] = None  # {"current": 10, "total": 100, "percentage": 10.0}

# Progress tracking helper
def update_job_progress(job_id: str, step: str, step_num: int, total_steps: int, message: str, video_progress: Dict = None):
    """Update job progress with detailed tracking."""
    progress_percentage = (step_num / total_steps) * 100
    training_jobs[job_id].update({
        "current_step": step,
        "steps_completed": step_num,
        "progress_percentage": progress_percentage,
        "message": f"[{progress_percentage:.1f}%] {message}",
        "video_progress": video_progress
    })
    logger.info(f"[{job_id}] Step {step_num}/{total_steps}: {message}")
    if video_progress:
        logger.info(f"[{job_id}] Video Progress: {video_progress['current']}/{video_progress['total']} ({video_progress['percentage']:.1f}%)")

# Enhanced subprocess execution with progress monitoring
async def run_script_with_progress(job_id: str, script_args: list, cwd: Path, step_name: str):
    """Run a script and monitor its output for progress indicators."""
    process = await asyncio.create_subprocess_exec(
        *script_args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    output_lines = []
    while True:
        line = await process.stdout.readline()
        if not line:
            break
            
        line = line.decode('utf-8').strip()
        output_lines.append(line)
        
        # Parse progress from output (looking for common progress patterns)
        if "%" in line or "progress" in line.lower() or "processing" in line.lower():
            training_jobs[job_id]["message"] = f"{step_name}: {line}"
            logger.info(f"[{job_id}] {step_name}: {line}")
        
        # Look for video processing progress
        if "clips" in line.lower() and ("/" in line or "of" in line):
            # Try to extract numbers like "Processing 5/20 clips" or "5 of 20"
            import re
            progress_match = re.search(r'(\d+)[\s/]+(?:of\s+)?(\d+)', line)
            if progress_match:
                current, total = map(int, progress_match.groups())
                video_progress = {
                    "current": current,
                    "total": total,
                    "percentage": (current / total) * 100
                }
                training_jobs[job_id]["video_progress"] = video_progress
                logger.info(f"[{job_id}] Video Progress: {current}/{total} ({video_progress['percentage']:.1f}%)")
    
    await process.wait()
    return process.returncode, "\n".join(output_lines)

# Local training execution
async def run_local_training(job_id: str, game_id: str):
    """Run training pipeline locally using Python scripts with detailed progress tracking."""
    try:
        training_jobs[job_id]["status"] = "running"
        training_jobs[job_id]["started_at"] = datetime.now()
        update_job_progress(job_id, "export", 0, 4, "Starting local training pipeline")
        
        project_root = Path(__file__).parent.parent.parent
        
        # Step 1: Export plays
        update_job_progress(job_id, "export", 0, 4, f"Exporting plays from database for game {game_id}")
        
        returncode, output = await run_script_with_progress(
            job_id,
            ["python", "scripts/training/export_plays.py", "--game-id", game_id],
            project_root,
            "Export Plays"
        )
        
        if returncode != 0:
            raise Exception(f"Export failed: {output}")
        
        update_job_progress(job_id, "export", 1, 4, "✅ Plays exported successfully")
        
        # Step 2: Extract clips (find the most recent plays file)
        output_dir = project_root / "output" / "training_data"
        plays_files = list(output_dir.glob("all_plays_*.json"))
        if not plays_files:
            raise Exception("No plays files found after export")
        
        plays_file = max(plays_files, key=lambda x: x.stat().st_mtime)
        update_job_progress(job_id, "clips", 1, 4, f"🎬 Extracting video clips from {plays_file.name}")
        
        returncode, output = await run_script_with_progress(
            job_id,
            ["python", "scripts/training/extract_clips.py", str(plays_file)],
            project_root,
            "Extract Clips"
        )
        
        if returncode != 0:
            raise Exception(f"Clip extraction failed: {output}")
        
        update_job_progress(job_id, "clips", 2, 4, "✅ Video clips extracted successfully")
        
        # Step 3: Format training data
        update_job_progress(job_id, "format", 2, 4, f"📝 Formatting training data for game {game_id}")
        
        returncode, output = await run_script_with_progress(
            job_id,
            ["python", "scripts/training/format_training_data.py", game_id],
            project_root,
            "Format Data"
        )
        
        if returncode != 0:
            raise Exception(f"Data formatting failed: {output}")
        
        update_job_progress(job_id, "format", 3, 4, "✅ Training data formatted successfully")
        
        # Step 4: Train model
        # Find training files (they might have timestamps or game IDs)
        training_files = list(output_dir.glob("training_*.jsonl"))
        validation_files = list(output_dir.glob("validation_*.jsonl"))
        
        if not training_files or not validation_files:
            raise Exception("Training/validation files not found after formatting")
        
        training_file = max(training_files, key=lambda x: x.stat().st_mtime)
        validation_file = max(validation_files, key=lambda x: x.stat().st_mtime)
        
        update_job_progress(job_id, "train", 3, 4, f"🤖 Training model with Vertex AI for game {game_id}")
        
        returncode, output = await run_script_with_progress(
            job_id,
            ["python", "scripts/training/train_model.py", 
             "--training-data", str(training_file),
             "--validation-data", str(validation_file)],
            project_root,
            "Train Model"
        )
        
        if returncode != 0:
            raise Exception(f"Model training failed: {output}")
        
        # Success
        training_jobs[job_id]["status"] = "completed"
        update_job_progress(job_id, "completed", 4, 4, f"🎉 Training pipeline completed successfully for game {game_id}")
        training_jobs[job_id]["completed_at"] = datetime.now()
        
        logger.info(f"[{job_id}] Training completed successfully for game {game_id}")
        
    except Exception as e:
        training_jobs[job_id]["status"] = "failed"
        training_jobs[job_id]["message"] = f"Training failed: {str(e)}"
        training_jobs[job_id]["error"] = str(e)
        training_jobs[job_id]["completed_at"] = datetime.now()
        logger.error(f"[{job_id}] Training failed: {e}")

# Cloud training execution
async def run_cloud_training(job_id: str, game_id: str):
    """Run training pipeline using Google Cloud Workflows."""
    try:
        training_jobs[job_id]["status"] = "running"
        training_jobs[job_id]["started_at"] = datetime.now()
        training_jobs[job_id]["message"] = "Triggering Cloud Workflows training pipeline"
        
        logger.info(f"[{job_id}] Triggering cloud training for game {game_id}")
        
        # Execute gcloud workflows run command
        result = await asyncio.create_subprocess_exec(
            "gcloud", "workflows", "run", settings.TRAINING_WORKFLOW_NAME,
            "--data", f'{{"game_id": "{game_id}"}}',
            "--location", settings.TRAINING_WORKFLOW_LOCATION,
            "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            raise Exception(f"Workflow execution failed: {stderr.decode()}")
        
        # Parse workflow execution ID from output
        import json
        workflow_result = json.loads(stdout.decode())
        execution_id = workflow_result.get("name", "").split("/")[-1]
        
        training_jobs[job_id]["status"] = "completed"
        training_jobs[job_id]["message"] = f"Cloud workflow triggered successfully (execution: {execution_id})"
        training_jobs[job_id]["steps_completed"] = 4
        training_jobs[job_id]["completed_at"] = datetime.now()
        
        logger.info(f"[{job_id}] Cloud training triggered successfully")
        
    except Exception as e:
        training_jobs[job_id]["status"] = "failed"
        training_jobs[job_id]["message"] = f"Cloud training failed: {str(e)}"
        training_jobs[job_id]["error"] = str(e)
        training_jobs[job_id]["completed_at"] = datetime.now()
        logger.error(f"[{job_id}] Cloud training failed: {e}")

@router.post("/pipeline", response_model=TrainingResponse)
async def start_training_pipeline(
    request: TrainingRequest,
    background_tasks: BackgroundTasks
):
    """
    Start the complete training pipeline for a game.
    Mode depends on TRAINING_MODE setting (local/cloud).
    """
    try:
        job_id = f"train-{uuid.uuid4().hex[:8]}"
        mode = settings.TRAINING_MODE
        
        # Initialize job tracking
        training_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "message": f"Training job queued (mode: {mode})",
            "game_id": request.game_id,
            "mode": mode,
            "steps_completed": 0,
            "total_steps": 4,
            "current_step": "queued",
            "progress_percentage": 0.0,
            "video_progress": None,
            "started_at": None,
            "completed_at": None,
            "error": None
        }
        
        # Execute based on mode
        if mode == "local":
            background_tasks.add_task(run_local_training, job_id, request.game_id)
        elif mode == "cloud":
            background_tasks.add_task(run_cloud_training, job_id, request.game_id)
        else:
            raise ValueError(f"Invalid training mode: {mode}")
        
        logger.info(f"✓ Started training job {job_id} for game {request.game_id} (mode: {mode})")
        
        return TrainingResponse(
            job_id=job_id,
            message=f"Training pipeline started in {mode} mode",
            mode=mode
        )
        
    except Exception as e:
        logger.error(f"Error starting training pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{job_id}", response_model=TrainingJobStatus)
async def get_training_status(job_id: str):
    """Get status of a training job."""
    if job_id not in training_jobs:
        raise HTTPException(status_code=404, detail="Training job not found")
    
    job_data = training_jobs[job_id]
    return TrainingJobStatus(**job_data)

@router.get("/jobs")
async def list_training_jobs():
    """List all training jobs."""
    return {"jobs": list(training_jobs.values())}

@router.post("/export/{game_id}")
async def export_plays_only(game_id: str):
    """Export plays for a specific game (utility endpoint)."""
    try:
        project_root = Path(__file__).parent.parent.parent
        
        result = await asyncio.create_subprocess_exec(
            "python", "scripts/training/export_plays.py", "--game-id", game_id,
            cwd=project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        
        if result.returncode != 0:
            raise Exception(f"Export failed: {stderr.decode()}")
        
        return {"message": f"Plays exported successfully for game {game_id}", "game_id": game_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/{job_id}")
async def get_training_progress(job_id: str):
    """Get real-time progress of a training job with video processing details."""
    if job_id not in training_jobs:
        raise HTTPException(status_code=404, detail="Training job not found")
    
    job_data = training_jobs[job_id]
    
    # Enhanced progress response
    progress_info = {
        "job_id": job_id,
        "game_id": job_data["game_id"],
        "status": job_data["status"],
        "current_step": job_data.get("current_step", "unknown"),
        "steps_completed": job_data["steps_completed"],
        "total_steps": job_data["total_steps"],
        "progress_percentage": job_data.get("progress_percentage", 0.0),
        "message": job_data["message"],
        "video_progress": job_data.get("video_progress"),
        "started_at": job_data["started_at"],
        "estimated_time_remaining": None
    }
    
    # Calculate estimated time remaining
    if job_data["started_at"] and job_data["status"] == "running":
        elapsed = (datetime.now() - job_data["started_at"]).total_seconds()
        if job_data.get("progress_percentage", 0) > 0:
            total_estimated = elapsed * (100 / job_data["progress_percentage"])
            remaining = max(0, total_estimated - elapsed)
            progress_info["estimated_time_remaining"] = f"{remaining/60:.1f} minutes"
    
    return progress_info

@router.get("/config")
async def get_training_config():
    """Get current training configuration."""
    return {
        "training_mode": settings.TRAINING_MODE,
        "environment": settings.ENVIRONMENT,
        "workflow_name": settings.TRAINING_WORKFLOW_NAME,
        "workflow_location": settings.TRAINING_WORKFLOW_LOCATION,
        "gcp_project": settings.GCP_PROJECT_ID
    }