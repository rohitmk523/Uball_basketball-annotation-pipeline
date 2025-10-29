# Basketball Training Pipeline - Deployment Guide

## Architecture Overview

The training pipeline uses **Cloud Functions + Workflows** for scalable, parallel processing:

- **Cloud Function**: `extract-clips-game` - Extracts clips for a single game
- **Workflow**: `basketball-training-pipeline` - Orchestrates the entire pipeline
- **Pattern**: Fire-and-forget + polling (handles long-running jobs)

## Prerequisites

1. GCP Project: `refined-circuit-474617-s8`
2. Service Account: `basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com`
3. Supabase database with plays data
4. Videos in `uball-videos-production` bucket

## Deployment

### Step 1: Deploy Cloud Function

```bash
cd functions/extract-clips-cf
bash deploy.sh
```

### Step 2: Deploy Workflow

```bash
gcloud workflows deploy basketball-training-pipeline \
  --source=workflows/basketball-training-pipeline.yaml \
  --location=us-central1 \
  --service-account=basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com \
  --project=refined-circuit-474617-s8
```

## Usage

### Run Training for Multiple Games

```bash
gcloud workflows run basketball-training-pipeline \
  --data='{"game_ids": ["game1-uuid", "game2-uuid", "game3-uuid"]}' \
  --location=us-central1 \
  --project=refined-circuit-474617-s8
```

### Monitor Execution

```bash
# List recent executions
gcloud workflows executions list basketball-training-pipeline \
  --location=us-central1 \
  --limit=5

# Get specific execution details
gcloud workflows executions describe EXECUTION_ID \
  --workflow=basketball-training-pipeline \
  --location=us-central1
```

## How It Works

### 1. Async Function Triggers
- Workflow triggers Cloud Functions for all games in parallel
- Functions run asynchronously (fire-and-forget pattern)
- No HTTP timeout issues

### 2. Polling for Completion
- Workflow polls GCS every 30 seconds
- Checks for JSONL file creation
- Waits up to 2 hours for all games

### 3. JSONL Combination
- Combines training/validation files from all games
- Creates cumulative training dataset

### 4. Vertex AI Tuning
- Starts supervised tuning job
- Monitors until completion
- Returns trained model

## Troubleshooting

### Check Function Logs

```bash
gcloud functions logs read extract-clips-game \
  --gen2 \
  --region=us-central1 \
  --limit=100
```

### Check Workflow Logs

```bash
gcloud logging read \
  'resource.type="workflows.googleapis.com/Workflow"
   AND resource.labels.workflow_id="basketball-training-pipeline"' \
  --limit=50
```

### Common Issues

**Games not completing**:
- Check if videos exist in GCS
- Verify plays data in Supabase
- Check Cloud Function logs

**Out of memory**:
- Increase function memory in `deploy.sh`
- Default is 8GB, can go up to 32GB

## Performance

- **6 games (996 plays)**: ~30-40 minutes total
- **Clip extraction**: 20-30 minutes (parallel)
- **JSONL combination**: 2-3 minutes
- **Vertex AI tuning**: 10-15 minutes

## Cost Estimation

- Cloud Functions: ~$10-15 per 6 games
- Vertex AI Tuning: ~$50-100 per job
- **Total**: ~$60-115 per training run
