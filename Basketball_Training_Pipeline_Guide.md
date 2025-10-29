# Basketball Training Pipeline Guide

A comprehensive guide to the UBALL basketball annotation training pipeline using Vertex AI and Google Cloud Platform.

## Table of Contents

1. [Overview](#overview)
2. [JSONL Format Structure](#jsonl-format-structure)
3. [Training Prompts](#training-prompts)
4. [Training Process](#training-process)
5. [Testing Strategy](#testing-strategy)
6. [5-Game Training Plan](#5-game-training-plan)
7. [Resource Optimization](#resource-optimization)
8. [Troubleshooting](#troubleshooting)

## Overview

The basketball training pipeline is designed to progressively train AI models for automatic basketball game annotation using Vertex AI. The system takes manually annotated plays from your custom annotation tool and trains models to replicate the annotation process automatically.

### Custom Annotation Workflow Integration

The pipeline integrates with your existing manual annotation process:

1. **Manual Annotation**: Your annotators use the custom annotation tool to mark plays with start/end timestamps
2. **Clip Extraction**: The pipeline extracts video clips based on the timestamp data
3. **Training Data Creation**: Clips are formatted into Vertex AI training examples
4. **Model Training**: Fine-tune models to replicate the manual annotation process
5. **Automation**: Trained models can annotate new games automatically

### Key Components

- **Extract Clips Job**: Processes game videos and extracts training clips
- **Training Data Formatter**: Converts clips into Vertex AI-compatible JSONL format
- **Model Trainer**: Manages Vertex AI fine-tuning jobs
- **Workflow Orchestrator**: Coordinates the entire pipeline via Cloud Workflows

### Architecture

```
Game Videos (GCS) → Extract Clips → Format JSONL → Vertex AI Training → Deploy Model
```

## JSONL Format Structure

The training data uses Vertex AI's conversation format with video inputs. Each example contains user input (video + prompt) and model response (structured basketball annotation).

### Single Training Example Structure

```jsonl
{
  "contents": [
    {
      "role": "user",
      "parts": [
        {
          "fileData": {
            "fileUri": "gs://uball-training-data/games/{game_id}/clips/{play_id}_{angle}.mp4",
            "mimeType": "video/mp4"
          }
        },
        {
          "text": "⚠️ CRITICAL: This is UBALL basketball with a 4-POINT LINE..."
        }
      ]
    },
    {
      "role": "model",
      "parts": [
        {
          "text": "[{\"timestamp_seconds\": 45.2, \"classification\": \"FG_MAKE\", ...}]"
        }
      ]
    }
  ],
  "generationConfig": {
    "mediaResolution": "MEDIA_RESOLUTION_MEDIUM"
  }
}
```

### Expected Model Response Format

The model should return a JSON array with play annotations:

```json
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
```

### Event Types Supported

- **Shooting**: `FG_MAKE`, `FG_MISS`, `3PT_MAKE`, `3PT_MISS`
- **Free Throws**: `FREE_THROW_MAKE`, `FREE_THROW_MISS`
- **Gameplay**: `ASSIST`, `REBOUND`, `STEAL`, `BLOCK`, `TURNOVER`, `FOUL`
- **Administrative**: `TIMEOUT`, `SUBSTITUTION`

### Camera Angle Mapping

Each play is captured from multiple angles for better training context:

```python
angle_mapping = {
    "LEFT": ["FAR_LEFT", "NEAR_RIGHT"],   # Left side plays
    "RIGHT": ["FAR_RIGHT", "NEAR_LEFT"]   # Right side plays
}
```

- **Far angles**: Wide court view, team formations
- **Near angles**: Close-up player details, jersey numbers

## Training Prompts

### Primary Training Prompt

Located in `/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/jobs/extract-clips/extract_clips_job.py` (lines 486-503):

```python
prompt_text = f"""Analyze this basketball game video from {angle} camera angle and identify the play with its events.

This is a {angle} camera view that provides {'wide court view and team formation context' if 'FAR' in angle else 'close-up details of player numbers and jerseys'}.

For the play, provide:
1. timestamp_seconds: The time in the video when the play occurs (number)
2. classification: The primary event type (FG_MAKE, FG_MISS, 3PT_MAKE, 3PT_MISS, FOUL, REBOUND, ASSIST, etc.)
3. note: A detailed description of what happened (string)
4. player_a: The primary player involved (format: "Player #X (Color Team)")
5. player_b: Secondary player if applicable (format: "Player #X (Color Team)")
6. events: Array of all events in the play, each with:
   - label: Event type (same options as classification)
   - playerA: Player identifier (format: "Player #X (Color Team)")
   - playerB: Secondary player if applicable

Return a JSON array with the single play. Be precise with timestamps and identify all basketball events."""
```

### Key Prompt Features

1. **Camera-Specific Instructions**: Different guidance for far vs near angles
2. **Structured Output**: JSON format with specific field requirements
3. **Player Identification**: Standardized format for player references
4. **Event Classification**: Standard basketball events (FG, 3PT, fouls, etc.)
5. **Timestamp Precision**: Exact timing for play events

### Multi-Angle Prompt (Alternative)

Found in `/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/app/services/vertex_ai_service.py`:

```python
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
6. events: Array of all events in the play

Return a JSON array of plays. Use information from all provided camera angles to accurately identify player numbers and team colors. Be precise with timestamps and identify all basketball events."""
```

## Training Process

### 1. Data Preparation Pipeline

#### Extract Clips Job (`/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/jobs/extract-clips/extract_clips_job.py`)

```python
class ClipExtractorJob:
    def __init__(self, game_id: str, plays_file_gcs: str, training_bucket: str):
        # Initialize with game data and GCS paths
        
    def extract_all_clips(self):
        # 1. Validate video files exist
        # 2. Process plays in parallel
        # 3. Extract clips using ffmpeg
        # 4. Upload to GCS training bucket
        # 5. Create JSONL training files
```

**Key Steps:**
1. Downloads plays data from GCS
2. Validates required video files exist
3. Extracts clips for multiple camera angles
4. Creates 80/20 train/validation split
5. Generates Vertex AI-compatible JSONL files

#### Directory Structure

```
gs://uball-training-data/
├── games/{game_id}/
│   ├── clips/
│   │   ├── {play_id}_FAR_LEFT.mp4
│   │   ├── {play_id}_NEAR_RIGHT.mp4
│   │   └── ...
│   ├── metadata.json
│   ├── plays.json
│   ├── video_training_{game_id}_{timestamp}.jsonl
│   └── video_validation_{game_id}_{timestamp}.jsonl
```

### 2. Model Training Job

#### Configuration

```python
# Training hyperparameters
{
    "epochCount": "5",
    "learningRateMultiplier": "1.0", 
    "adapterSize": "ADAPTER_SIZE_ONE"
}

# Base model
base_model = "gemini-2.5-flash"  # or "gemini-1.5-flash-001"
```

#### Training Job Creation

```python
tuning_job = TuningJob(
    display_name=f"basketball-flash-cumulative-{num_games}-games-{timestamp}",
    base_model=base_model,
    supervised_tuning_spec=SupervisedTuningSpec(
        training_dataset_uri="gs://uball-training-data/combined_training.jsonl",
        validation_dataset_uri="gs://uball-training-data/combined_validation.jsonl",
        hyper_parameters=hyperparameters
    )
)
```

### 3. Workflow Orchestration

The training pipeline is managed by Cloud Workflows (`/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/workflows/basketball-training-pipeline.yaml`):

```yaml
main:
  steps:
    - combine_files: # Merge JSONL from multiple games
    - create_tuning_job: # Start Vertex AI training
    - wait_tuning: # Monitor completion  
    - return_result: # Provide training summary
```

**Pipeline Flow:**
1. **Initialization**: Set up execution environment
2. **File Combination**: Merge training data from multiple games
3. **Tuning Job Creation**: Submit to Vertex AI
4. **Monitoring**: Track progress and handle errors
5. **Completion**: Return training results

### 4. Training Modes

#### Local Development Mode
- Runs scripts directly in FastAPI process
- Single game training
- Good for testing and development

#### Cloud Production Mode  
- Uses Cloud Run Jobs for heavy processing
- Supports multi-game training
- Scales automatically

### 5. Progress Monitoring

```python
# Monitor tuning job status
tuning_status_check = {
    "JOB_STATE_SUCCEEDED": "Training completed successfully",
    "JOB_STATE_FAILED": "Training failed", 
    "JOB_STATE_CANCELLED": "Training was cancelled",
    "ACTIVE/RUNNING": "Training in progress"
}
```

## Testing Strategy

### 1. Pre-Training Validation

#### Quick Check Script (`/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/scripts/validation/quick_check.py`)

```python
def quick_validate():
    # 1. Environment variables check
    # 2. GCP authentication verification  
    # 3. Vertex AI API access test
    # 4. Workflow deployment check
    # 5. Storage bucket access validation
```

**Run before training:**
```bash
python scripts/validation/quick_check.py
```

#### Comprehensive Validation (`/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/scripts/validation/validate_workflow_params.py`)

```python
class WorkflowValidator:
    def run_validation(self):
        # Environment validation
        # GCP authentication check
        # API format validation
        # Workflow syntax check
        # Storage structure validation
        # Current models/endpoints check
```

**Validation checklist:**
- ✅ Environment variables configured
- ✅ GCP authentication working
- ✅ Vertex AI API accessible
- ✅ Workflow syntax valid
- ✅ Storage buckets accessible
- ✅ Required directories exist

### 2. Training Data Quality Checks

#### Video Validation
```python
def _validate_required_videos(self):
    # Check all required video files exist
    # Verify file sizes > 0
    # Validate camera angles available
    # Report missing files
```

#### JSONL Format Validation
```python
def _create_jsonl_examples(self, plays: List[Dict], dataset_type: str):
    # Validate play data structure
    # Check required fields present
    # Verify video URIs accessible
    # Ensure proper train/validation split
```

### 3. Training Progress Monitoring

#### Real-time Status Tracking
```python
async def monitor_basketball_workflow(job_id: str, execution_id: str):
    # Poll workflow status every 30 seconds
    # Extract current step information
    # Update progress percentage
    # Handle timeout (24 hours max)
```

#### Progress Indicators
- **Step 1**: Export plays from database
- **Step 2**: Extract video clips (with clip count progress)
- **Step 3**: Format training data
- **Step 4**: Train model with Vertex AI

### 4. Post-Training Validation

#### Model Quality Checks
1. **Training Metrics**: Check loss, accuracy from Vertex AI
2. **Validation Performance**: Monitor validation dataset results
3. **Endpoint Deployment**: Verify model deploys successfully
4. **API Response Testing**: Test inference with sample videos

#### Expected Training Times
- **Estimated Duration**: 4-12 hours depending on data size
- **Cost Estimate**: $50-150 per training job
- **Monitoring Window**: 24 hours with 30-second polling

### 5. Error Handling

#### Common Issues & Solutions

**Video File Missing:**
```
Error: Missing required video files
Solution: Check video paths in gs://uball-videos-production/Games/{game_id}/
```

**JSONL Format Error:**
```
Error: Invalid JSONL structure
Solution: Validate play data schema before training
```

**Training Job Failure:**
```
Error: Vertex AI training failed
Solution: Check training data size, format, and quotas
```

## 5-Game Training Plan

### Strategy Overview

Progressive training approach that builds model knowledge incrementally:

1. **Game 1**: Foundation training with base model
2. **Game 2**: Add new scenarios and edge cases  
3. **Game 3**: Improve player identification accuracy
4. **Game 4**: Enhance multi-angle understanding
5. **Game 5**: Refine complex play recognition

### Step-by-Step Execution

#### Phase 1: Single Game Training (Game 1)

```bash
# 1. Start with baseline game
gcloud workflows run basketball-training-pipeline \
  --data='{"game_ids": ["game_001"]}' \
  --location=us-central1
```

**Expected Outcomes:**
- Model learns basic basketball events
- Establishes player identification patterns
- Creates first fine-tuned checkpoint

**Validation:**
```bash
# Test model with sample clips
curl -X POST "https://your-api-endpoint/annotate" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test_game", "angle": "LEFT"}'
```

#### Phase 2: Incremental Training (Games 2-3)

```bash
# 2. Add second game for cumulative training
gcloud workflows run basketball-training-pipeline \
  --data='{"game_ids": ["game_001", "game_002"]}' \
  --location=us-central1

# 3. Continue with third game
gcloud workflows run basketball-training-pipeline \
  --data='{"game_ids": ["game_001", "game_002", "game_003"]}' \
  --location=us-central1
```

**Focus Areas:**
- **Game 2**: Different team colors, playing styles
- **Game 3**: Various camera angles, lighting conditions

**Quality Metrics:**
- Player identification accuracy > 85%
- Event classification precision > 90%
- Response format compliance 100%

#### Phase 3: Advanced Training (Games 4-5)

```bash
# 4. Four-game cumulative training
gcloud workflows run basketball-training-pipeline \
  --data='{"game_ids": ["game_001", "game_002", "game_003", "game_004"]}' \
  --location=us-central1

# 5. Five-game comprehensive training
gcloud workflows run basketball-training-pipeline \
  --data='{"game_ids": ["game_001", "game_002", "game_003", "game_004", "game_005"]}' \
  --location=us-central1
```

**Advanced Features:**
- **Game 4**: Complex plays, fast breaks, defensive strategies
- **Game 5**: 4-point shots, unusual situations, referee calls

### Training Data Organization

#### Game Selection Criteria

1. **Diversity**: Different teams, venues, lighting
2. **Quality**: Clear video, good annotations
3. **Coverage**: All court positions, camera angles
4. **Events**: Comprehensive event type coverage

#### Expected Data Volumes

| Phase | Games | Total Clips | Training Examples | Est. Training Time |
|-------|-------|-------------|-------------------|-------------------|
| 1     | 1     | ~200        | ~400             | 2-4 hours        |
| 2     | 2     | ~400        | ~800             | 4-6 hours        |
| 3     | 3     | ~600        | ~1,200           | 6-8 hours        |
| 4     | 4     | ~800        | ~1,600           | 8-10 hours       |
| 5     | 5     | ~1,000      | ~2,000           | 10-12 hours      |

### Performance Tracking

#### Key Metrics to Monitor

```python
# Model performance indicators
performance_metrics = {
    "training_loss": "< 0.1",
    "validation_accuracy": "> 92%", 
    "inference_speed": "< 30s per video",
    "response_format_compliance": "100%",
    "player_id_accuracy": "> 90%",
    "event_classification_f1": "> 0.88"
}
```

#### Quality Gates

**After Each Game:**
1. Run validation dataset through model
2. Check response format compliance
3. Verify player identification accuracy
4. Test event classification precision
5. Validate 4-point shot recognition

**Example Validation Script:**
```python
def validate_model_quality(model_endpoint, test_clips):
    results = []
    for clip in test_clips:
        response = model_endpoint.predict(clip)
        results.append(evaluate_response(response, clip.ground_truth))
    
    return {
        "accuracy": sum(r.correct for r in results) / len(results),
        "format_compliance": sum(r.valid_format for r in results) / len(results),
        "avg_confidence": sum(r.confidence for r in results) / len(results)
    }
```

### Optimization Strategies

#### Resource Management

1. **Parallel Processing**: Extract clips for multiple games simultaneously
2. **Smart Caching**: Reuse downloaded videos across training runs
3. **Incremental Updates**: Only retrain on new data, not full dataset
4. **Batch Optimization**: Combine similar games for efficient processing

#### Cost Optimization

```python
# Cost-effective training schedule
training_schedule = {
    "phase_1": {"games": 1, "epochs": 3, "adapter_size": "SMALL"},
    "phase_2": {"games": 2, "epochs": 4, "adapter_size": "MEDIUM"}, 
    "phase_3": {"games": 3, "epochs": 5, "adapter_size": "MEDIUM"},
    "phase_4": {"games": 4, "epochs": 5, "adapter_size": "LARGE"},
    "phase_5": {"games": 5, "epochs": 6, "adapter_size": "LARGE"}
}
```

#### Success Criteria

**Phase Completion Checklist:**
- ✅ Training job completes without errors
- ✅ Model deploys to persistent endpoint
- ✅ API returns valid responses
- ✅ Performance metrics meet thresholds
- ✅ Manual spot-checks pass quality review

## Resource Optimization

### 1. Compute Resources

#### Cloud Run Jobs Configuration
```python
# Optimal resource allocation
job_resources = {
    "cpu": "2-4 cores",
    "memory": "4-8 Gi",
    "timeout": "1800s",  # 30 minutes
    "max_retries": 3
}
```

#### Vertex AI Training Resources
```python
# Training job optimization
training_config = {
    "machine_type": "n1-standard-4",
    "accelerator_count": 0,  # CPU-only for cost efficiency
    "disk_size_gb": 100,
    "max_runtime_hours": 24
}
```

### 2. Storage Optimization

#### GCS Storage Classes
```python
storage_strategy = {
    "active_training": "STANDARD",  # Frequent access
    "completed_models": "NEARLINE",  # Monthly access
    "archived_clips": "COLDLINE"   # Annual access
}
```

#### Data Lifecycle Management
```python
# Automatic storage class transitions
lifecycle_rules = {
    "training_data": "Delete after 90 days",
    "model_artifacts": "Move to NEARLINE after 30 days",
    "video_clips": "Move to COLDLINE after 60 days"
}
```

### 3. Cost Monitoring

#### Expected Costs per Training Run

| Component | Cost Range | Optimization |
|-----------|------------|-------------|
| Vertex AI Training | $50-150 | Use smaller adapter sizes initially |
| Cloud Storage | $5-20 | Implement lifecycle policies |
| Cloud Run Jobs | $10-30 | Optimize job duration |
| Data Transfer | $2-10 | Keep data in same region |
| **Total per Game** | **$67-210** | **Use progressive training** |

#### Cost Optimization Tips

1. **Start Small**: Begin with 1-2 games, expand gradually
2. **Use Efficient Formats**: Compress video clips when possible
3. **Monitor Quotas**: Track Vertex AI usage limits
4. **Regional Consistency**: Keep all resources in us-central1
5. **Cleanup Policies**: Remove temporary files after training

### 4. Performance Optimization

#### Parallel Processing
```python
# Concurrent clip extraction
async def extract_clips_parallel(games, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(extract_game_clips, game) for game in games]
        results = [future.result() for future in futures]
    return results
```

#### Smart Caching
```python
# Video caching strategy
def download_video_if_needed(game_id, angle):
    cache_path = f"/tmp/{game_id}_{angle}.mp4"
    if not os.path.exists(cache_path):
        download_from_gcs(game_id, angle, cache_path)
    return cache_path
```

#### Batch Processing
```python
# Optimize JSONL creation
def create_training_batch(plays_batch, batch_size=50):
    """Process plays in batches for memory efficiency."""
    for i in range(0, len(plays_batch), batch_size):
        batch = plays_batch[i:i+batch_size]
        yield process_play_batch(batch)
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Video File Access Errors

**Problem**: Missing video files in GCS
```
Error: Missing required video files:
  - gs://uball-videos-production/Games/game_001/test_farleft.mp4
```

**Solution**: 
```bash
# Check video file naming patterns
gsutil ls gs://uball-videos-production/Games/{game_id}/

# Expected patterns:
# test_farleft.mp4, game1_farleft.mp4, etc.
```

#### 2. JSONL Format Validation Errors

**Problem**: Invalid training data format
```
Error: Invalid JSONL structure in training file
```

**Solution**:
```python
# Validate JSONL format
def validate_jsonl_file(file_path):
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Line {line_num}: {e}")
```

#### 3. Vertex AI Training Failures

**Problem**: Training job fails with quota errors
```
Error: Quota exceeded for tuning jobs
```

**Solution**:
```bash
# Check current quotas
gcloud compute project-info describe --project=your-project-id

# Request quota increase if needed
gcloud support cases create --display-name="Vertex AI Quota Increase"
```

#### 4. Memory Issues During Processing

**Problem**: Out of memory during clip extraction
```
Error: Memory allocation failed during video processing
```

**Solution**:
```python
# Reduce batch size and add memory management
def process_clips_with_memory_management(plays, max_batch=10):
    for batch in chunks(plays, max_batch):
        process_batch(batch)
        gc.collect()  # Force garbage collection
```

#### 5. Authentication and Permissions

**Problem**: Access denied errors
```
Error: 403 Forbidden - insufficient permissions
```

**Solution**:
```bash
# Check service account permissions
gcloud projects get-iam-policy your-project-id \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:your-sa@project.iam.gserviceaccount.com"

# Required roles:
# - aiplatform.user
# - storage.admin
# - workflows.invoker
```

### Debugging Commands

#### Check Training Status
```bash
# Monitor active training jobs
gcloud ai models tuning-jobs list --region=us-central1

# Get specific job details
gcloud ai models tuning-jobs describe JOB_ID --region=us-central1
```

#### Validate Workflow
```bash
# Test workflow syntax
gcloud workflows deploy basketball-training-pipeline \
  --source=workflows/basketball-training-pipeline.yaml \
  --location=us-central1

# Run validation script
python scripts/validation/validate_workflow_params.py
```

#### Monitor Storage Usage
```bash
# Check bucket contents
gsutil du -sh gs://uball-training-data/

# List recent training files
gsutil ls -l gs://uball-training-data/games/*/video_training_*.jsonl
```

### Performance Monitoring

#### Key Metrics Dashboard
```python
monitoring_metrics = {
    "clip_extraction_rate": "clips/minute",
    "training_job_duration": "hours", 
    "api_response_time": "seconds",
    "storage_usage": "GB",
    "training_cost": "USD"
}
```

#### Health Checks
```python
def health_check():
    checks = [
        verify_gcp_authentication(),
        check_vertex_ai_quotas(),
        validate_storage_access(),
        test_workflow_deployment(),
        verify_model_endpoint()
    ]
    return all(checks)
```

### Contact and Support

For additional support:
- Check the validation scripts in `/scripts/validation/`
- Run comprehensive validation before training
- Monitor Cloud Console for resource usage
- Review logs in Cloud Logging for detailed error messages

---

*This guide covers the complete basketball training pipeline. Follow the step-by-step instructions and validation checks for successful model training.*