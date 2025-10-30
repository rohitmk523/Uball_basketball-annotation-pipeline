# Basketball Training Pipeline - Architecture

## Overview

Automated pipeline for processing basketball game videos, extracting clips, generating training data, and fine-tuning Gemini models using Vertex AI.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Cloud Workflows                             │
│           (Orchestration & State Management)                     │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ├──────────────────────────────────────────┐
           │                                          │
           ▼                                          ▼
┌──────────────────────┐                  ┌────────────────────────┐
│  Cloud Run Jobs      │                  │  Cloud Function        │
│  (Parallel)          │                  │  (combine-jsonl)       │
│                      │                  │                        │
│  - extract-clips-job │                  │  Combines JSONL from   │
│  - 6 jobs parallel   │                  │  all games             │
│  - Skip logic        │                  └────────────────────────┘
└──────────┬───────────┘                              │
           │                                          │
           ▼                                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                  Google Cloud Storage                             │
│                                                                   │
│  Buckets:                                                         │
│  - uball-videos-production     (Source videos)                   │
│  - uball-training-data         (Clips & JSONL files)             │
└───────────────────────────────────────┬───────────────────────────┘
                                        │
                                        ▼
                              ┌─────────────────────┐
                              │   Vertex AI         │
                              │   Tuning Jobs       │
                              │                     │
                              │   Fine-tune         │
                              │   Gemini 2.5 Pro    │
                              └─────────────────────┘
```

## Components

### 1. Cloud Run Job: `extract-clips-job`

**Purpose**: Extract video clips for basketball plays from full game videos.

**Specs**:
- Memory: 8GB
- CPU: 4 cores
- Timeout: 2 hours
- Execution: Parallel (one per game)

**Features**:
- **Skip Logic**: Automatically detects existing clips and skips extraction
- **Dual-angle Processing**: Handles both broadcast and tactical camera angles
- **JSONL Generation**: Creates training/validation datasets
- **Error Handling**: Robust retry and error logging

**Process**:
1. Receives `GAME_ID` as environment variable
2. Fetches play metadata from Supabase
3. Downloads game video from GCS
4. Checks if clips already exist (skip if yes)
5. Extracts clips using ffmpeg
6. Generates JSONL training files (80/20 split)
7. Uploads to GCS

**Output Structure**:
```
gs://uball-training-data/
  games/
    {game_id}/
      clips/
        {play_id}_broadcast.mp4
        {play_id}_tactical.mp4
      video_training_{timestamp}.jsonl
      video_validation_{timestamp}.jsonl
```

### 2. Cloud Function: `combine-jsonl`

**Purpose**: Combine JSONL files from multiple games into unified training dataset.

**Specs**:
- Memory: 2GB
- Timeout: 9 minutes
- Trigger: HTTP

**Input**:
```json
{
  "game_ids": ["id1", "id2", ...],
  "execution_dir": "cumulative-execution-12345"
}
```

**Output**:
```
gs://uball-training-data/
  {execution_dir}/
    combined_training.jsonl
    combined_validation.jsonl
```

### 3. Cloud Workflows: `basketball-training-pipeline-jobs`

**Purpose**: Orchestrate the entire training pipeline.

**Steps**:

1. **Initialization**
   - Parse game IDs
   - Generate execution directory
   - Set base model and parameters

2. **Parallel Clip Extraction**
   - Trigger Cloud Run Job for each game
   - All games process simultaneously
   - Independent executions

3. **Completion Polling**
   - Check GCS for JSONL file existence
   - Poll every 30 seconds
   - Track completed games

4. **JSONL Combination**
   - Call combine-jsonl Cloud Function
   - Merge all training data
   - Create unified dataset

5. **Vertex AI Tuning**
   - Create tuning job
   - Configure hyperparameters
   - Monitor completion

**Parameters**:
```json
{
  "game_ids": ["<uuid>", "<uuid>", ...],
  "base_model": "gemini-2.5-pro",
  "epochs": 5,
  "learning_rate_multiplier": 1.0,
  "adapter_size": "ADAPTER_SIZE_ONE"
}
```

## Data Flow

### Phase 1: Clip Extraction (Parallel)
```
Game Video (GCS) → Cloud Run Job → Clips + JSONL
```
- Process: 6 games × ~30 plays = ~180 clips
- Time: ~5-10 minutes (with skip logic)
- Output: Individual game JSONL files

### Phase 2: Data Combination
```
Individual JSONL → Cloud Function → Combined JSONL
```
- Process: Merge training/validation files
- Time: ~10 seconds
- Output: Unified training dataset

### Phase 3: Model Tuning
```
Combined JSONL → Vertex AI → Fine-tuned Model
```
- Process: Supervised fine-tuning
- Time: 1-3 hours
- Output: Deployed model endpoint

## Storage Structure

### Videos Bucket: `uball-videos-production`
```
Games/
  {game_id}/
    BroadcastHalf1.mp4
    BroadcastHalf2.mp4
    TacticalHalf1.mp4
    TacticalHalf2.mp4
```

### Training Bucket: `uball-training-data`
```
games/
  {game_id}/
    clips/
      {play_id}_broadcast.mp4
      {play_id}_tactical.mp4
    video_training_{timestamp}.jsonl
    video_validation_{timestamp}.jsonl

cumulative-execution-{timestamp}/
  combined_training.jsonl
  combined_validation.jsonl
```

## Database Schema (Supabase)

### Table: `plays`
```sql
- id (uuid, primary key)
- game_id (uuid, foreign key)
- start_time (numeric)
- end_time (numeric)
- angle (text: 'broadcast' | 'tactical' | 'both')
- description (text)
- created_at (timestamp)
```

## JSONL Format

### Training Data Structure
```json
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
          "text": "Analyze this basketball play."
        }
      ]
    },
    {
      "role": "model",
      "parts": [
        {
          "text": "{play_description}"
        }
      ]
    }
  ]
}
```

## Performance Characteristics

### Extraction (with Skip Logic)
- **New Games**: ~10 minutes per game
- **Existing Clips**: ~30 seconds per game
- **Parallel Speedup**: 6 games in ~10 minutes (vs 60 minutes sequential)

### Combination
- **6 Games**: ~10 seconds
- **Output Size**: ~1,500-2,000 examples

### Tuning
- **Duration**: 1-3 hours
- **Cost**: ~$5-10 per job
- **Output**: Fine-tuned Gemini model

## Error Handling

### Job-Level
- Automatic retries (max 3)
- Individual game failures don't block others
- Detailed logging in Cloud Run

### Workflow-Level
- Try-catch blocks for API calls
- Continue on individual game failure
- Timeout protection (1 hour max)

### Data-Level
- Validation of JSONL format
- Check for file existence before processing
- Verify clip extraction success

## Scalability

### Current Capacity
- **Games per execution**: Unlimited (tested with 6)
- **Parallel jobs**: Up to 20 concurrent
- **Storage**: Effectively unlimited (GCS)

### Bottlenecks
- Vertex AI tuning: Sequential only
- ffmpeg extraction: CPU-bound
- Network I/O: Video download bandwidth

## Security

### Authentication
- Service Account: `basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com`
- Principle of least privilege

### Permissions Required
- **Cloud Run**: Execute jobs
- **Cloud Functions**: Invoke
- **GCS**: Read/write to specific buckets
- **Vertex AI**: Create tuning jobs
- **Supabase**: Read plays data

### Data Access
- Private GCS buckets
- IAM-controlled access
- No public endpoints

## Monitoring & Observability

### Logs
- Cloud Workflows: Execution logs
- Cloud Run Jobs: Container logs
- Cloud Functions: Invocation logs
- Vertex AI: Tuning job logs

### Metrics
- Job success rate
- Execution duration
- Clip extraction count
- Training example count

### Alerts
- Job failures
- Workflow timeouts
- Storage quota warnings

## Cost Optimization

### Strategies
1. **Skip Logic**: Avoid re-extracting existing clips
2. **Parallel Processing**: Reduce total wall-clock time
3. **Right-sized Resources**: 8GB/4CPU for jobs
4. **Spot Instances**: (Future) For non-time-critical jobs

### Estimated Costs (6 games)
- Cloud Run Jobs: ~$0.50
- Cloud Functions: ~$0.01
- Cloud Workflows: ~$0.01
- GCS Storage: ~$0.10/month
- Vertex AI Tuning: ~$5-10
- **Total per run**: ~$6-11

## Future Enhancements

1. **Database Tracking**: Store execution history in Supabase
2. **Automatic Retries**: Intelligent retry with backoff
3. **Model Registry**: Automatic model versioning
4. **Real-time Monitoring**: Dashboard for pipeline status
5. **Cost Analytics**: Detailed cost tracking per execution
6. **A/B Testing**: Compare model versions
7. **Auto-scaling**: Dynamic resource allocation
8. **Incremental Training**: Add new games to existing models

