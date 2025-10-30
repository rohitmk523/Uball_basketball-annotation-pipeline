# Basketball Video Annotation Pipeline

Automated pipeline for processing basketball game videos and fine-tuning Gemini models for play analysis.

## Overview

This system processes full basketball game videos, extracts individual play clips, generates training data, and fine-tunes Google's Gemini 2.5 Pro model using Vertex AI.

**Key Features**:
- ⚡ **Parallel Processing**: Process multiple games simultaneously using Cloud Run Jobs
- 🎯 **Smart Skip Logic**: Automatically detects and skips already-extracted clips
- 🔄 **End-to-End Automation**: From raw videos to deployed model
- 📊 **Scalable**: Process 1 game or 100 with the same pipeline

## Quick Start

### Prerequisites

- Google Cloud Project with billing enabled
- Service account with required permissions
- Supabase database with play metadata
- Game videos uploaded to GCS

### Run the Pipeline

```bash
gcloud workflows execute basketball-training-pipeline-jobs \
  --data='{"game_ids": ["<game-id-1>", "<game-id-2>", ...]}' \
  --location=us-central1 \
  --project=<your-project-id>
```

### Monitor Progress

```bash
# List recent executions
gcloud workflows executions list basketball-training-pipeline-jobs \
  --location=us-central1 \
  --limit=5

# Check specific execution
gcloud workflows executions describe <execution-id> \
  --workflow basketball-training-pipeline-jobs \
  --location=us-central1
```

## Repository Structure

```
├── app/                          # FastAPI application (optional API)
│   ├── api/                      # API routes
│   ├── core/                     # Core configuration
│   ├── models/                   # Data models
│   └── services/                 # Business logic services
│
├── jobs/                         # Cloud Run Jobs
│   └── extract-clips-job/        # Main clip extraction job
│       ├── Dockerfile
│       ├── main.py               # Entry point
│       ├── extract_clips_job.py  # Core logic
│       └── requirements.txt
│
├── functions/                    # Cloud Functions
│   └── combine-jsonl-cf/         # JSONL combination function
│       ├── main.py
│       └── requirements.txt
│
├── workflows/                    # Cloud Workflows definitions
│   └── basketball-training-pipeline-jobs.yaml
│
├── credentials/                  # Service account keys (gitignored)
│   └── service-account-key.json
│
├── ARCHITECTURE.md               # Detailed architecture documentation
├── requirements.txt              # Python dependencies (FastAPI app)
└── docker-compose.yml            # Local development (FastAPI app)
```

## Core Components

### 1. Cloud Run Job: extract-clips-job
Extracts video clips for individual plays from full game videos.
- Processes one game per execution
- Runs in parallel for multiple games
- Automatically skips existing clips
- Generates JSONL training data

### 2. Cloud Function: combine-jsonl
Combines JSONL files from multiple games into unified training dataset.
- Lightweight HTTP function
- Merges training and validation files
- Returns combined statistics

### 3. Cloud Workflows: basketball-training-pipeline-jobs
Orchestrates the entire pipeline from videos to trained model.
- Triggers parallel clip extraction
- Polls for completion
- Combines training data
- Initiates Vertex AI tuning

## Data Flow

```
1. Game Videos (GCS)
   ↓
2. Cloud Run Jobs (Parallel)
   ↓ 
3. Individual Clips + JSONL
   ↓
4. Cloud Function (Combine)
   ↓
5. Combined Training Dataset
   ↓
6. Vertex AI Tuning
   ↓
7. Fine-tuned Gemini Model
```

## Configuration

### Environment Variables

For Cloud Run Job (`extract-clips-job`):
```bash
GAME_ID=<uuid>                    # Required: Game to process
SUPABASE_URL=<url>                # Required: Supabase database URL
SUPABASE_KEY=<key>                # Required: Supabase API key
```

### GCS Buckets

```bash
# Source videos
uball-videos-production/Games/{game_id}/

# Training data output  
uball-training-data/games/{game_id}/
uball-training-data/cumulative-execution-{timestamp}/
```

### Supabase Schema

The pipeline expects a `plays` table:
```sql
CREATE TABLE plays (
  id UUID PRIMARY KEY,
  game_id UUID NOT NULL,
  start_time NUMERIC NOT NULL,
  end_time NUMERIC NOT NULL,
  angle TEXT NOT NULL,  -- 'broadcast', 'tactical', or 'both'
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Deployment

### 1. Deploy Cloud Run Job

```bash
cd jobs/extract-clips-job

# Build image
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/<project-id>/basketball-jobs/extract-clips-job:latest

# Deploy job
gcloud run jobs deploy extract-clips-job \
  --image=us-central1-docker.pkg.dev/<project-id>/basketball-jobs/extract-clips-job:latest \
  --region=us-central1 \
  --memory=8Gi \
  --cpu=4 \
  --task-timeout=2h \
  --max-retries=3 \
  --set-env-vars=SUPABASE_URL=<url> \
  --set-secrets=SUPABASE_KEY=supabase-key:latest \
  --service-account=<service-account-email>
```

### 2. Deploy Cloud Function

```bash
cd functions/combine-jsonl-cf

gcloud functions deploy combine-jsonl \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=combine_jsonl \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=2Gi \
  --service-account=<service-account-email>
```

### 3. Deploy Cloud Workflow

```bash
gcloud workflows deploy basketball-training-pipeline-jobs \
  --source=workflows/basketball-training-pipeline-jobs.yaml \
  --location=us-central1 \
  --service-account=<service-account-email>
```

## Performance

### Processing Time (6 games)

| Phase | With Skip Logic | Without Skip Logic |
|-------|----------------|-------------------|
| Clip Extraction | ~30 sec | ~10 min |
| JSONL Combination | ~10 sec | ~10 sec |
| Vertex AI Tuning | 1-3 hours | 1-3 hours |
| **Total** | **~1-3 hours** | **~1.5-3.5 hours** |

### Output Statistics

For 6 games (~180 plays):
- **Training Examples**: ~1,500
- **Validation Examples**: ~400
- **Total Clips**: ~360 (2 angles per play)
- **Storage Required**: ~5-10 GB

## Cost Estimates

Per 6-game execution:
- Cloud Run Jobs: ~$0.50
- Cloud Functions: ~$0.01
- Cloud Workflows: ~$0.01
- GCS Storage: ~$0.10/month
- Vertex AI Tuning: ~$5-10
- **Total**: ~$6-11 per run

## Monitoring

### View Workflow Logs

```bash
gcloud logging read \
  "resource.type=workflows.googleapis.com/Workflow" \
  --limit=50 \
  --format="table(timestamp,jsonPayload.message)"
```

### View Job Logs

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=extract-clips-job" \
  --limit=50
```

### Check Tuning Job Status

```bash
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1/projects/<project-id>/locations/us-central1/tuningJobs"
```

## Troubleshooting

### Common Issues

**Job fails with "No plays found"**
- Check Supabase connectivity
- Verify game_id exists in database
- Check plays table has data for that game

**Clips extraction timeout**
- Increase job timeout (currently 2h)
- Check video file accessibility in GCS
- Verify ffmpeg installation in container

**Workflow stuck at polling**
- Check if JSONL files were created in GCS
- Verify GCS bucket permissions
- Check for job execution failures

**Tuning job fails**
- Verify JSONL format is correct
- Check file accessibility in GCS
- Ensure sufficient Vertex AI quota

### Debug Mode

Add verbose logging to jobs:
```bash
gcloud run jobs execute extract-clips-job \
  --region=us-central1 \
  --update-env-vars=LOG_LEVEL=DEBUG
```

## Security

- Service accounts follow principle of least privilege
- GCS buckets are private
- API keys stored in Secret Manager
- No public endpoints exposed
- IAM-controlled access to all resources

## Development

### Local Testing (FastAPI App)

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload

# With Docker
docker-compose up
```

### Testing Job Locally

```bash
cd jobs/extract-clips-job

# Build image
docker build -t extract-clips-job:test .

# Run locally
docker run --rm \
  -e GAME_ID=<test-game-id> \
  -e SUPABASE_URL=<url> \
  -e SUPABASE_KEY=<key> \
  -v ~/.config/gcloud:/root/.config/gcloud \
  extract-clips-job:test
```

## Support

For detailed architecture information, see [ARCHITECTURE.md](./ARCHITECTURE.md).

For issues or questions:
1. Check Cloud Workflows execution logs
2. Check Cloud Run Jobs logs
3. Verify GCS bucket contents
4. Check Vertex AI tuning job status

## License

Proprietary - Cellstrat © 2025
