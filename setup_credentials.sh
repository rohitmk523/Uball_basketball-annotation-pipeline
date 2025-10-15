#!/bin/bash

# Setup script to configure credentials

echo "=================================="
echo "Basketball Annotation Setup"
echo "=================================="
echo ""

# Check if .env exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists!"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Edit .env manually."
        exit 0
    fi
fi

echo "📝 Creating .env file..."

cat > .env << 'EOF'
# ==================== APPLICATION ====================
ENVIRONMENT=development
LOG_LEVEL=INFO
API_PORT=8000
API_BASE_URL=http://localhost:8000

# ==================== SUPABASE ====================
SUPABASE_URL=https://mhbrsftxvxxtfgbajrlc.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1oYnJzZnR4dnh4dGZnYmFqcmxjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU2MzIwODQsImV4cCI6MjA3MTIwODA4NH0.zRS0B-dOYDC8rarpj3piWWE7pZJ7TqGamod2mPo-qPg
EOF

# Prompt for Supabase Service Key
echo ""
echo "🔑 Please provide your Supabase Service Role Key"
echo "   (Go to Supabase Dashboard → Settings → API → service_role)"
read -p "Supabase Service Key: " SUPABASE_SERVICE_KEY

cat >> .env << EOF
SUPABASE_SERVICE_KEY=${SUPABASE_SERVICE_KEY}

# ==================== GOOGLE CLOUD PLATFORM ====================
GCP_PROJECT_ID=refined-circuit-474617-s8
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json

# ==================== GCS BUCKETS ====================
GCS_VIDEO_BUCKET=uball-videos-production
GCS_TRAINING_BUCKET=uball-training-data
GCS_MODEL_BUCKET=uball-models

# ==================== VERTEX AI ====================
VERTEX_AI_BASE_MODEL=gemini-1.5-pro-002
VERTEX_AI_FINETUNED_ENDPOINT=
VERTEX_AI_TRAINING_PIPELINE=

# ==================== PROCESSING CONFIGURATION ====================
MAX_CONCURRENT_ANNOTATIONS=3
VIDEO_PROCESSING_TIMEOUT_SECONDS=1800
CLIP_EXTRACTION_PADDING_SECONDS=10
DEFAULT_CLIP_DURATION_SECONDS=20

# ==================== FEATURE FLAGS ====================
ENABLE_PLAYER_MATCHING=true
ENABLE_AUTO_RETRAINING=false

# ==================== MONITORING ====================
ENABLE_CLOUD_LOGGING=true
ENABLE_ERROR_REPORTING=true
SENTRY_DSN=
EOF

echo ""
echo "✅ .env file created!"
echo ""

# Verify service account key
if [ -f "service-account-key.json" ]; then
    echo "✅ Service account key found: service-account-key.json"
else
    echo "❌ Service account key NOT found!"
    echo "   Expected: service-account-key.json"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Test connection: python -c 'from app.core.database import get_supabase; get_supabase()'"
echo "2. Run API: uvicorn app.main:app --reload"
echo "3. Visit: http://localhost:8000/docs"
echo ""

