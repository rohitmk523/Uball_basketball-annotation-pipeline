# Basketball Training Pipeline V2 - Deployment Guide

## Overview

This guide covers the deployment of the **new Cloud Functions architecture** that replaces Cloud Run Jobs with a more scalable, reliable solution.

## Architecture Changes

### Before (Cloud Run Jobs)
- ❌ Sequential processing of games
- ❌ 8GB memory limit causing OOM
- ❌ Poor logging visibility
- ❌ Long running times (30+ min for 6 games)
- ❌ No partial success

### After (Cloud Functions)
- ✅ Parallel processing (up to 40 games simultaneously)
- ✅ Configurable memory per function
- ✅ Excellent logging in Cloud Logging
- ✅ Fast execution (all games process at once)
- ✅ Isolated failures (one game failure doesn't affect others)

## Prerequisites

1. **GCP Project**: `refined-circuit-474617-s8`
2. **Service Account**: `basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com`
3. **Required APIs Enabled**:
   - Cloud Functions API
   - Cloud Run API
   - Workflows API
   - Vertex AI API
   - Cloud Storage API

4. **GCS Buckets**:
   - `uball-videos-production` (source videos)
   - `uball-training-data` (output clips and training data)

5. **Supabase Database** with plays data

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
# From repository root
bash scripts/deploy-new-architecture.sh
```

This script will:
1. Deploy the Cloud Function
2. Deploy the new workflow
3. Provide verification commands

### Option 2: Manual Deployment

#### Step 1: Deploy Cloud Function

```bash
cd functions/extract-clips-cf

# Deploy the function
gcloud functions deploy extract-clips-game \
  --gen2 \
  --runtime=python311 \
  --region=us-central1 \
  --source=. \
  --entry-point=extract_clips_game \
  --trigger-http \
  --allow-unauthenticated \
  --memory=8GB \
  --timeout=3600s \
  --max-instances=40 \
  --env-vars-file=.env.yaml \
  --service-account=basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com \
  --project=refined-circuit-474617-s8
```

**Note**: Make sure `.env.yaml` is configured with your Supabase credentials.

#### Step 2: Deploy Workflow

```bash
cd ../..

gcloud workflows deploy basketball-training-pipeline-v2 \
  --source=workflows/basketball-training-pipeline-v2.yaml \
  --location=us-central1 \
  --service-account=basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com \
  --project=refined-circuit-474617-s8
```

## Testing

### Test 1: Single Game via Cloud Function

```bash
# Get function URL
FUNCTION_URL=$(gcloud functions describe extract-clips-game \
  --gen2 \
  --region=us-central1 \
  --project=refined-circuit-474617-s8 \
  --format="value(serviceConfig.uri)")

# Test with a game
curl -X POST $FUNCTION_URL \
  -H "Content-Type: application/json" \
  -d '{"game_id": "23135de8-36ca-4882-bdf1-8796cd8caa8a"}'
```

Expected response:
```json
{
  "success": true,
  "game_id": "23135de8-36ca-4882-bdf1-8796cd8caa8a",
  "total_plays": 120,
  "clips_extracted": 238,
  "clips_failed": 2,
  "clips_needed": 240,
  "success_rate": 99.2,
  "training_file": "gs://uball-training-data/games/{game_id}/video_training_...",
  "validation_file": "gs://uball-training-data/games/{game_id}/video_validation_..."
}
```

### Test 2: Small Batch via Workflow

```bash
# Run workflow with 2-3 games
gcloud workflows run basketball-training-pipeline-v2 \
  --data='{"game_ids": ["23135de8-36ca-4882-bdf1-8796cd8caa8a", "776981a3-b898-4df1-83ab-5e5b1bb4d2c5"]}' \
  --location=us-central1 \
  --project=refined-circuit-474617-s8
```

### Test 3: Full Scale (30-40 games)

Once tests 1 and 2 pass:

```bash
gcloud workflows run basketball-training-pipeline-v2 \
  --data='{"game_ids": ["game1", "game2", ..., "game40"]}' \
  --location=us-central1 \
  --project=refined-circuit-474617-s8
```

## Monitoring

### Cloud Function Logs

```bash
# View recent logs
gcloud functions logs read extract-clips-game \
  --gen2 \
  --region=us-central1 \
  --limit=100

# Stream logs in real-time
gcloud functions logs read extract-clips-game \
  --gen2 \
  --region=us-central1 \
  --follow

# Filter by game_id (in log message)
gcloud logging read 'resource.type="cloud_function" AND resource.labels.function_name="extract-clips-game" AND textPayload:~"game_id"' \
  --limit=100 \
  --format=json
```

### Workflow Logs

```bash
# List recent executions
gcloud workflows executions list basketball-training-pipeline-v2 \
  --location=us-central1 \
  --limit=10

# Get specific execution details
gcloud workflows executions describe EXECUTION_ID \
  --workflow=basketball-training-pipeline-v2 \
  --location=us-central1
```

### Cloud Logging Console

Visit: https://console.cloud.google.com/logs

Filter by:
- Resource type: `Cloud Function`
- Function name: `extract-clips-game`

## Troubleshooting

### Issue: Out of Memory (OOM)

**Symptom**: Function fails with "memory limit exceeded"

**Solution**: Increase memory in `functions/extract-clips-cf/deploy.sh`:

```bash
--memory=16GB  # or 32GB
```

Redeploy:
```bash
cd functions/extract-clips-cf
bash deploy.sh
```

### Issue: Timeout

**Symptom**: Function timeout after 60 minutes

**Solution**: Games with many plays may need more time. Increase timeout:

```bash
--timeout=3600s  # Already at max (60 min)
```

If still timing out, split the game or optimize clip extraction.

### Issue: Video Not Found

**Symptom**: Error "No video found for FAR_LEFT"

**Solution**: Check video naming in GCS:

```bash
gsutil ls gs://uball-videos-production/Games/{game_id}/
```

Expected files:
- `game1_farleft.mp4`
- `game1_farright.mp4`
- `game1_nearleft.mp4`
- `game1_nearright.mp4`

Or other patterns like `test_farleft.mp4`, `farleft.mp4`, etc.

### Issue: Supabase Connection Failed

**Symptom**: Error "Failed to load plays from Supabase"

**Solution**: Check environment variables:

```bash
# Verify .env.yaml has correct values
cat functions/extract-clips-cf/.env.yaml

# Test Supabase connection manually
python3 -c "
from supabase import create_client
client = create_client('YOUR_URL', 'YOUR_KEY')
response = client.table('plays').select('id').limit(1).execute()
print(response.data)
"
```

### Issue: Function Not Found

**Symptom**: 404 when calling function URL

**Solution**: Verify deployment:

```bash
gcloud functions describe extract-clips-game \
  --gen2 \
  --region=us-central1 \
  --project=refined-circuit-474617-s8
```

Redeploy if needed.

## Performance Benchmarks

Based on typical game data:

| Metric | Value |
|--------|-------|
| Plays per game | 100-150 |
| Clips per play | 2 |
| Total clips per game | 200-300 |
| Processing time per game | 10-20 minutes |
| Parallel games | Up to 40 |
| Total time for 40 games | 15-25 minutes (vs 3-4 hours sequential) |

## Cost Estimation

### Cloud Functions

- **Invocations**: 40 games × 1 = 40 invocations
- **Memory**: 8GB × 20 min × 40 = ~100 GB-hours
- **Estimated cost**: ~$8-12 per run

### Vertex AI Tuning

- **Training**: ~$50-100 per tuning job (depends on model size and epochs)

**Total per training run**: ~$60-110

## Migration from Old Architecture

### Step 1: Test New Architecture

Run new workflow in parallel with old one using different game sets.

### Step 2: Compare Results

Verify JSONL files are identical:

```bash
# Compare training data
diff <(gsutil cat gs://uball-training-data/games/game1/video_training_OLD.jsonl | jq -S .) \
     <(gsutil cat gs://uball-training-data/games/game1/video_training_NEW.jsonl | jq -S .)
```

### Step 3: Switch Over

Once validated, update your application to use the new workflow:

```python
# Old
workflow_name = "basketball-training-pipeline"

# New
workflow_name = "basketball-training-pipeline-v2"
```

### Step 4: Cleanup Old Resources

After confirming new architecture works:

```bash
# Delete old Cloud Run Jobs
gcloud run jobs delete extract-clips-GAME_ID --region=us-central1

# Keep old workflow as backup for 1 week, then delete
gcloud workflows delete basketball-training-pipeline --location=us-central1
```

## Support

For issues or questions:
1. Check logs in Cloud Logging
2. Review this troubleshooting guide
3. Test with a single game first
4. Gradually scale up

## Rollback Plan

If new architecture has issues:

1. Revert to old workflow:
   ```bash
   gcloud workflows run basketball-training-pipeline \
     --data='{"game_ids": [...]}' \
     --location=us-central1
   ```

2. Old workflow still uses Cloud Run Jobs (existing deployment)

3. Keep both workflows deployed until confident in new architecture
