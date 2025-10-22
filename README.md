# 🏀 Basketball AI Annotation System

**Production-ready AI system for automated basketball video analysis using fine-tuned Vertex AI (Gemini 2.5 Flash) with hybrid cloud architecture.**

## 🎯 Quick Overview

**Input:** Basketball game videos from GCS  
**Output:** Structured play annotations with 4-point line support  
**Performance:** Continuous learning with incremental training  
**Architecture:** Hybrid Cloud Functions + Cloud Run Jobs + Vertex AI

---

## 🏗️ System Architecture

### **High-Level Architecture**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client API    │───▶│  Cloud Workflow │───▶│   Cloud Run     │───▶│   Vertex AI     │
│   (FastAPI)     │    │  (Orchestrator) │    │   (Processing)  │    │  (ML Training)  │
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
  -d '{"game_id": "your-game-id"}'
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
- `POST /api/training/pipeline` - Start training for a game
- `GET /api/training/progress/{job_id}` - Real-time progress tracking
- `GET /api/training/status/{job_id}` - Job status and details
- `GET /api/training/config` - Current configuration

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