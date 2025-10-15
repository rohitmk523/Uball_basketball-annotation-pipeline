#!/usr/bin/env python3
"""
Test script for training API endpoints with progress tracking.
"""

import requests
import time
import json

# Configuration
BASE_URL = "http://localhost:8000/api/training"
GAME_ID = "a3c9c041-6762-450a-8444-413767bb6428"

def test_training_pipeline():
    """Test the complete training pipeline with progress monitoring."""
    print("🚀 Testing Training Pipeline API")
    print("=" * 50)
    
    # 1. Check configuration
    print("📋 Checking training configuration...")
    response = requests.get(f"{BASE_URL}/config")
    if response.status_code == 200:
        config = response.json()
        print(f"✅ Training Mode: {config['training_mode']}")
        print(f"✅ Environment: {config['environment']}")
    else:
        print(f"❌ Config check failed: {response.status_code}")
        return
    
    # 2. Start training pipeline
    print(f"\n🎯 Starting training pipeline for game: {GAME_ID}")
    response = requests.post(f"{BASE_URL}/pipeline", json={
        "game_id": GAME_ID,
        "force_retrain": False
    })
    
    if response.status_code != 200:
        print(f"❌ Failed to start training: {response.status_code} - {response.text}")
        return
    
    result = response.json()
    job_id = result["job_id"]
    print(f"✅ Training job started: {job_id}")
    print(f"✅ Mode: {result['mode']}")
    
    # 3. Monitor progress
    print(f"\n📊 Monitoring progress for job: {job_id}")
    print("-" * 50)
    
    while True:
        # Get detailed progress
        response = requests.get(f"{BASE_URL}/progress/{job_id}")
        if response.status_code != 200:
            print(f"❌ Failed to get progress: {response.status_code}")
            break
        
        progress = response.json()
        
        # Display progress bar
        percentage = progress["progress_percentage"]
        steps = progress["steps_completed"]
        total_steps = progress["total_steps"]
        current_step = progress["current_step"]
        
        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * percentage / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        print(f"\r[{bar}] {percentage:5.1f}% | Step {steps}/{total_steps} ({current_step})", end="")
        
        # Show video progress if available
        if progress.get("video_progress"):
            video_prog = progress["video_progress"]
            print(f"\n📹 Video: {video_prog['current']}/{video_prog['total']} ({video_prog['percentage']:.1f}%)")
        
        # Show message
        print(f"\n💬 {progress['message']}")
        
        # Show estimated time remaining
        if progress.get("estimated_time_remaining"):
            print(f"⏱️  ETA: {progress['estimated_time_remaining']}")
        
        # Check if completed
        if progress["status"] in ["completed", "failed"]:
            print(f"\n🏁 Training {progress['status'].upper()}")
            if progress["status"] == "completed":
                print("🎉 Training pipeline completed successfully!")
            else:
                print(f"❌ Training failed: {progress.get('error', 'Unknown error')}")
            break
        
        print("-" * 50)
        time.sleep(5)  # Check every 5 seconds
    
    # 4. Final status
    print(f"\n📋 Final Status for job: {job_id}")
    response = requests.get(f"{BASE_URL}/status/{job_id}")
    if response.status_code == 200:
        status = response.json()
        print(f"Status: {status['status']}")
        print(f"Game ID: {status['game_id']}")
        print(f"Mode: {status['mode']}")
        if status.get("started_at"):
            print(f"Started: {status['started_at']}")
        if status.get("completed_at"):
            print(f"Completed: {status['completed_at']}")

def test_export_only():
    """Test the export-only endpoint."""
    print(f"\n🔄 Testing export-only for game: {GAME_ID}")
    response = requests.post(f"{BASE_URL}/export/{GAME_ID}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ {result['message']}")
    else:
        print(f"❌ Export failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    print("🏀 Basketball Training API Test")
    print("Make sure FastAPI server is running on http://localhost:8000")
    print("Press Ctrl+C to stop monitoring")
    print()
    
    try:
        # Test export only first (quicker)
        test_export_only()
        
        # Then test full pipeline
        input("\nPress Enter to start full training pipeline test...")
        test_training_pipeline()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Make sure FastAPI server is running on http://localhost:8000")
        print("Start server with: python -m uvicorn app.main:app --reload --port 8000")