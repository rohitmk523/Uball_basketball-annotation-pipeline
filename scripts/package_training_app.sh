#!/bin/bash

# Package Basketball Custom Training Application for Vertex AI
# This script creates a Python package and uploads it to GCS for use with Custom Jobs

set -e

# Configuration
PROJECT_ID="refined-circuit-474617-s8"
BUCKET_NAME="uball-training-packages"
PACKAGE_NAME="basketball-custom-training"
VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏀 Basketball Custom Training Package Builder${NC}"
echo "================================================"

# Check if we're in the right directory
if [ ! -d "jobs/custom-training" ]; then
    echo -e "${RED}❌ Error: Must run from repository root directory${NC}"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo -e "${BLUE}📦 Step 1: Building Python package...${NC}"

# Navigate to the training job directory
cd jobs/custom-training

# Create source distribution
python setup.py sdist

# Get the package file name (setuptools uses underscores)
PACKAGE_FILE="basketball_custom_training-${VERSION}.tar.gz"
PACKAGE_PATH="dist/${PACKAGE_FILE}"

if [ ! -f "$PACKAGE_PATH" ]; then
    echo -e "${RED}❌ Error: Package file not found at $PACKAGE_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Package created: $PACKAGE_PATH${NC}"

echo -e "${BLUE}📤 Step 2: Uploading to Google Cloud Storage...${NC}"

# Create bucket if it doesn't exist
if ! gsutil ls "gs://${BUCKET_NAME}" > /dev/null 2>&1; then
    echo -e "${YELLOW}📁 Creating GCS bucket: gs://${BUCKET_NAME}${NC}"
    gsutil mb "gs://${BUCKET_NAME}"
else
    echo -e "${GREEN}✅ Bucket gs://${BUCKET_NAME} already exists${NC}"
fi

# Upload the package
echo -e "${BLUE}⬆️ Uploading package to GCS...${NC}"
gsutil cp "$PACKAGE_PATH" "gs://${BUCKET_NAME}/${PACKAGE_FILE}"

# Verify upload
if gsutil ls "gs://${BUCKET_NAME}/${PACKAGE_FILE}" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Package uploaded successfully!${NC}"
    echo -e "${GREEN}   Location: gs://${BUCKET_NAME}/${PACKAGE_FILE}${NC}"
else
    echo -e "${RED}❌ Error: Package upload failed${NC}"
    exit 1
fi

echo -e "${BLUE}🔧 Step 3: Package verification...${NC}"

# Show package contents
echo -e "${BLUE}📋 Package contents:${NC}"
tar -tzf "$PACKAGE_PATH" | head -10

# Show package info
echo -e "${BLUE}📊 Package information:${NC}"
echo "  Package name: $PACKAGE_NAME"
echo "  Version: $VERSION"
echo "  Size: $(du -h "$PACKAGE_PATH" | cut -f1)"
echo "  GCS URL: gs://${BUCKET_NAME}/${PACKAGE_FILE}"

echo -e "${BLUE}🧪 Step 4: Testing package installation...${NC}"

# Create a temporary virtual environment for testing
TEMP_VENV="/tmp/test_basketball_training"
python -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

# Install the package
pip install "$PACKAGE_PATH"

# Test import
if python -c "from trainer.task import BasketballIncrementalTrainer; print('✅ Package import successful')"; then
    echo -e "${GREEN}✅ Package installation and import test passed${NC}"
else
    echo -e "${RED}❌ Package installation or import test failed${NC}"
    deactivate
    rm -rf "$TEMP_VENV"
    exit 1
fi

# Cleanup test environment
deactivate
rm -rf "$TEMP_VENV"

# Return to repository root
cd ../..

echo -e "${GREEN}🎉 Package build and upload completed successfully!${NC}"
echo ""
echo -e "${BLUE}📋 Next Steps:${NC}"
echo "1. Update workflow YAML to use: gs://${BUCKET_NAME}/${PACKAGE_FILE}"
echo "2. Deploy updated workflow: gcloud workflows deploy hybrid-training-pipeline --source=workflows/hybrid-training-pipeline.yaml --location=us-central1"
echo "3. Test custom training: python cli.py train --game-id test-game-123"
echo ""
echo -e "${BLUE}🔗 Useful Commands:${NC}"
echo "  View package in GCS: gsutil ls -la gs://${BUCKET_NAME}/${PACKAGE_FILE}"
echo "  Download package: gsutil cp gs://${BUCKET_NAME}/${PACKAGE_FILE} ."
echo "  Delete package: gsutil rm gs://${BUCKET_NAME}/${PACKAGE_FILE}"

exit 0