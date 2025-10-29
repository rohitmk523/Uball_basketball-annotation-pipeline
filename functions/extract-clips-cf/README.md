# Extract Clips Cloud Function

Cloud Function (2nd Gen) for extracting basketball video clips and creating training data.

## Architecture

This function replaces the Cloud Run Jobs architecture with a more scalable approach:

- **Parallel Processing**: Each game processed in parallel (up to 40 games simultaneously)
- **Streaming**: Videos streamed from GCS, no full download needed
- **Better Logging**: All logs in Cloud Logging with game_id labels
- **Auto-scaling**: Functions auto-scale based on load
- **Isolated Execution**: Each game is isolated, failures don't affect others

## Function Flow

1. Receive `game_id` via HTTP POST
2. Query Supabase for all plays in that game
3. Validate all required videos exist in GCS
4. Extract clips for each play using ffmpeg
5. Upload clips to training bucket
6. Create JSONL training/validation files
7. Return results

## Deployment

```bash
# 1. Make sure you're in the function directory
cd functions/extract-clips-cf

# 2. Deploy
bash deploy.sh
```

## Usage

### Via curl

```bash
curl -X POST https://us-central1-refined-circuit-474617-s8.cloudfunctions.net/extract-clips-game \
  -H "Content-Type: application/json" \
  -d '{"game_id": "23135de8-36ca-4882-bdf1-8796cd8caa8a"}'
```

### Via Workflows (recommended)

The workflow will call this function for each game in parallel.

## Configuration

### Environment Variables

Set in `.env.yaml`:

- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_KEY`: Supabase service role key
- `GCS_VIDEO_BUCKET`: Bucket containing game videos (default: uball-videos-production)
- `GCS_TRAINING_BUCKET`: Bucket for training data (default: uball-training-data)

### Resources

- **Memory**: 8GB (configurable in deploy.sh)
- **Timeout**: 60 minutes
- **Max Instances**: 40 (allows 40 games in parallel)

## Input Format

```json
{
  "game_id": "uuid-string"
}
```

## Output Format

```json
{
  "success": true,
  "game_id": "uuid",
  "total_plays": 120,
  "clips_extracted": 238,
  "clips_failed": 2,
  "clips_needed": 240,
  "success_rate": 99.2,
  "training_file": "gs://uball-training-data/games/{game_id}/video_training_{game_id}_{timestamp}.jsonl",
  "validation_file": "gs://uball-training-data/games/{game_id}/video_validation_{game_id}_{timestamp}.jsonl",
  "training_examples": 192,
  "validation_examples": 48
}
```

## Error Handling

- If no plays found: Returns 404
- If videos missing: Returns 500 with error details
- If extraction fails: Continues with other clips, reports failures in response

## Monitoring

View logs:

```bash
gcloud functions logs read extract-clips-game \
  --gen2 \
  --region=us-central1 \
  --limit=100
```

## Troubleshooting

### Out of Memory

Increase memory in `deploy.sh`:

```bash
--memory=16GB
```

### Timeout

Increase timeout (max 60 minutes):

```bash
--timeout=3600s
```

### Too Many Concurrent Requests

Increase max instances:

```bash
--max-instances=50
```
