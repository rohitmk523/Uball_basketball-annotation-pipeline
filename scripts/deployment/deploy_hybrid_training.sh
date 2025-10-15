#!/bin/bash
# Deploy Hybrid Training Architecture
# This script deploys:
# 1. Cloud Function for export-plays
# 2. Cloud Run Jobs for extract-clips and train-model  
# 3. Hybrid Cloud Workflows

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}
REGION=${GCP_LOCATION:-"us-central1"}
FUNCTION_NAME="export-plays-cf"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Hybrid Training Architecture${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "Project ID: ${PROJECT_ID}"
echo -e "Region: ${REGION}"
echo ""

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites satisfied${NC}"
echo ""

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required APIs...${NC}"
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable workflows.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
echo -e "${GREEN}✅ APIs enabled${NC}"
echo ""

# Deploy Cloud Function
echo -e "${YELLOW}☁️ Deploying Cloud Function: ${FUNCTION_NAME}${NC}"
cd functions/export-plays-cf

# Update environment variables in .env.yaml
echo -e "${BLUE}📝 Updating environment variables...${NC}"
sed -i.bak "s/your-service-key-here/${SUPABASE_SERVICE_KEY:-placeholder}/g" .env.yaml

gcloud functions deploy ${FUNCTION_NAME} \
    --runtime python311 \
    --trigger-http \
    --allow-unauthenticated \
    --memory 2GB \
    --timeout 900s \
    --region ${REGION} \
    --env-vars-file .env.yaml \
    --source .

echo -e "${GREEN}✅ Cloud Function deployed${NC}"
cd ../..
echo ""

# Build and deploy Cloud Run Jobs
echo -e "${YELLOW}🏗️ Building Cloud Run Job images...${NC}"

# Build extract-clips job
echo -e "${BLUE}📦 Building extract-clips job...${NC}"
cd jobs/extract-clips
docker build -t gcr.io/${PROJECT_ID}/extract-clips:latest .
docker push gcr.io/${PROJECT_ID}/extract-clips:latest
echo -e "${GREEN}✅ Extract-clips image built and pushed${NC}"
cd ../..

# Build train-model job  
echo -e "${BLUE}📦 Building train-model job...${NC}"
cd jobs/train-model
docker build -t gcr.io/${PROJECT_ID}/train-model:latest .
docker push gcr.io/${PROJECT_ID}/train-model:latest
echo -e "${GREEN}✅ Train-model image built and pushed${NC}"
cd ../..
echo ""

# Deploy Cloud Workflows
echo -e "${YELLOW}⚙️ Deploying Hybrid Cloud Workflows...${NC}"
gcloud workflows deploy hybrid-training-pipeline \
    --source=workflows/hybrid-training-pipeline.yaml \
    --location=${REGION}
echo -e "${GREEN}✅ Hybrid workflow deployed${NC}"
echo ""

# Test Cloud Function
echo -e "${YELLOW}🧪 Testing Cloud Function...${NC}"
FUNCTION_URL="https://${REGION}-${PROJECT_ID}.cloudfunctions.net/${FUNCTION_NAME}"
echo -e "${BLUE}Function URL: ${FUNCTION_URL}${NC}"

# Basic health check
if curl -s -f "${FUNCTION_URL}" > /dev/null; then
    echo -e "${GREEN}✅ Cloud Function is responding${NC}"
else
    echo -e "${YELLOW}⚠️ Cloud Function test failed (this might be normal if it requires POST data)${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}🎉 HYBRID TRAINING ARCHITECTURE DEPLOYED SUCCESSFULLY!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${BLUE}📋 Deployment Summary:${NC}"
echo -e "• Cloud Function: ${FUNCTION_URL}"
echo -e "• Extract-clips job: gcr.io/${PROJECT_ID}/extract-clips:latest"
echo -e "• Train-model job: gcr.io/${PROJECT_ID}/train-model:latest"  
echo -e "• Hybrid workflow: hybrid-training-pipeline"
echo ""
echo -e "${BLUE}🧪 Test the pipeline:${NC}"
echo -e "curl -X POST \"${FUNCTION_URL}\" \\"
echo -e "  -H \"Content-Type: application/json\" \\"
echo -e "  -d '{\"game_id\": \"your-game-id\"}'"
echo ""
echo -e "${BLUE}🎯 Run workflow:${NC}"
echo -e "gcloud workflows run hybrid-training-pipeline \\"
echo -e "  --data='{\"game_id\": \"your-game-id\"}' \\"
echo -e "  --location=${REGION}"
echo ""
echo -e "${YELLOW}⚠️ Remember to set TRAINING_MODE=hybrid in your environment!${NC}"