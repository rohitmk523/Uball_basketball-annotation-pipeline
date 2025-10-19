#!/bin/bash

# 🔐 Production Service Account Setup Script
# Creates a service account with all required permissions for hybrid basketball training architecture

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-refined-circuit-474617-s8}"
SERVICE_ACCOUNT_NAME="basketball-training-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="./credentials/service-account-key.json"

echo -e "${BLUE}🔐 Creating Production Service Account for Basketball Training${NC}"
echo -e "${YELLOW}Project: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}Service Account: ${SERVICE_ACCOUNT_EMAIL}${NC}"
echo

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Error: Not authenticated with gcloud${NC}"
    echo "Please run: gcloud auth login"
    exit 1
fi

# Set the project
echo -e "${BLUE}📋 Setting GCP project...${NC}"
gcloud config set project "$PROJECT_ID"

# Create credentials directory
mkdir -p credentials

# Create service account
echo -e "${BLUE}👤 Creating service account...${NC}"
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Service account already exists${NC}"
else
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="Basketball Training Production SA" \
        --description="Service account for hybrid basketball training pipeline with Cloud Functions and Cloud Run Jobs"
    echo -e "${GREEN}✅ Service account created${NC}"
fi

# Define required roles for hybrid architecture
REQUIRED_ROLES=(
    # Core compute roles
    "roles/run.admin"                    # Cloud Run services and jobs
    "roles/cloudfunctions.admin"         # Cloud Functions
    "roles/workflows.admin"              # Cloud Workflows
    
    # Storage and data
    "roles/storage.admin"                # GCS buckets
    "roles/storage.objectAdmin"          # GCS objects
    
    # AI/ML services
    "roles/aiplatform.admin"             # Vertex AI
    "roles/aiplatform.user"              # Vertex AI endpoints
    
    # Container and build
    "roles/cloudbuild.builds.editor"     # Cloud Build
    "roles/container.admin"              # Container Registry/Artifact Registry
    
    # Monitoring and logging
    "roles/logging.admin"                # Cloud Logging
    "roles/monitoring.admin"             # Cloud Monitoring
    "roles/cloudtrace.agent"             # Cloud Trace
    
    # Service management
    "roles/serviceusage.serviceUsageConsumer"  # API usage
    "roles/iam.serviceAccountUser"             # Service account usage
)

echo -e "${BLUE}🔑 Assigning IAM roles...${NC}"
for role in "${REQUIRED_ROLES[@]}"; do
    echo -e "  Adding role: ${role}"
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role="$role" \
        --quiet
done
echo -e "${GREEN}✅ All roles assigned${NC}"

# Generate and download service account key
echo -e "${BLUE}🔑 Generating service account key...${NC}"
if [ -f "$KEY_FILE" ]; then
    echo -e "${YELLOW}⚠️  Key file already exists. Creating backup...${NC}"
    mv "$KEY_FILE" "${KEY_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
fi

gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SERVICE_ACCOUNT_EMAIL"

echo -e "${GREEN}✅ Service account key saved to: ${KEY_FILE}${NC}"

# Set appropriate permissions on key file
chmod 600 "$KEY_FILE"

# Enable required APIs
echo -e "${BLUE}🔌 Enabling required APIs...${NC}"
REQUIRED_APIS=(
    "cloudfunctions.googleapis.com"
    "run.googleapis.com"
    "workflows.googleapis.com"
    "storage.googleapis.com"
    "aiplatform.googleapis.com"
    "cloudbuild.googleapis.com"
    "containerregistry.googleapis.com"
    "logging.googleapis.com"
    "monitoring.googleapis.com"
    "cloudtrace.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    echo -e "  Enabling: ${api}"
    gcloud services enable "$api" --quiet
done
echo -e "${GREEN}✅ All APIs enabled${NC}"

# Verify service account
echo -e "${BLUE}🔍 Verifying service account...${NC}"
gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL"

echo
echo -e "${GREEN}🎉 Service Account Setup Complete!${NC}"
echo
echo -e "${BLUE}📋 Next Steps:${NC}"
echo -e "1. ${YELLOW}Set environment variable:${NC}"
echo -e "   export GOOGLE_APPLICATION_CREDENTIALS=\"$(pwd)/${KEY_FILE}\""
echo
echo -e "2. ${YELLOW}Add to your .env.hybrid file:${NC}"
echo -e "   GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/${KEY_FILE}"
echo -e "   GCP_PROJECT_ID=${PROJECT_ID}"
echo
echo -e "3. ${YELLOW}Test authentication:${NC}"
echo -e "   gcloud auth activate-service-account --key-file=\"${KEY_FILE}\""
echo -e "   gcloud auth list"
echo
echo -e "4. ${YELLOW}Deploy hybrid infrastructure:${NC}"
echo -e "   ./scripts/deployment/deploy_hybrid_training.sh"
echo
echo -e "${BLUE}📁 Files created:${NC}"
echo -e "   - ${KEY_FILE}"
echo -e "   - ${KEY_FILE}.backup.* (if key already existed)"
echo
echo -e "${RED}⚠️  IMPORTANT: Keep the service account key secure and never commit it to git!${NC}"