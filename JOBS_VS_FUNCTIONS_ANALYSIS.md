# Cloud Run Jobs vs Cloud Functions - Architecture Analysis

## Current Problem Diagnosis

### What's Happening Now:
- **Expected**: 6 games processing in parallel, 5-10 min per game
- **Actual**: Only 1 game processing, 5 clips in 5 minutes (very slow)
- **Issue**: Likely hitting storage/memory constraints or functions aren't all triggering

### Root Cause - Temporary Storage Problem:
```python
# Current approach downloads 10GB video per angle
temp_video = /tmp/FAR_LEFT.mp4  # 10GB file!
```

**Problem**: Cloud Functions (2nd gen) have limited ephemeral storage:
- Default `/tmp` size: **512MB** (not enough!)
- Video files: **~10GB each**
- Result: Function fails or doesn't start

---

## Architecture Comparison

### Option 1: Cloud Functions (Current)

```
Architecture:
  Workflow → 6 Cloud Functions (parallel)
  Each function processes 1 game:
    - Download 4 videos (40GB total)
    - Extract all clips
    - Upload to GCS
```

**Specifications:**
- Memory: 8GB
- Timeout: 3600s (1 hour)
- Ephemeral storage: 512MB (default) or up to 10GB if configured
- Max instances: 40
- CPU: 2-4 vCPUs (tied to memory)
- Disk: In-memory filesystem only

**Pros:**
✅ HTTP triggered (easy from workflows)
✅ Auto-scaling
✅ Fully serverless
✅ No cold start for HTTP
✅ Simple deployment

**Cons:**
❌ Limited disk space (512MB default, 10GB max)
❌ Memory-tied to vCPUs (can't configure separately)
❌ **Can't process 10GB video with 512MB disk**
❌ Fire-and-forget is a workaround
❌ No persistent storage
❌ More expensive for long-running tasks

**Cost (per game):**
- 8GB memory × 10 minutes = 80 GB-minutes
- ~$0.008 per game

---

### Option 2: Cloud Run Jobs (Recommended)

```
Architecture:
  Workflow → 6 Cloud Run Jobs (parallel)
  Each job processes 1 game:
    For each angle (4 angles):
      - Download 1 video (10GB)
      - Extract clips for that angle
      - Upload clips
      - Delete video
    Generate JSONL files
```

**Specifications:**
- Memory: 512MB to 32GB (flexible)
- CPU: 1 to 8 vCPUs (independent of memory)
- Timeout: Up to 24 hours
- Ephemeral storage: **Up to 10GB** (configurable)
- Max concurrent tasks: 100+
- Can mount persistent volumes if needed

**Pros:**
✅ **Purpose-built for batch processing**
✅ **More ephemeral storage (up to 10GB)**
✅ Independent CPU/memory configuration
✅ Better for long-running tasks
✅ Native async execution (no fire-and-forget hack)
✅ Better logging and job lifecycle
✅ Cheaper for long-running tasks
✅ Can use persistent disks if needed
✅ Better resource isolation

**Cons:**
❌ Not directly HTTP triggered (need API call)
❌ Slightly more complex workflow integration
❌ Cold start on first task

**Cost (per game):**
- 4GB memory × 10 minutes × 2 vCPUs = 80 GB-minutes
- ~$0.005 per game (cheaper!)

---

## Storage Solutions

### Problem: Need to temporarily store 10GB video files

### Solution 1: Configure Ephemeral Storage (Both Functions & Jobs)
```yaml
# Cloud Function deployment
gcloud functions deploy extract-clips-game \
  --memory 8GB \
  --ephemeral-storage 10GB  # ← Add this!
```

```yaml
# Cloud Run Job deployment
gcloud run jobs deploy extract-clips-job \
  --memory 8GB \
  --ephemeral-storage 10GB  # ← Add this!
```

**Impact:**
- Provides 10GB of temporary disk space in `/tmp`
- Enough for 1 video at a time
- Cleaned up after execution

### Solution 2: Process One Angle at a Time (Already Implemented)
```python
# Current code already does this!
for angle in ["FAR_LEFT", "NEAR_LEFT", "FAR_RIGHT", "NEAR_RIGHT"]:
    # Download 1 video (10GB)
    download_video(angle)

    # Extract all clips from this video
    extract_clips(angle)

    # Delete video (free up 10GB)
    delete_video(angle)

    # Repeat for next angle
```

**Why this works:**
- Only 1 video in memory at a time
- 10GB ephemeral storage is sufficient
- Sequential angle processing (fast enough)

### Solution 3: Use Persistent Disk (Cloud Run Jobs Only)
```yaml
# Mount a persistent disk
gcloud run jobs deploy extract-clips-job \
  --memory 8GB \
  --add-volume name=video-cache,type=cloud-storage,bucket=temp-videos
```

**Pros:**
- Can cache videos across executions
- Larger storage capacity
- Reusable

**Cons:**
- More complex
- Additional cost
- Not needed for our use case

---

## Recommended Architecture

### **Cloud Run Jobs (Per Game)**

#### Workflow Structure:
```yaml
main:
  steps:
    - trigger_jobs:
        parallel:
          for:
            value: game_id
            in: ${game_ids}
          steps:
            - trigger_job:
                call: googleapis.run.v1.namespaces.jobs.run
                args:
                  name: projects/${project}/locations/${region}/jobs/extract-clips-job
                  body:
                    overrides:
                      containerOverrides:
                        env:
                          - name: GAME_ID
                            value: ${game_id}
```

#### Job Execution (Per Game):
```python
def process_game(game_id):
    """Process one game - download one angle at a time"""

    plays = fetch_plays(game_id)
    clips_by_angle = group_by_angle(plays)

    # Process each angle sequentially
    for angle in clips_by_angle:
        logger.info(f"🎥 Processing {angle}")

        # 1. Download video (10GB) to /tmp
        video_path = download_video(angle)
        logger.info(f"✅ Downloaded {angle} (10GB)")

        # 2. Extract all clips for this angle
        for clip in clips_by_angle[angle]:
            extract_clip(video_path, clip)
            upload_clip(clip)
        logger.info(f"✅ Extracted {len(clips_by_angle[angle])} clips")

        # 3. Delete video to free space
        os.remove(video_path)
        logger.info(f"🗑️  Deleted {angle}, freed 10GB")

    # 4. Generate JSONL
    create_jsonl(game_id, plays)
    logger.info(f"✅ Created JSONL files")
```

#### Resource Configuration:
```bash
gcloud run jobs deploy extract-clips-job \
  --image gcr.io/project/extract-clips-job \
  --region us-central1 \
  --memory 8Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 1 \
  --parallelism 6 \
  --ephemeral-storage 10Gi  # ← CRITICAL!
```

---

## Why This Solves Your Problems

### Problem 1: Only 1 Game Processing
**Cause**: Functions likely failing due to storage constraints
**Solution**:
- Configure 10GB ephemeral storage
- Cloud Run Jobs with proper resource allocation
- Better job lifecycle management

### Problem 2: Slow Clip Creation (5 clips in 5 min)
**Cause**: Function may be restarting or hitting errors
**Solution**:
- Proper storage configuration
- Better error handling in jobs
- Sequential angle processing (already implemented)

### Problem 3: Not Parallel
**Cause**: Workflow may not be triggering all functions
**Solution**:
- Cloud Run Jobs have better parallel execution
- Workflow can spawn 6 jobs simultaneously
- Each job is independent

---

## Performance Comparison

### Current (Cloud Functions - No Storage Config):
```
Timeline:
  0:00 - Trigger 6 functions
  0:00 - Function 1 tries to download video
  0:01 - Function 1 FAILS (no disk space)
  0:01 - Only 1-2 functions succeed

Result: 60+ minutes for 1 game (sequential fallback)
```

### Option A: Cloud Functions + 10GB Ephemeral Storage:
```
Timeline:
  0:00 - Trigger 6 functions (parallel)
  0:00 - All 6 start downloading angle 1
  0:01 - All 6 extract clips from angle 1
  0:03 - All 6 download angle 2
  0:04 - All 6 extract clips from angle 2
  ... (repeat for 4 angles)
  0:10 - All 6 complete

Result: 10 minutes total (6 games in parallel)
```

### Option B: Cloud Run Jobs + 10GB Ephemeral Storage:
```
Timeline:
  0:00 - Trigger 6 jobs (parallel)
  0:00 - All 6 start downloading angle 1
  0:01 - All 6 extract clips from angle 1
  0:03 - All 6 download angle 2
  0:04 - All 6 extract clips from angle 2
  ... (repeat for 4 angles)
  0:08 - All 6 complete (slightly faster due to better CPU)

Result: 8 minutes total (6 games in parallel)
```

---

## Migration Path

### Step 1: Quick Fix (Cloud Functions + Storage)
**Fastest solution to test:**
```bash
cd functions/extract-clips-cf

gcloud functions deploy extract-clips-game \
  --gen2 \
  --runtime python311 \
  --region us-central1 \
  --source . \
  --entry-point extract_clips_game \
  --memory 8GB \
  --timeout 3600 \
  --max-instances 40 \
  --env-vars-file .env.yaml \
  --ephemeral-storage 10GB  # ← ADD THIS!
```

**Test this first!** This might solve your problem immediately.

### Step 2: Migrate to Cloud Run Jobs (If Needed)
**If Functions still slow, migrate to Jobs:**

1. **Convert Function to Job** (`jobs/extract-clips-job/`):
```python
# main.py - Job entry point
import os
from extract_clips_job import ClipExtractor

def main():
    """Job entry point"""
    game_id = os.environ["GAME_ID"]

    processor = ClipExtractor(
        game_id=game_id,
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_key=os.environ["SUPABASE_SERVICE_KEY"],
        video_bucket=os.environ["GCS_VIDEO_BUCKET"],
        training_bucket=os.environ["GCS_TRAINING_BUCKET"]
    )

    result = processor.process_game()
    print(f"✅ Completed: {result}")

if __name__ == "__main__":
    main()
```

2. **Create Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

3. **Deploy Job**:
```bash
gcloud run jobs deploy extract-clips-job \
  --image gcr.io/project/extract-clips-job \
  --region us-central1 \
  --memory 8Gi \
  --cpu 4 \
  --task-timeout 3600 \
  --max-retries 1 \
  --parallelism 6 \
  --ephemeral-storage 10Gi \
  --set-env-vars SUPABASE_URL=...,SUPABASE_SERVICE_KEY=...,GCS_VIDEO_BUCKET=...,GCS_TRAINING_BUCKET=...
```

4. **Update Workflow** to trigger jobs instead of functions

---

## Alternative: Process Per Angle (Not Recommended)

You mentioned: "for each game we would use each job execution in order to download one angle make clips"

### Per-Angle Jobs Architecture:
```
Workflow triggers 24 jobs (6 games × 4 angles)
Job 1: Game A, Angle FAR_LEFT
Job 2: Game A, Angle NEAR_LEFT
Job 3: Game A, Angle FAR_RIGHT
Job 4: Game A, Angle NEAR_RIGHT
Job 5: Game B, Angle FAR_LEFT
... (24 total)

Final step: 6 JSONL generation jobs
```

**Pros:**
- Simpler per-job logic
- Even smaller storage needs (just 1 angle)
- Maximum parallelization (24 concurrent)

**Cons:**
- ❌ More complex workflow (24 triggers + 6 JSONL jobs)
- ❌ More coordination needed
- ❌ 30 total jobs vs 6 jobs
- ❌ More cold starts
- ❌ Need to coordinate JSONL generation after all angles complete
- ❌ More workflow logic complexity

**Verdict**: Not worth the added complexity. Processing 4 angles sequentially in one job is fast enough (8-10 min) and much simpler.

---

## My Recommendation

### Immediate Action (Today):
**1. Redeploy Cloud Function with 10GB ephemeral storage**
```bash
cd functions/extract-clips-cf

gcloud functions deploy extract-clips-game \
  --gen2 \
  --runtime python311 \
  --region us-central1 \
  --source . \
  --entry-point extract_clips_game \
  --memory 8GB \
  --timeout 3600 \
  --max-instances 40 \
  --env-vars-file .env.yaml \
  --ephemeral-storage 10GB
```

**2. Test immediately**
- Start workflow with 6 games
- Should see all 6 processing in parallel
- Should complete in 8-10 minutes total

### If That Doesn't Work:
**3. Migrate to Cloud Run Jobs**
- Better resource control
- More reliable for batch processing
- Purpose-built for this use case

---

## Summary Table

| Feature | Cloud Functions | Cloud Functions + Storage | Cloud Run Jobs |
|---------|----------------|--------------------------|----------------|
| **Storage** | 512MB (default) | 10GB | 10GB |
| **Parallel Games** | ❌ (failing) | ✅ (6 parallel) | ✅ (6 parallel) |
| **Speed** | 60+ min (1 game) | 10 min (6 games) | 8 min (6 games) |
| **Cost** | $0.008/game | $0.008/game | $0.005/game |
| **Complexity** | Low | Low | Medium |
| **Reliability** | Low (storage issue) | High | High |
| **Setup Time** | Done | 5 minutes | 1 hour |

---

## Decision Matrix

### Use Cloud Functions + 10GB Storage If:
✅ You want the fastest fix (5-minute deploy)
✅ Current code works with more storage
✅ HTTP triggering is important
✅ You want to keep existing workflow

### Use Cloud Run Jobs If:
✅ You want better resource control
✅ You need even longer processing time (24hr limit)
✅ You want cheaper execution
✅ You need persistent storage options
✅ You want purpose-built batch processing

---

## Next Steps

1. **Check current function logs** to confirm storage issue
2. **Redeploy function with 10GB storage** (5-minute fix)
3. **Test with 6 games** to verify parallel execution
4. **If successful**, document and done
5. **If still slow**, migrate to Cloud Run Jobs

Would you like me to:
- Redeploy the function with proper storage NOW?
- Check the logs to confirm the storage issue?
- Start migrating to Cloud Run Jobs instead?
