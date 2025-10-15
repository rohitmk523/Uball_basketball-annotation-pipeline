#!/bin/bash

# Deploy Basketball Annotation API to Cloud Run

set -e  # Exit on error

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-refined-circuit-474617-s8}"
REGION="${GCP_LOCATION:-us-central1}"
SERVICE_NAME="basketball-annotation-api"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "====================================="
echo "Deploying to Cloud Run"
echo "====================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "====================================="

# Step 1: Build Docker image
echo ""
echo "📦 Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

# Step 2: Push to Google Container Registry
echo ""
echo "⬆️  Pushing image to GCR..."
docker push ${IMAGE_NAME}:latest

# Step 3: Deploy to Cloud Run
echo ""
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 1800 \
  --max-instances 5 \
  --min-instances 0 \
  --set-env-vars "ENVIRONMENT=production" \
  --set-secrets "SUPABASE_SERVICE_KEY=supabase-service-key:latest" \
  --set-secrets "GOOGLE_APPLICATION_CREDENTIALS=gcp-service-account:latest"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Get service URL:"
echo "gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'"

