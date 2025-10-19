# 🚀 Production Deployment Guide

## 📋 Prerequisites Checklist

Before deploying to production, ensure you have:

### **Google Cloud Setup**
- ✅ GCP Project: `refined-circuit-474617-s8` 
- ✅ Billing enabled
- ✅ APIs enabled:
  - **Vertex AI API** (model training)
  - **Cloud Storage API** (data storage)
  - **Cloud Run API** (FastAPI + Jobs)
  - **Cloud Functions API** (serverless functions)
  - **Cloud Workflows API** (orchestration)
  - **Cloud Build API** (container builds)
  - **Container Registry API** (image storage)
- ✅ Service Account with roles:
  - **Vertex AI Admin**
  - **Storage Admin** 
  - **Cloud Run Admin**
  - **Cloud Functions Developer**
  - **Workflows Admin**
  - **Cloud Build Editor**

### **Data Requirements**
- ✅ Basketball videos in GCS bucket: `uball-training-data`
- ✅ Video format: MP4, organized as `{game_id}/game3_{angle}.mp4`
- ✅ Supabase database with plays table
- ✅ At least 50+ annotated plays for initial training

### **Local Development**
- ✅ Python 3.11+
- ✅ Docker installed
- ✅ gcloud CLI authenticated
- ✅ ffmpeg installed

---

## 🛠️ Step-by-Step Production Setup

### **Step 1: Environment Configuration**

1. **Clone and setup repository:**
```bash
git clone <repository-url>
cd Uball_basketball-annotation-pipeline
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment variables:**
```bash
# For development mode
cp .env.dev .env

# For production/hybrid mode  
cp .env.hybrid .env
```

Edit `.env` with your production values:
```bash
# Training Mode (CRITICAL)
TRAINING_MODE=hybrid                    # local = dev, hybrid = production

# GCP Configuration
GCP_PROJECT_ID=refined-circuit-474617-s8
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# GCS Buckets
GCS_VIDEO_BUCKET=uball-videos-production
GCS_TRAINING_BUCKET=uball-training-data
GCS_MODEL_BUCKET=uball-models

# Supabase Configuration  
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-key

# Vertex AI
VERTEX_AI_BASE_MODEL=gemini-1.5-pro-002

# Training Configuration
TRAINING_WORKFLOW_NAME=hybrid-training-pipeline
TRAINING_WORKFLOW_LOCATION=us-central1
CLIP_EXTRACTION_PADDING_SECONDS=10

# Production Configuration
ENVIRONMENT=production
```

### **Step 2: Authenticate with Google Cloud**

```bash
# Authenticate with your personal account
gcloud auth login

# Set application default credentials
gcloud auth application-default login

# Verify authentication
gcloud auth list
gcloud config set project refined-circuit-474617-s8
```

### **Step 3: Test Local Setup**

```bash
# Test connection to all services
python test_connection.py

# Test training pipeline locally first
TRAINING_MODE=local uvicorn app.main:app --port 8000

# Test local training endpoint
curl -X POST "http://localhost:8000/api/training/pipeline" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test-game-id"}'
```

### **Step 4: Deploy Hybrid Infrastructure**

**🚀 One-Command Deployment**
```bash
# Set required environment variables
export GCP_PROJECT_ID="refined-circuit-474617-s8"
export SUPABASE_SERVICE_KEY="your-supabase-key"

# Deploy entire hybrid infrastructure
./scripts/deployment/deploy_hybrid_training.sh
```

**Manual Step-by-Step Deployment**

**4a. Deploy Cloud Function (Export Plays)**
```bash
cd functions/export-plays-cf

gcloud functions deploy export-plays-cf \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --memory 2GB \
  --timeout 900s \
  --region us-central1 \
  --set-env-vars SUPABASE_URL=$SUPABASE_URL,SUPABASE_SERVICE_KEY=$SUPABASE_SERVICE_KEY
```

**4b. Build and Deploy Cloud Run Jobs**
```bash
# Extract Clips Job
cd jobs/extract-clips
docker build -t gcr.io/$GCP_PROJECT_ID/extract-clips .
docker push gcr.io/$GCP_PROJECT_ID/extract-clips

gcloud run jobs create extract-clips-job \
  --image gcr.io/$GCP_PROJECT_ID/extract-clips \
  --region us-central1 \
  --memory 16Gi \
  --cpu 8 \
  --task-timeout 86400 \
  --max-retries 3

# Train Model Job  
cd ../train-model
docker build -t gcr.io/$GCP_PROJECT_ID/train-model .
docker push gcr.io/$GCP_PROJECT_ID/train-model

gcloud run jobs create train-model-job \
  --image gcr.io/$GCP_PROJECT_ID/train-model \
  --region us-central1 \
  --memory 8Gi \
  --cpu 4 \
  --task-timeout 86400 \
  --max-retries 3
```

**4c. Deploy Hybrid Workflow**
```bash
gcloud workflows deploy hybrid-training-pipeline \
  --source=workflows/hybrid-training-pipeline.yaml \
  --location=us-central1
```

### **Step 5: Deploy FastAPI Application**

**Option A: Local Development (with Hybrid Backend)**
```bash
# Run locally but use hybrid cloud infrastructure
TRAINING_MODE=hybrid uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test hybrid training
curl -X POST "http://localhost:8000/api/training/pipeline" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test-game-id"}'

# Monitor progress  
curl "http://localhost:8000/api/training/progress/{job_id}"
```

**Option B: Full Production Deployment to Cloud Run**
```bash
# Build and deploy FastAPI to Cloud Run
docker build -t gcr.io/refined-circuit-474617-s8/basketball-annotation .
docker push gcr.io/refined-circuit-474617-s8/basketball-annotation

gcloud run deploy basketball-annotation \
  --image gcr.io/refined-circuit-474617-s8/basketball-annotation \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10 \
  --set-env-vars TRAINING_MODE=hybrid,ENVIRONMENT=production,GCP_PROJECT_ID=refined-circuit-474617-s8
```

**Option C: Use Deployment Script**
```bash
# Deploy FastAPI with hybrid infrastructure
./scripts/deployment/deploy_to_cloud_run.sh
```

---

## 🎯 Production Usage

### **Training New Models (Hybrid Architecture)**

**Using FastAPI Endpoints (Recommended)**
```bash
# Trigger hybrid training pipeline via API
curl -X POST "https://basketball-annotation-xxx-uc.a.run.app/api/training/pipeline" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "new-game-uuid", "force_retrain": false}'

# Monitor real-time progress with video processing details
curl "https://basketball-annotation-xxx-uc.a.run.app/api/training/progress/{job_id}"

# Check detailed status
curl "https://basketball-annotation-xxx-uc.a.run.app/api/training/status/{job_id}"

# Get configuration info
curl "https://basketball-annotation-xxx-uc.a.run.app/api/training/config"
```

**Direct Workflow Execution**
```bash
# Trigger hybrid workflow directly
gcloud workflows run hybrid-training-pipeline \
  --data='{"game_id": "new-game-uuid"}' \
  --location us-central1

# Monitor workflow execution
gcloud workflows executions list \
  --workflow hybrid-training-pipeline \
  --location us-central1

# Get execution details
gcloud workflows executions describe EXECUTION_ID \
  --workflow hybrid-training-pipeline \
  --location us-central1
```

### **Annotating Videos**

Use the deployed API:

```bash
# Annotate a game
curl -X POST "https://basketball-annotation-xxx-uc.a.run.app/api/annotate" \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": "game-uuid",
    "angle": "LEFT",
    "force_reprocess": false
  }'

# Check job status
curl "https://basketball-annotation-xxx-uc.a.run.app/api/jobs/{job_id}"

# Get results
curl "https://basketball-annotation-xxx-uc.a.run.app/api/plays/game-uuid?angle=LEFT"
```

---

## 🔍 Monitoring & Maintenance

### **Key Metrics to Monitor**

1. **Performance Metrics:**
   - Clip extraction time per game
   - Cache hit rate (should be >80%)
   - Parallel processing efficiency
   - API response times

2. **Error Tracking:**
   - Failed video downloads
   - ffmpeg extraction errors
   - Model inference failures
   - GCS upload failures

3. **Cost Monitoring:**
   - Vertex AI endpoint usage
   - GCS storage costs
   - Cloud Run compute costs

### **Regular Maintenance**

**Weekly:**
- Monitor cache disk usage
- Review failed jobs logs
- Check model performance metrics

**Monthly:**
- Clean up old cached videos
- Review and optimize costs
- Update model with new training data

### **Troubleshooting Common Issues**

**1. "Hybrid workflow execution failed"**
```bash
# Check workflow deployment
gcloud workflows describe hybrid-training-pipeline --location=us-central1

# Check recent executions
gcloud workflows executions list --workflow=hybrid-training-pipeline --location=us-central1

# Get execution logs
gcloud workflows executions describe EXECUTION_ID --workflow=hybrid-training-pipeline --location=us-central1
```

**2. "Cloud Function timeout or error"**
```bash
# Check function logs
gcloud functions logs read export-plays-cf --region=us-central1 --limit=50

# Test function directly
curl -X POST "https://us-central1-refined-circuit-474617-s8.cloudfunctions.net/export-plays-cf" \
  -H "Content-Type: application/json" \
  -d '{"game_id": "test-id"}'

# Check function status
gcloud functions describe export-plays-cf --region=us-central1
```

**3. "Cloud Run Job failed"**
```bash
# Check job executions
gcloud run jobs executions list --job=extract-clips-job --region=us-central1
gcloud run jobs executions list --job=train-model-job --region=us-central1

# Get job logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=extract-clips-job" --limit=50

# Check job configuration
gcloud run jobs describe extract-clips-job --region=us-central1
```

**4. "FastAPI not connecting to hybrid backend"**
```bash
# Check environment variables
curl "http://localhost:8000/api/training/config"

# Verify authentication
gcloud auth list
gcloud auth application-default print-access-token

# Test local vs hybrid mode
TRAINING_MODE=local curl -X POST "http://localhost:8000/api/training/pipeline" ...
TRAINING_MODE=hybrid curl -X POST "http://localhost:8000/api/training/pipeline" ...
```

**5. "Video not found in GCS"**
```bash
# Check if video exists
gsutil ls gs://uball-training-data/{game_id}/

# Verify service account permissions
gcloud projects get-iam-policy refined-circuit-474617-s8
```

**6. "Docker build/push failures"**
```bash
# Authenticate Docker
gcloud auth configure-docker

# Enable required APIs
gcloud services enable containerregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Test Docker build
docker build -t test-image jobs/extract-clips/
```

---

## 📊 Performance Expectations

### **Hybrid Architecture Benefits**
- **⚡ 2s startup** vs 60s+ with Cloud Build
- **💪 24-hour timeout** vs 60-minute limit
- **🔄 Auto-scaling** from 0 to unlimited
- **💰 Pay-per-use** vs always-on costs
- **📊 Real-time monitoring** with progress tracking

### **Processing Performance**
| Component | Resource | Timeout | Throughput |
|-----------|----------|---------|------------|
| **Export Plays** | 2GB RAM | 15 min | 1000+ plays/min |
| **Extract Clips** | 16GB RAM, 8 vCPU | 24 hours | 100+ clips/hour |
| **Train Model** | 8GB RAM, 4 vCPU | 24 hours | Varies by data size |

### **Capacity Estimates**
- **Local Development**: 1-2 games sequentially
- **Hybrid Production**: 10+ concurrent games  
- **Auto-scaling**: Unlimited with GCP quotas

---

## 🚨 Production Checklist

### **Pre-Deployment**
- [ ] All APIs enabled in GCP console
- [ ] Service account permissions configured
- [ ] Environment variables set (`TRAINING_MODE=hybrid`)
- [ ] GCP authentication working (`gcloud auth list`)
- [ ] Docker authentication (`gcloud auth configure-docker`)

### **Infrastructure Deployment**
- [ ] Cloud Function deployed (`export-plays-cf`)
- [ ] Cloud Run Jobs created (`extract-clips-job`, `train-model-job`)  
- [ ] Hybrid workflow deployed (`hybrid-training-pipeline`)
- [ ] FastAPI deployed to Cloud Run (optional)

### **Testing & Validation**
- [ ] Local training works (`TRAINING_MODE=local`)
- [ ] Hybrid training works (`TRAINING_MODE=hybrid`)
- [ ] Function responds to HTTP requests
- [ ] Jobs execute successfully
- [ ] Workflow orchestrates all components
- [ ] Real-time progress monitoring works

### **Production Readiness**
- [ ] Monitoring dashboard setup
- [ ] Error alerting configured  
- [ ] Backup strategy in place
- [ ] Documentation updated
- [ ] Client training completed

---

## 🔧 Development vs Production

| Aspect | Development (`local`) | Production (`hybrid`) |
|--------|----------------------|----------------------|
| **Training Mode** | `TRAINING_MODE=local` | `TRAINING_MODE=hybrid` |
| **Architecture** | Python scripts | Cloud Function + Jobs |
| **Processing** | Sequential | Parallel (auto-scaling) |
| **Resources** | Local machine | 16GB RAM, 8 vCPU per job |
| **Timeout** | No limit | 24 hours per component |
| **Storage** | Local files | GCS buckets |
| **Monitoring** | Console logs | Real-time API + Cloud Logging |
| **Scaling** | Single instance | Auto-scaling (0 to ∞) |
| **Cost** | $0 | Pay-per-use ($10-50/training) |
| **Startup Time** | Instant | 2s (vs 60s+ Cloud Build) |

---

## 📞 Support & Next Steps

### **For Issues:**
1. **Check real-time status**: `curl "/api/training/progress/{job_id}"`
2. **Review Cloud Console logs** for detailed error messages
3. **Use troubleshooting section** for common issues above
4. **Test components individually** before full deployment

### **Getting Help:**
- **Documentation**: Check `HYBRID_ARCHITECTURE.md` for technical details
- **Logs**: Use `gcloud logging read` for detailed error analysis
- **Configuration**: Verify with `/api/training/config` endpoint

### **Next Steps (Advanced Features):**
- **Multi-region deployment** for global availability
- **GPU acceleration** for faster training
- **Preemptible instances** for cost optimization
- **Custom metrics & alerting** for production monitoring
- **Redis integration** for job persistence across restarts

---

## 🚀 Quick Start Summary

**Development:**
```bash
TRAINING_MODE=local uvicorn app.main:app --port 8000
curl -X POST "http://localhost:8000/api/training/pipeline" -d '{"game_id": "test"}'
```

**Production:**
```bash
./scripts/deployment/deploy_hybrid_training.sh
TRAINING_MODE=hybrid uvicorn app.main:app --port 8000  
curl -X POST "http://localhost:8000/api/training/pipeline" -d '{"game_id": "prod"}'
```

**🎉 You're ready for production!** 

The hybrid architecture gives you AWS Lambda + Step Functions equivalent on Google Cloud.