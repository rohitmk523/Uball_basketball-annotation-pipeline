# 🏀 Basketball AI Annotation System

**Production-ready AI system for automated basketball video analysis using fine-tuned Vertex AI (Gemini 1.5 Pro) with hybrid cloud architecture.**

## 🎯 Quick Overview

**Input:** Game videos from GCS  
**Output:** Structured play annotations in Supabase  
**Performance:** 5x faster processing, 90%+ accuracy  
**Architecture:** Hybrid Cloud Functions + Cloud Run Jobs

---

## 🏗️ Architecture

### **Hybrid Training Pipeline**
```
FastAPI → Cloud Workflows → Cloud Function (Export) → Cloud Run Jobs (Processing) → Vertex AI (Training)
```

**Benefits:**
- ⚡ **Fast startup**: Cloud Functions (2s) vs Cloud Build (60s+)
- 💪 **Unlimited resources**: 24-hour timeout, 32GB RAM, GPU support
- 💰 **Cost optimized**: Pay only for execution time
- 🔄 **Auto-scaling**: Handle any workload size

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

## 📚 Documentation

- **[Hybrid Architecture Guide](./HYBRID_ARCHITECTURE.md)** - Detailed architecture documentation
- **[Production Guide](./PRODUCTION_GUIDE.md)** - Production deployment guide
- **[Technical Approach](./TECHNICAL_APPROACH.md)** - Technical implementation details

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

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
