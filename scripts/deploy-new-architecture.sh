#!/bin/bash

# Complete deployment script for the new Cloud Functions architecture

set -e

PROJECT_ID="refined-circuit-474617-s8"
REGION="us-central1"

echo "=========================================="
echo "🚀 Basketball Training Pipeline V2"
echo "   Cloud Functions Architecture"
echo "=========================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Step 1: Deploy Cloud Function
echo "📦 Step 1: Deploying Cloud Function..."
echo "----------------------------------------"

cd functions/extract-clips-cf

echo "Deploying extract-clips-game function..."
gcloud functions deploy extract-clips-game \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=extract_clips_game \
  --trigger-http \
  --allow-unauthenticated \
  --memory=8GB \
  --timeout=3600s \
  --max-instances=40 \
  --env-vars-file=.env.yaml \
  --service-account=basketball-training-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --project=$PROJECT_ID

echo ""
echo "✅ Cloud Function deployed!"
echo ""

# Get function URL
FUNCTION_URL=$(gcloud functions describe extract-clips-game \
  --gen2 \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(serviceConfig.uri)")

echo "🔗 Function URL: $FUNCTION_URL"
echo ""

cd ../..

# Step 2: Deploy Workflow
echo "📦 Step 2: Deploying Workflow..."
echo "----------------------------------------"

echo "Deploying basketball-training-pipeline-v2..."
gcloud workflows deploy basketball-training-pipeline-v2 \
  --source=workflows/basketball-training-pipeline-v2.yaml \
  --location=$REGION \
  --service-account=basketball-training-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --project=$PROJECT_ID

echo ""
echo "✅ Workflow deployed!"
echo ""

# Step 3: Verification
echo "🔍 Step 3: Verification"
echo "----------------------------------------"

echo "Testing Cloud Function with sample request..."
echo ""

# Note: This would need a real game_id to test
echo "To test manually, run:"
echo ""
echo "curl -X POST $FUNCTION_URL \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"game_id\": \"YOUR_GAME_ID\"}'"
echo ""

echo "To run workflow:"
echo ""
echo "gcloud workflows run basketball-training-pipeline-v2 \\"
echo "  --data='{\"game_ids\": [\"game1\", \"game2\"]}' \\"
echo "  --location=$REGION"
echo ""

echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "1. Test the Cloud Function with a single game"
echo "2. Run the workflow with 2-3 games to validate"
echo "3. Scale up to 30-40 games"
echo ""
echo "Monitoring:"
echo "- Function logs: gcloud functions logs read extract-clips-game --gen2 --region=$REGION --limit=100"
echo "- Workflow logs: gcloud workflows executions list basketball-training-pipeline-v2 --location=$REGION"
echo ""
