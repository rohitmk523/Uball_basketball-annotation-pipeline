#!/bin/bash

# Deploy Cloud Function for clip extraction

set -e

PROJECT_ID="refined-circuit-474617-s8"
REGION="us-central1"
FUNCTION_NAME="extract-clips-game"

echo "🚀 Deploying Cloud Function: $FUNCTION_NAME"
echo "📦 Project: $PROJECT_ID"
echo "🌍 Region: $REGION"

gcloud functions deploy $FUNCTION_NAME \
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
  --run-service-account=basketball-training-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --project=$PROJECT_ID \
  --execution-environment=gen2

echo "✅ Deployment complete!"
echo ""
echo "🔗 Function URL:"
gcloud functions describe $FUNCTION_NAME \
  --gen2 \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(serviceConfig.uri)"
