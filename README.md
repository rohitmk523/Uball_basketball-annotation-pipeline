# 🏀 Basketball AI Annotation System

**Production-ready AI system for automated basketball video analysis using fine-tuned Vertex AI (Gemini 2.5 Flash) with hybrid cloud architecture.**

> 🚀 **NEW: V2 Architecture Available!**
> We've rebuilt the training pipeline with Cloud Functions for **10x faster, more reliable processing**.
> See [ARCHITECTURE_V2_SUMMARY.md](ARCHITECTURE_V2_SUMMARY.md) and [DEPLOYMENT_GUIDE_V2.md](DEPLOYMENT_GUIDE_V2.md)

## 🎯 Quick Overview

**Input:** Basketball game videos from GCS
**Output:** Structured play annotations with 4-point line support
**Performance:** Continuous learning with incremental training
**Architecture:** Cloud Functions + Workflows + Vertex AI (V2) or Cloud Run Jobs (V1)

---

## 🏗️ System Architecture

### **V2 Architecture (Recommended - 10x Faster)**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Workflow       │───▶│ Cloud Functions │───▶│   Vertex AI     │
│  (Trigger)      │    │ (Parallel x40)  │    │  (ML Training)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐    ┌─────────────────┐
         └──────────────│ Supabase DB     │    │      GCS        │
                        │ (Plays Data)    │    │  (Video/Data)   │
                        └─────────────────┘    └─────────────────┘
```

- ✅ **Parallel processing** of 40 games simultaneously
- ✅ **15-25 minutes** for 40 games (vs 3-4 hours in V1)
- ✅ **Better reliability** with isolated failures
- ✅ **Superior logging** in Cloud Logging

See: [ARCHITECTURE_V2_SUMMARY.md](ARCHITECTURE_V2_SUMMARY.md)

### **V1 Architecture (Legacy - Sequential Processing)**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client API    │───▶│  Cloud Workflow │───▶│   Cloud Run     │───▶│   Vertex AI     │
│   (FastAPI)     │    │  (Orchestrator) │    │   (Jobs)        │    │  (ML Training)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │              ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
         │              │ Cloud Function  │    │      GCS        │    │   Persistent    │
         └──────────────│  (DB Export)    │    │  (Video/Data)   │    │   Endpoints     │
                        └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Component Breakdown**

#### 1. **API Layer (FastAPI)**
- RESTful endpoints for training pipeline
- Real-time progress tracking
- Configuration management
- Error handling and logging

#### 2. **Orchestration (Cloud Workflows)**
- End-to-end pipeline coordination
- Error handling and retries
- State management
- Progress monitoring

#### 3. **Data Export (Cloud Function)**
- Fast database queries (2-3 seconds)
- Export plays from Supabase
- Split training/validation data (80/20)
- Generate GCS file paths

#### 4. **Video Processing (Cloud Run Jobs)**
- Extract video clips from basketball games
- Create Vertex AI JSONL training files
- Support for multiple camera angles
- Smart skipping for existing data

#### 5. **AI Training (Vertex AI)**
- Fine-tune Gemini 2.5 Flash models
- Incremental learning approach
- UBALL 4-point line support
- Automatic model deployment

---

## 🔄 Training Process Flow

### **Step-by-Step Process**

```
🎯 START: Training Request
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Database Export (Cloud Function)                                       │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│ │ Query Supabase  │─▶│ Split 80/20     │─▶│ Export to GCS   │                 │
│ │ for game plays  │  │ Train/Validate  │  │ as JSON files   │                 │
│ └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│ ⏱️ Duration: ~3 seconds                                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Video Processing (Cloud Run Job)                                       │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│ │ Extract Clips   │─▶│ Multi-Angle     │─▶│ Create JSONL    │                 │
│ │ from Full Game  │  │ Processing      │  │ Training Files  │                 │
│ │ Videos (GCS)    │  │ (FAR_LEFT, etc) │  │ (Vertex AI)     │                 │
│ └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│ ⏱️ Duration: ~5-10 minutes                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Model Training (Vertex AI)                                             │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│ │ Incremental     │─▶│ Fine-tune       │─▶│ Validate Model  │                 │
│ │ Training Setup  │  │ Gemini 2.5      │  │ Performance     │                 │
│ │ (Base Model)    │  │ Flash Model     │  │ (Validation)    │                 │
│ └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│ ⏱️ Duration: ~10-15 minutes                                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Model Deployment (Persistent Endpoint)                                 │
│ ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│ │ Deploy to       │─▶│ Update Traffic  │─▶│ Model Ready     │                 │
│ │ Persistent      │  │ Split (100%)    │  │ for Inference   │                 │
│ │ Endpoint        │  │ to New Model    │  │ (API Access)    │                 │
│ └─────────────────┘  └─────────────────┘  └─────────────────┘                 │
│ ⏱️ Duration: ~2-3 minutes                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
🎉 COMPLETE: Model Deployed & Ready
```

---

## 🧠 AI Training Deep Dive

### **Incremental Learning Strategy**

```
🏀 Training Philosophy: Continuous Learning
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  Game 1: Base Model (Gemini 2.5 Flash)                                        │
│     │                                                                           │
│     ▼                                                                           │
│  ┌─────────────────┐                                                           │
│  │ basketball-     │  ←─── First training creates foundation model              │
│  │ model-v1-1games │                                                           │
│  └─────────────────┘                                                           │
│     │                                                                           │
│     ▼                                                                           │
│  Game 2-5: Incremental Training                                                │
│     │                                                                           │
│     ▼                                                                           │
│  ┌─────────────────┐                                                           │
│  │ basketball-     │  ←─── Builds upon v1 with new game data                   │
│  │ model-v2-5games │                                                           │
│  └─────────────────┘                                                           │
│     │                                                                           │
│     ▼                                                                           │
│  Game 6-10: Advanced Training                                                  │
│     │                                                                           │
│     ▼                                                                           │
│  ┌─────────────────┐                                                           │
│  │ basketball-     │  ←─── Expert model with comprehensive knowledge           │
│  │ model-v3-10games│                                                           │
│  └─────────────────┘                                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### **JSONL Training Data Format**

Each basketball play is converted to Vertex AI format:

```json
{
  "contents": [
    {
      "role": "user",
      "parts": [
        {
          "fileData": {
            "fileUri": "gs://bucket/clips/play_FAR_LEFT.mp4",
            "mimeType": "video/mp4"
          }
        },
        {
          "text": "⚠️ CRITICAL: This is UBALL basketball with a 4-POINT LINE. Analyze this basketball video and identify the play with its events..."
        }
      ]
    },
    {
      "role": "model",
      "parts": [
        {
          "text": "[{\"timestamp_seconds\": 45.2, \"classification\": \"4PT_MAKE\", \"note\": \"Player shoots from beyond 4-point line\", \"player_a\": \"Player #23 (Blue Team)\"}]"
        }
      ]
    }
  ]
}
```

### **Multi-Angle Training**

- **FAR_LEFT** angle → Creates training examples for **FAR_LEFT** + **NEAR_RIGHT** views
- **FAR_RIGHT** angle → Creates training examples for **FAR_RIGHT** + **NEAR_LEFT** views
- Each camera angle becomes **separate training example** (Vertex AI requirement)
- Provides comprehensive court coverage and context

---

## 📦 S3 to GCS Migration

### **Migration Overview**

Before training, you may need to migrate basketball game videos from S3 to GCS. The migration script handles this seamlessly without quality loss.

```
📂 Migration Flow:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   S3 Bucket     │───▶│  Migration      │───▶│   GCS Bucket    │
│   (Source)      │    │  Script         │    │  (Training)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
s3://uball-videos-     Direct transfer       gs://uball-videos-
production/Games/      (no quality loss)     production/Games/
09-22-2025/game1/                            d6ba2cbb-da84-4614/
```

### **Setup Migration Environment**

```bash
# 1. Install migration dependencies
pip install -r requirements-migration.txt

# 2. Configure credentials (create .env.migration file)
cp .env.migration.example .env.migration
# Edit with your actual credentials:
```

**.env.migration** (create this file):
```bash
# S3 to GCS Migration Environment Variables
# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_S3_BUCKET=uball-videos-production
AWS_S3_REGION=us-east-1

# GCP Configuration
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
GCS_BUCKET=uball-videos-production
```

### **Migration Usage**

#### **Basic Migration**
```bash
# Migrate a single game
python scripts/migrate_s3_to_gcs.py \
  --s3-path "Games/09-22-2025/game1/" \
  --game-id "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"
```

#### **Advanced Migration with Custom Parameters**
```bash
# Full parameter migration
python scripts/migrate_s3_to_gcs.py \
  --s3-path "Games/09-22-2025/game1/" \
  --game-id "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab" \
  --aws-access-key "AKIA..." \
  --aws-secret-key "secret..." \
  --aws-bucket "uball-videos-production" \
  --aws-region "us-east-1" \
  --gcp-service-account "/path/to/service-account.json" \
  --gcs-bucket "uball-videos-production"
```

#### **Environment Variable Migration**
```bash
# Using environment variables (recommended)
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

python scripts/migrate_s3_to_gcs.py \
  --s3-path "Games/09-22-2025/game1/" \
  --game-id "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"
```

### **Migration Examples**

#### **Example 1: Single Game Migration**
```bash
# Source: s3://uball-videos-production/Games/09-22-2025/game1/
# Target: gs://uball-videos-production/Games/d6ba2cbb-da84-4614-82fc-ff58ba12d5ab/

python scripts/migrate_s3_to_gcs.py \
  --s3-path "Games/09-22-2025/game1/" \
  --game-id "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"

# Output:
# 🚀 Starting migration for game: d6ba2cbb-da84-4614-82fc-ff58ba12d5ab
# 🔍 Listing objects in s3://uball-videos-production/Games/09-22-2025/game1/
# 📊 Found 15 objects in S3
# 🔄 Migrating: s3://uball-videos-production/Games/09-22-2025/game1/FAR_LEFT.mp4
# ✅ Successfully migrated: Games/d6ba2cbb-da84-4614-82fc-ff58ba12d5ab/FAR_LEFT.mp4
# 🎉 Migration completed!
# 📊 Results: 15/15 files migrated (100.0%)
```

#### **Example 2: Multiple Game Migration (Batch)**
```bash
# Create a batch migration script
cat > migrate_multiple_games.sh << 'EOF'
#!/bin/bash

# Array of games to migrate
declare -A games=(
  ["Games/09-22-2025/game1/"]="d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"
  ["Games/09-22-2025/game2/"]="a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  ["Games/09-23-2025/game3/"]="f2e3d4c5-b6a7-8901-cdef-234567890abc"
)

for s3_path in "${!games[@]}"; do
  game_id="${games[$s3_path]}"
  echo "🔄 Migrating $s3_path -> $game_id"
  
  python scripts/migrate_s3_to_gcs.py \
    --s3-path "$s3_path" \
    --game-id "$game_id"
  
  if [ $? -eq 0 ]; then
    echo "✅ Successfully migrated $game_id"
  else
    echo "❌ Failed to migrate $game_id"
  fi
  echo "---"
done
EOF

chmod +x migrate_multiple_games.sh
./migrate_multiple_games.sh
```

### **Migration Features**

#### **🔄 What Gets Migrated**
- All video files (`.mp4`, `.mov`, etc.)
- Preserves original file structure within game directory
- Maintains file metadata and content type
- Zero quality loss (byte-for-byte copy)

#### **📊 Migration Output**
```json
{
  "success": true,
  "game_id": "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab",
  "source_path": "s3://uball-videos-production/Games/09-22-2025/game1/",
  "destination_path": "gs://uball-videos-production/Games/d6ba2cbb-da84-4614-82fc-ff58ba12d5ab/",
  "total_files": 15,
  "migrated_files": 15,
  "failed_files": 0,
  "success_rate": 100.0,
  "migrated_list": [
    {
      "source": "s3://uball-videos-production/Games/09-22-2025/game1/FAR_LEFT.mp4",
      "destination": "gs://uball-videos-production/Games/d6ba2cbb-da84-4614-82fc-ff58ba12d5ab/FAR_LEFT.mp4"
    }
  ]
}
```

#### **🔧 Migration Troubleshooting**

**AWS Credentials Error:**
```bash
# Error: AWS credentials required
# Solution: Set environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
```

**GCP Authentication Error:**
```bash
# Error: GCP service account not found
# Solution: Set service account path
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

**No Objects Found:**
```bash
# Error: No objects found in S3 path
# Solution: Check S3 path format (should end with /)
--s3-path "Games/09-22-2025/game1/"  # ✅ Correct
--s3-path "Games/09-22-2025/game1"   # ❌ Missing trailing slash
```

### **Post-Migration: Training**

After migration, use the basketball training pipeline:

```bash
# Train with migrated game
curl -X POST "http://localhost:8000/api/training/pipeline" \
  -H "Content-Type: application/json" \
  -d '{"game_ids": ["d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"]}'

# Train with multiple migrated games (cumulative training)
curl -X POST "http://localhost:8000/api/training/pipeline" \
  -H "Content-Type: application/json" \
  -d '{"game_ids": ["d6ba2cbb-da84-4614-82fc-ff58ba12d5ab", "a1b2c3d4-e5f6-7890-abcd-ef1234567890"]}'
```

---

## 🚀 Quick Start

### **Development Mode**
```bash
# 1. Clone and install
git clone <repository-url>
cd Uball_basketball-annotation-pipeline
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure for local development
cp .env.dev .env
# Update with your credentials

# 3. Start FastAPI
uvicorn app.main:app --reload --port 8000

# 4. Test training pipeline
curl -X POST "http://localhost:8000/api/training/pipeline" \
  -H "Content-Type: application/json" \
  -d '{"game_ids": ["your-game-id"]}'
```

### **Production Deployment**
```bash
# 1. Deploy hybrid infrastructure
./scripts/deployment/deploy_hybrid_training.sh

# 2. Configure for production
cp .env.hybrid .env
# Update with your credentials

# 3. Deploy FastAPI to Cloud Run
./scripts/deployment/deploy_to_cloud_run.sh
```

---

## 📋 API Endpoints

### **Training Pipeline**
- `POST /api/training/pipeline` - Start training for multiple games (cumulative)
- `GET /api/training/progress/{job_id}` - Real-time progress tracking
- `GET /api/training/status/{job_id}` - Job status and details
- `GET /api/training/config` - Current configuration
- `GET /api/training/jobs` - List all training jobs

### **Annotation Pipeline**  
- `POST /api/annotate` - Process game video
- `GET /api/jobs/{job_id}` - Job status
- `GET /api/plays/{game_id}` - Get annotations

---

## 🔧 Configuration

### **Environment Variables**
```bash
# Training Mode
TRAINING_MODE=local          # local = dev, hybrid = production

# GCP Configuration  
GCP_PROJECT_ID=your-project
GCS_TRAINING_BUCKET=your-bucket

# Supabase
SUPABASE_URL=your-url
SUPABASE_SERVICE_KEY=your-key
```

---

## 🏆 Benefits

### **For Clients**
- ✅ **Automated Processing**: No manual video annotation required
- ✅ **4-Point Line Support**: Specialized for UBALL basketball rules
- ✅ **Continuous Learning**: Model improves with each game
- ✅ **Fast Results**: Complete pipeline in ~20 minutes
- ✅ **Multi-Angle Analysis**: Comprehensive court coverage

### **For Developers**
- 🔧 **Hybrid Architecture**: Best of both worlds (speed + power)
- 📊 **Real-time Monitoring**: Track progress at every step
- 🎯 **Error Recovery**: Automatic retries and smart skipping
- 🔄 **Incremental Training**: Efficient model updates
- 🚀 **Scalable**: Handle unlimited concurrent games

---

## 🔧 Troubleshooting

### **Common Issues**

**Development Mode Not Working?**
```bash
# Check environment
cat .env | grep TRAINING_MODE  # Should be "local"

# Test individual scripts
python scripts/training/export_plays.py --game-id test-id
```

**Production Deployment Failing?**
```bash
# Check APIs are enabled
gcloud services list --enabled | grep -E "(functions|run|workflows)"

# Check permissions
gcloud auth list
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.