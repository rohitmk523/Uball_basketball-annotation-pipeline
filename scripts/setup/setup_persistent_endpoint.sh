#!/bin/bash

# Setup persistent Vertex AI endpoint for basketball annotation
# This creates a single endpoint that will be reused for all model versions

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"refined-circuit-474617-s8"}
REGION=${GCP_LOCATION:-"us-central1"}
ENDPOINT_NAME="basketball-annotation-endpoint"

echo "🔄 Setting up persistent Vertex AI endpoint..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Endpoint: $ENDPOINT_NAME"

# Get or create the persistent endpoint
echo "📍 Getting persistent endpoint URL..."
ENDPOINT_URL=$(python scripts/training/deploy_model.py --get-endpoint-only)

echo "✅ Persistent endpoint ready!"
echo ""
echo "🎯 Add this to your .env file (ONE TIME ONLY):"
echo "$ENDPOINT_URL"
echo ""
echo "💡 Key Benefits:"
echo "✓ Same endpoint URL for all model versions"
echo "✓ API automatically uses latest trained model"
echo "✓ No need to update .env after each training"
echo "✓ Models are versioned automatically"
echo ""
echo "🚀 Now you can train models and they'll auto-deploy to this endpoint!"