# Basketball Training Pipeline - Workflow Architecture

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Data Flow](#data-flow)
4. [Detailed Component Breakdown](#detailed-component-breakdown)
5. [Performance Optimizations](#performance-optimizations)
6. [Error Handling & Resilience](#error-handling--resilience)
7. [API Contracts](#api-contracts)
8. [Sequence Diagrams](#sequence-diagrams)
9. [File Structure](#file-structure)
10. [Cost & Scale Considerations](#cost--scale-considerations)

---

## System Overview

### Purpose
Automated pipeline to extract basketball play clips from full game videos, annotate them, and generate training data in JSONL format for Vertex AI model fine-tuning.

### High-Level Flow
```
Game Videos (GCS) + Play Metadata (Supabase)
    ↓
Cloud Workflows (Orchestrator)
    ↓
Cloud Functions (6 parallel instances)
    ↓
Training Data (GCS) → Vertex AI Training
```

### Key Metrics
- **Input**: 6 games, ~4 hours each, ~10GB per game
- **Output**: ~200 clips per game, 2 angles each = 400 clips
- **Processing Time**: 5-10 minutes per game (optimized)
- **Previous Time**: 60-90 minutes per game (unoptimized)
- **Improvement**: ~10x speedup via video download optimization

---

## Architecture Components

### 1. Cloud Workflows (`workflows/basketball-training-pipeline.yaml`)
**Role**: Orchestration and coordination
**Location**: `us-central1`
**Timeout**: 2 hours (7200s)

**Key Features**:
- Fire-and-forget pattern for function invocation
- Polling-based completion detection
- Parallel game processing (up to 6 games simultaneously)
- Automatic retry logic

### 2. Cloud Function (`functions/extract-clips-cf/`)
**Name**: `extract-clips-game`
**Runtime**: Python 3.11
**Memory**: 8GB
**Timeout**: 3600s (1 hour)
**Max Instances**: 40
**Region**: `us-central1`

**Responsibilities**:
1. Fetch play metadata from Supabase
2. Download game videos from GCS (once per angle)
3. Extract clips using ffmpeg
4. Upload clips to GCS
5. Generate JSONL training files (80/20 train/validation split)

### 3. Data Sources

#### Supabase (PostgreSQL Database)
**URL**: `https://mhbrsftxvxxtfgbajrlc.supabase.co`
**Table**: `plays`

**Schema**:
```sql
CREATE TABLE plays (
    id UUID PRIMARY KEY,
    game_id UUID NOT NULL,
    angle TEXT NOT NULL,  -- 'LEFT' or 'RIGHT'
    start_timestamp FLOAT NOT NULL,  -- seconds
    end_timestamp FLOAT NOT NULL,    -- seconds
    play_type TEXT,
    -- other metadata fields
);
```

#### Google Cloud Storage

**Video Bucket**: `uball-videos-production`
```
uball-videos-production/
└── Games/
    └── {game_id}/
        ├── FAR_LEFT.mp4
        ├── NEAR_LEFT.mp4
        ├── FAR_RIGHT.mp4
        └── NEAR_RIGHT.mp4
```

**Training Bucket**: `uball-training-data`
```
uball-training-data/
└── games/
    └── {game_id}/
        ├── clips/
        │   └── {play_id}_{angle}.mp4
        ├── training_data.jsonl (80%)
        └── validation_data.jsonl (20%)
```

---

## Data Flow

### Phase 1: Initialization (Workflow)
```
1. Workflow receives: {"game_ids": ["game1", "game2", ...]}
2. Validates input (game_ids is array)
3. For each game_id in parallel:
   ├── Triggers Cloud Function (HTTP POST with game_id)
   └── Sets 10s timeout (fire-and-forget)
```

### Phase 2: Processing (Cloud Function)
```
For each game:
1. Query Supabase for plays
   ├── SELECT * FROM plays WHERE game_id = ?
   └── Get: play_id, angle, start_timestamp, end_timestamp

2. Group clips by source video angle
   ├── LEFT plays → FAR_LEFT + NEAR_RIGHT videos
   └── RIGHT plays → FAR_RIGHT + NEAR_LEFT videos

3. For each unique video angle:
   ├── Download video ONCE from GCS
   ├── Extract ALL clips from that video locally using ffmpeg
   ├── Upload all clips to GCS
   └── Delete local video file

4. Generate JSONL files
   ├── 80% → training_data.jsonl
   └── 20% → validation_data.jsonl

5. Upload JSONL to GCS (this signals completion)
```

### Phase 3: Polling (Workflow)
```
While not all games complete (max 2 hours):
1. Every 30 seconds:
   ├── Check GCS for {game_id}/training_data.jsonl
   ├── Check GCS for {game_id}/validation_data.jsonl
   └── Mark game complete if both exist

2. If all games complete:
   └── Workflow succeeds

3. If timeout (2 hours):
   └── Workflow fails with incomplete games listed
```

---

## Detailed Component Breakdown

### Workflow Structure

#### Main Workflow Steps
```yaml
1. validate_input
   - Ensures game_ids is array
   - Stores game count

2. init_tracking
   - Creates completion tracking map
   - game_id → {training: false, validation: false}

3. parallel_trigger (forEach loop)
   - For each game_id in parallel:
     ├── trigger_function (try/except)
     │   ├── HTTP POST to function URL
     │   ├── Body: {"game_id": "..."}
     │   └── Timeout: 10s (just to start)
     └── log_trigger (exception ignored)

4. wait_for_all_games
   - Calls poll_games_completion subworkflow

5. return_results
   - Returns final completion status
```

#### Polling Subworkflow
```yaml
poll_games_completion:
  Args: game_ids, max_wait_minutes

  Logic:
    1. init_polling
       - Start time
       - Completed games = []

    2. polling_loop (while loop)
       - For each game_id:
         ├── check_game_files (HTTP GET to GCS)
         │   ├── List files in gs://bucket/games/{game_id}/
         │   └── Look for *.jsonl files
         ├── Update tracking if found
         └── Add to completed_games

       - If all games complete:
         └── Exit loop (SUCCESS)

       - If timeout exceeded:
         └── Exit loop (TIMEOUT)

       - Wait 30 seconds before next poll

    3. return_status
       - completed_games
       - pending_games
       - total_time
```

### Cloud Function Architecture

#### Entry Point (`main.py`)
```python
@functions_framework.http
def extract_clips_game(request):
    """HTTP endpoint triggered by workflow"""

    # 1. Parse request
    game_id = request.get_json()["game_id"]

    # 2. Initialize processor
    processor = ClipExtractor(
        game_id=game_id,
        supabase_url=os.environ["SUPABASE_URL"],
        supabase_key=os.environ["SUPABASE_SERVICE_KEY"],
        video_bucket=os.environ["GCS_VIDEO_BUCKET"],
        training_bucket=os.environ["GCS_TRAINING_BUCKET"]
    )

    # 3. Process
    result = processor.process_game()

    # 4. Return
    return jsonify(result), 200
```

#### Core Processing Logic (`extract_clips_job.py`)

**Class: ClipExtractor**

**Key Methods**:

1. **`process_game()`** - Main orchestrator
```python
def process_game(self) -> Dict[str, Any]:
    """Main processing pipeline"""

    # Fetch plays from Supabase
    plays = self._fetch_plays_from_supabase()

    # Extract clips (OPTIMIZED)
    clip_results = self.extract_all_clips(plays)

    # Generate JSONL
    jsonl_results = self._create_training_jsonl(plays, clip_results)

    return {
        "game_id": self.game_id,
        "total_plays": len(plays),
        "successful_clips": clip_results["successful"],
        "failed_clips": clip_results["failed"],
        "jsonl_files": jsonl_results
    }
```

2. **`extract_all_clips(plays)`** - CRITICAL OPTIMIZATION
```python
def extract_all_clips(self, plays: List[Dict]) -> Dict:
    """Extract clips - OPTIMIZED to download each video ONCE"""

    # STEP 1: Group clips by source video
    clips_by_video = {}
    # Example: {
    #   "FAR_LEFT": [(play1, ts1, ts2, out1), (play2, ts1, ts2, out2)],
    #   "NEAR_RIGHT": [(play3, ts1, ts2, out3), ...]
    # }

    for play in plays:
        training_angles = self._get_training_angles(play["angle"])
        for angle in training_angles:
            if angle not in clips_by_video:
                clips_by_video[angle] = []
            clips_by_video[angle].append(
                (play["id"], play["start_timestamp"],
                 play["end_timestamp"], output_path)
            )

    # STEP 2: Process each video ONCE
    for angle, clips in clips_by_video.items():
        logger.info(f"🎥 Processing {angle}: {len(clips)} clips")

        # Download video ONCE
        temp_video = self.temp_dir / f"{angle}_{os.getpid()}.mp4"
        video_gcs_path = f"Games/{self.game_id}/{angle}.mp4"
        blob = self.video_bucket.blob(video_gcs_path)
        blob.download_to_filename(str(temp_video))
        logger.info(f"✅ Downloaded {angle}")

        # Extract ALL clips from this video
        for play_id, start_ts, end_ts, output_path in clips:
            self._extract_clip_from_local_video(
                str(temp_video), start_ts, end_ts, output_path
            )

        # Delete temp video
        temp_video.unlink()
        logger.info(f"🗑️  Deleted temp video: {angle}")

    return {"successful": success_count, "failed": fail_count}
```

3. **`_extract_clip_from_local_video()`** - ffmpeg wrapper
```python
def _extract_clip_from_local_video(
    self, local_video_path: str,
    start_timestamp: float,
    end_timestamp: float,
    output_gcs_path: str
) -> bool:
    """Extract clip from already-downloaded local video"""

    duration = end_timestamp - start_timestamp
    temp_clip = self.temp_dir / f"clip_{os.getpid()}_{start_timestamp}.mp4"

    try:
        # ffmpeg extraction
        cmd = [
            "ffmpeg",
            "-ss", str(start_timestamp),      # Start time
            "-i", local_video_path,           # Input (LOCAL file)
            "-t", str(duration),              # Duration
            "-c:v", "libx264",                # Video codec
            "-preset", "ultrafast",           # Speed preset
            "-crf", "23",                     # Quality
            "-c:a", "aac",                    # Audio codec
            "-y",                             # Overwrite
            str(temp_clip)
        ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=60)

        # Upload to GCS
        blob = self.training_bucket.blob(output_gcs_path)
        blob.upload_from_filename(str(temp_clip))

        return True

    except Exception as e:
        logger.error(f"❌ Clip extraction error: {e}")
        return False

    finally:
        if temp_clip.exists():
            temp_clip.unlink()
```

4. **`_create_training_jsonl()`** - JSONL generation
```python
def _create_training_jsonl(
    self, plays: List[Dict], clip_results: Dict
) -> Dict[str, str]:
    """Generate training and validation JSONL files"""

    # 80/20 split
    random.shuffle(plays)
    split_idx = int(len(plays) * 0.8)
    training_plays = plays[:split_idx]
    validation_plays = plays[split_idx:]

    # Generate JSONL entries
    training_jsonl = []
    for play in training_plays:
        for angle in self._get_training_angles(play["angle"]):
            gcs_url = f"gs://{self.training_bucket}/games/{self.game_id}/clips/{play['id']}_{angle}.mp4"
            training_jsonl.append({
                "videoGcsUri": gcs_url,
                "textPrompt": "Basketball play annotation..."
            })

    # Upload to GCS
    training_path = f"games/{self.game_id}/training_data.jsonl"
    validation_path = f"games/{self.game_id}/validation_data.jsonl"

    # Write files
    self._upload_jsonl(training_jsonl, training_path)
    self._upload_jsonl(validation_jsonl, validation_path)

    return {
        "training": f"gs://{self.training_bucket}/{training_path}",
        "validation": f"gs://{self.training_bucket}/{validation_path}"
    }
```

5. **`_get_training_angles()`** - Angle mapping logic
```python
def _get_training_angles(self, play_angle: str) -> List[str]:
    """Map play angle to camera angles for training"""

    # LEFT plays → FAR_LEFT + NEAR_RIGHT cameras
    # RIGHT plays → FAR_RIGHT + NEAR_LEFT cameras

    if play_angle == "LEFT":
        return ["FAR_LEFT", "NEAR_RIGHT"]
    elif play_angle == "RIGHT":
        return ["FAR_RIGHT", "NEAR_LEFT"]
    else:
        raise ValueError(f"Unknown angle: {play_angle}")
```

---

## Performance Optimizations

### Critical Optimization: Video Download Strategy

#### Problem (Original Implementation)
```python
# OLD CODE (INEFFICIENT)
def _extract_clip_streaming(video_path, start, end, output):
    # ❌ Downloads FULL video for EVERY clip
    blob.download_to_filename(temp_video)  # 10GB download
    # Extract 1 clip
    ffmpeg.extract(temp_video, start, end, temp_clip)
    # Upload 1 clip
    blob.upload(temp_clip, output)
    # Delete temp files
```

**Impact**:
- 100 plays × 2 angles = 200 clips needed
- Each clip triggers separate video download
- 200 downloads × 10GB = **2TB downloaded per game**
- Time: 60-90 minutes per game

#### Solution (Optimized Implementation)
```python
# NEW CODE (OPTIMIZED)
def extract_all_clips(plays):
    # Group by video first
    clips_by_video = group_by_angle(plays)

    for angle, clips in clips_by_video.items():
        # ✅ Download video ONCE
        blob.download_to_filename(temp_video)

        # ✅ Extract ALL clips from this video
        for clip in clips:
            ffmpeg.extract(temp_video, start, end, output)
            blob.upload(output)

        # ✅ Delete temp video
        temp_video.unlink()
```

**Impact**:
- 4 unique videos (FAR_LEFT, NEAR_LEFT, FAR_RIGHT, NEAR_RIGHT)
- 4 downloads × 10GB = **40GB downloaded per game**
- Time: 5-10 minutes per game
- **100x bandwidth reduction, 10x speed improvement**

### Other Optimizations

1. **Parallel Game Processing**
   - Cloud Workflows triggers all 6 games simultaneously
   - Cloud Functions scale to 40 instances
   - 6 games process in parallel

2. **Fire-and-Forget Pattern**
   - Workflow doesn't wait for HTTP response
   - 10s timeout just to start function
   - Function continues in background

3. **Polling vs Callbacks**
   - Simple polling every 30s
   - No need for webhooks or pub/sub
   - JSONL file creation signals completion

4. **ffmpeg Optimization**
   - `preset: ultrafast` - fastest encoding
   - `crf: 23` - good quality/size balance
   - Direct file operations (no streaming)

---

## Error Handling & Resilience

### Workflow Level

1. **Function Trigger Failures**
```yaml
trigger_function:
  try:
    call: http.post
  except:
    as: e
    steps:
      - log_trigger_note:
          # ⏱️ Function triggered, will poll for completion
          # Exception is expected and ignored
```

2. **Timeout Protection**
```yaml
max_wait_minutes: 120  # 2 hours total
# Workflow will fail if any game exceeds this
```

3. **Completion Detection**
```yaml
# Only marks complete if BOTH files exist:
- gs://bucket/games/{game_id}/training_data.jsonl
- gs://bucket/games/{game_id}/validation_data.jsonl
```

### Function Level

1. **Supabase Query Failures**
```python
try:
    plays = supabase.table("plays").select("*").eq("game_id", game_id).execute()
except Exception as e:
    logger.error(f"Failed to fetch plays: {e}")
    return {"error": "supabase_error"}, 500
```

2. **Video Download Failures**
```python
try:
    blob.download_to_filename(temp_video)
except Exception as e:
    logger.error(f"Failed to download {angle}: {e}")
    # Skip this angle, continue with others
    continue
```

3. **Clip Extraction Failures**
```python
try:
    subprocess.run(ffmpeg_cmd, timeout=60)
except subprocess.TimeoutExpired:
    logger.error(f"ffmpeg timeout for clip {play_id}")
    # Mark clip as failed, continue with next
    failed_clips.append(play_id)
```

4. **Partial Success Handling**
```python
# Function returns success even if some clips fail
# JSONL only includes successful clips
return {
    "status": "completed",
    "successful_clips": 180,
    "failed_clips": 20  # Still returns 200 OK
}
```

---

## API Contracts

### Workflow → Cloud Function

**Endpoint**: `https://extract-clips-game-{hash}-uc.a.run.app`

**Request**:
```http
POST / HTTP/1.1
Content-Type: application/json

{
  "game_id": "23135de8-36ca-4882-bdf1-8796cd8caa8a"
}
```

**Response** (not actually used by workflow):
```json
{
  "status": "processing",
  "game_id": "23135de8-36ca-4882-bdf1-8796cd8caa8a",
  "message": "Processing started"
}
```

### Supabase API

**Query**:
```sql
SELECT id, game_id, angle, start_timestamp, end_timestamp
FROM plays
WHERE game_id = ?
ORDER BY start_timestamp ASC
```

**Response**:
```json
{
  "data": [
    {
      "id": "157c4f80-493e-42fc-aaf1-71c545aedd18",
      "game_id": "23135de8-36ca-4882-bdf1-8796cd8caa8a",
      "angle": "LEFT",
      "start_timestamp": 123.45,
      "end_timestamp": 145.67
    }
  ]
}
```

### JSONL Format (Vertex AI)

**Structure**:
```jsonl
{"videoGcsUri": "gs://bucket/path/to/clip.mp4", "textPrompt": "annotation"}
{"videoGcsUri": "gs://bucket/path/to/clip2.mp4", "textPrompt": "annotation"}
```

**Example**:
```jsonl
{"videoGcsUri": "gs://uball-training-data/games/23135de8.../clips/157c4f80..._FAR_LEFT.mp4", "textPrompt": "Basketball offensive play from left side with 2 players"}
{"videoGcsUri": "gs://uball-training-data/games/23135de8.../clips/157c4f80..._NEAR_RIGHT.mp4", "textPrompt": "Basketball offensive play from left side with 2 players"}
```

---

## Sequence Diagrams

### End-to-End Flow
```
User                Workflow            Cloud Function       Supabase        GCS
 |                     |                      |                |             |
 | 1. Start workflow   |                      |                |             |
 |-------------------->|                      |                |             |
 |                     |                      |                |             |
 |                     | 2. For each game_id: |                |             |
 |                     |   POST /game_id      |                |             |
 |                     |--------------------->|                |             |
 |                     |   (10s timeout)      |                |             |
 |                     |                      |                |             |
 |                     |                      | 3. Query plays |             |
 |                     |                      |--------------->|             |
 |                     |                      |<---------------|             |
 |                     |                      |                |             |
 |                     |                      | 4. Download video            |
 |                     |                      |----------------|------------>|
 |                     |                      |<---------------|-------------|
 |                     |                      |                |             |
 |                     |                      | 5. Extract clips             |
 |                     |                      | (local ffmpeg) |             |
 |                     |                      |                |             |
 |                     |                      | 6. Upload clips|             |
 |                     |                      |----------------|------------>|
 |                     |                      |                |             |
 |                     |                      | 7. Upload JSONL              |
 |                     |                      |----------------|------------>|
 |                     |                      |                |             |
 |                     | 8. Poll GCS (every 30s)               |             |
 |                     |---------------------------------------|------------>|
 |                     |<--------------------------------------|-------------|
 |                     |    (check for JSONL files)            |             |
 |                     |                      |                |             |
 |                     | 9. All complete      |                |             |
 | 10. Success         |                      |                |             |
 |<--------------------|                      |                |             |
```

### Detailed Clip Extraction Flow
```
Function                    GCS Video Bucket         Local Disk          GCS Training Bucket
   |                              |                       |                      |
   | 1. Group clips by angle      |                       |                      |
   |----------------------------->|                       |                      |
   |                              |                       |                      |
   | 2. Download FAR_LEFT.mp4     |                       |                      |
   |----------------------------->|                       |                      |
   |                              |--------download------>|                      |
   |                              |                       |                      |
   | 3. Extract clip 1            |                       |                      |
   |                              |                       | ffmpeg               |
   |                              |                       |----extract--->clip1  |
   |                              |                       |                      |
   | 4. Upload clip 1             |                       |                      |
   |----------------------------------------------------------upload----------->|
   |                              |                       |                      |
   | 5. Extract clip 2            |                       |                      |
   |                              |                       | ffmpeg               |
   |                              |                       |----extract--->clip2  |
   |                              |                       |                      |
   | 6. Upload clip 2             |                       |                      |
   |----------------------------------------------------------upload----------->|
   |                              |                       |                      |
   | ... (repeat for all clips)   |                       |                      |
   |                              |                       |                      |
   | N. Delete FAR_LEFT.mp4       |                       |                      |
   |                              |                       |<----delete-----------|
   |                              |                       |                      |
   | N+1. Download NEAR_RIGHT.mp4 |                       |                      |
   |----------------------------->|                       |                      |
   |                              |--------download------>|                      |
   |                              |                       |                      |
   | ... (repeat extraction)      |                       |                      |
```

---

## File Structure

```
Uball_basketball-annotation-pipeline/
│
├── workflows/
│   └── basketball-training-pipeline.yaml      # Main orchestration workflow
│
├── functions/
│   └── extract-clips-cf/
│       ├── main.py                            # HTTP entry point
│       ├── jobs/
│       │   └── extract-clips/
│       │       ├── extract_clips_job.py       # Core processing logic
│       │       └── main.py                    # Job wrapper
│       ├── requirements.txt                   # Python dependencies
│       ├── .env.yaml                          # Environment config
│       └── deploy.sh                          # Deployment script
│
├── scripts/
│   ├── check-supabase-games.py               # Verify game data
│   ├── trigger-workflow.sh                   # Manual workflow trigger
│   └── check-workflow-status.sh              # Monitor workflow
│
├── DEPLOYMENT_GUIDE.md                        # Deployment instructions
├── WORKFLOW_ARCHITECTURE.md                   # This document
└── README.md                                  # Project overview
```

---

## Cost & Scale Considerations

### Current Scale
- **Games**: 6 games per batch
- **Plays**: ~100 plays per game
- **Clips**: ~200 clips per game (2 angles each)
- **Video Size**: ~10GB per game video
- **Processing Time**: 5-10 minutes per game

### Cost Breakdown (Estimated per batch)

1. **Cloud Functions**
   - 6 instances × 8GB × 10 minutes = 480 GB-minutes
   - Cost: ~$0.05 per batch

2. **Cloud Workflows**
   - 1 execution × 120 minutes = 120 minutes
   - Cost: ~$0.01 per batch

3. **Cloud Storage**
   - Download: 40GB per game × 6 = 240GB
   - Upload: 2GB clips per game × 6 = 12GB
   - Cost: ~$0.05 per batch

4. **Supabase**
   - Database queries: Free tier

**Total Cost**: ~$0.11 per batch (6 games)

### Scaling Limits

1. **Cloud Functions**
   - Max instances: 40 (configured)
   - Can scale to 1000+ if needed
   - Bottleneck: GCS bandwidth

2. **Cloud Workflows**
   - Max parallel steps: 1000
   - Max execution time: 365 days
   - Current: 6 parallel + 2 hour timeout

3. **GCS**
   - Bandwidth: ~5Gbps per region
   - Can handle 100+ concurrent downloads

### Optimization Opportunities

1. **Multi-region deployment**
   - Deploy functions in multiple regions
   - Use regional buckets

2. **Batch processing**
   - Process 100+ games per batch
   - Increase workflow timeout

3. **Video format optimization**
   - Use H.265 instead of H.264
   - Reduce video quality if acceptable

4. **Caching**
   - Cache downloaded videos across functions
   - Use Cloud CDN for video distribution

---

## Key Design Decisions

### 1. Fire-and-Forget vs Synchronous
**Chosen**: Fire-and-Forget
**Rationale**:
- Cloud Functions can run for 1 hour
- Workflow timeout is 10 minutes for HTTP calls
- Polling is simpler than webhooks/pub-sub

### 2. Polling vs Event-Driven
**Chosen**: Polling
**Rationale**:
- Simple to implement
- No need for pub/sub infrastructure
- 30s polling is sufficient (not real-time)
- JSONL file creation is natural completion signal

### 3. Download Once vs Stream Processing
**Chosen**: Download Once
**Rationale**:
- 100x bandwidth reduction
- 10x speed improvement
- Disk space is cheap (8GB memory available)
- ffmpeg works better with local files

### 4. JSONL vs Database Storage
**Chosen**: JSONL
**Rationale**:
- Vertex AI requires JSONL format
- Directly consumable by training job
- No additional ETL needed

### 5. Parallel vs Sequential Game Processing
**Chosen**: Parallel
**Rationale**:
- 6x speedup (6 games in 10 min vs 60 min)
- Cloud Functions auto-scale
- No resource contention

---

## Monitoring & Observability

### Key Metrics to Monitor

1. **Workflow Metrics**
   - Execution time
   - Success rate
   - Games per batch

2. **Function Metrics**
   - Invocation count
   - Error rate
   - Memory usage
   - Execution time

3. **Data Metrics**
   - Clips per game
   - Failed clips
   - JSONL file size

### Logging Strategy

1. **Workflow Logs**
```yaml
- log_progress:
    call: sys.log
    args:
      data: '${"Processing game " + game_id}'
```

2. **Function Logs**
```python
logger.info(f"🎬 Starting clip extraction for {len(plays)} plays")
logger.info(f"📊 Organized {total_clips} clips across {len(videos)} videos")
logger.info(f"🎥 Processing {angle}: {len(clips)} clips")
logger.info(f"✅ Downloaded {angle} ({size_mb:.1f} MB)")
logger.info(f"🗑️ Deleted temp video: {angle}")
```

3. **Error Logs**
```python
logger.error(f"❌ Failed to download video {angle}: {error}")
logger.error(f"❌ Clip extraction failed for {play_id}: {error}")
```

### Dashboard Queries (Cloud Logging)

**Function execution time**:
```
resource.type="cloud_run_revision"
resource.labels.service_name="extract-clips-game"
severity>=INFO
"Processing game"
```

**Clip extraction progress**:
```
resource.type="cloud_run_revision"
"Downloaded" OR "clips to extract"
```

**Errors**:
```
resource.type="cloud_run_revision"
severity>=ERROR
```

---

## Troubleshooting Guide

### Issue: Workflow times out after 2 hours
**Cause**: Games taking too long to process
**Solution**:
- Check function logs for errors
- Verify video download optimization is working
- Increase timeout if needed

### Issue: No clips being created
**Cause**: Supabase query returning no plays
**Solution**:
- Verify game_id exists in Supabase
- Check plays table has data for that game
- Verify Supabase credentials

### Issue: Function returns 400 error
**Cause**: Invalid request format
**Solution**:
- Verify game_id is in request body
- Check function logs for specific error

### Issue: JSONL files not created
**Cause**: All clips failed to extract
**Solution**:
- Check video files exist in GCS
- Verify ffmpeg is working
- Check for disk space issues

### Issue: Slow processing (60+ minutes per game)
**Cause**: Download optimization not working
**Solution**:
- Verify using latest function revision
- Check logs for "Downloaded {angle}" messages
- Should see 4 downloads per game, not 200+

---

## Security Considerations

### Secrets Management
- Supabase key stored in `.env.yaml` (NOT committed to git)
- Environment variables injected at deployment
- Service account uses IAM roles (no keys)

### Access Control
- Cloud Function uses service account: `basketball-training-sa@...`
- Service account has roles:
  - `storage.admin` (GCS access)
  - `logging.admin` (write logs)
  - `aiplatform.admin` (Vertex AI access)

### Network Security
- Functions run in VPC (if configured)
- Supabase accessed over HTTPS
- GCS accessed via private Google network

---

## Future Enhancements

1. **Real-time Progress Updates**
   - Use Cloud Pub/Sub for events
   - WebSocket for live progress

2. **Advanced Retry Logic**
   - Retry failed clips automatically
   - Exponential backoff

3. **Quality Validation**
   - Verify clip quality before upload
   - Detect corrupted videos

4. **Auto-Scaling Based on Queue**
   - Use Cloud Tasks for job queue
   - Scale functions based on queue depth

5. **Multi-region Deployment**
   - Deploy to multiple regions
   - Route based on video location

6. **Cost Optimization**
   - Use Spot instances
   - Compress videos before upload
   - Use cheaper storage classes

---

## Appendix

### Environment Variables
```yaml
SUPABASE_URL: "https://mhbrsftxvxxtfgbajrlc.supabase.co"
SUPABASE_SERVICE_KEY: "eyJhbGci..."  # JWT service role key
GCS_VIDEO_BUCKET: "uball-videos-production"
GCS_TRAINING_BUCKET: "uball-training-data"
```

### Service Account
```
basketball-training-sa@refined-circuit-474617-s8.iam.gserviceaccount.com
```

### Key URLs
- **Function URL**: `https://extract-clips-game-m5owpfulcq-uc.a.run.app`
- **Video Bucket**: `gs://uball-videos-production`
- **Training Bucket**: `gs://uball-training-data`

### Dependencies
```txt
functions-framework==3.*
google-cloud-storage
supabase
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-29
**Author**: Basketball Training Pipeline Team
