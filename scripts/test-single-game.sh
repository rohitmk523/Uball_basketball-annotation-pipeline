#!/bin/bash

# Test script for single game extraction using Cloud Function

set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <game_id>"
  echo "Example: $0 23135de8-36ca-4882-bdf1-8796cd8caa8a"
  exit 1
fi

GAME_ID=$1
PROJECT_ID="refined-circuit-474617-s8"
REGION="us-central1"
FUNCTION_NAME="extract-clips-game"

echo "=========================================="
echo "🧪 Testing Single Game Extraction"
echo "=========================================="
echo ""
echo "Game ID: $GAME_ID"
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""

# Get function URL
echo "📡 Getting function URL..."
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
  --gen2 \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(serviceConfig.uri)" 2>/dev/null)

if [ -z "$FUNCTION_URL" ]; then
  echo "❌ Function not found! Please deploy it first:"
  echo "   cd functions/extract-clips-cf && bash deploy.sh"
  exit 1
fi

echo "✅ Function URL: $FUNCTION_URL"
echo ""

# Make request
echo "🚀 Sending request to function..."
echo ""

RESPONSE=$(curl -s -X POST "$FUNCTION_URL" \
  -H "Content-Type: application/json" \
  -d "{\"game_id\": \"$GAME_ID\"}")

echo "📥 Response:"
echo "$RESPONSE" | jq .

# Check if successful
SUCCESS=$(echo "$RESPONSE" | jq -r '.success')

if [ "$SUCCESS" == "true" ]; then
  echo ""
  echo "=========================================="
  echo "✅ Test PASSED!"
  echo "=========================================="
  echo ""

  # Extract key metrics
  CLIPS_EXTRACTED=$(echo "$RESPONSE" | jq -r '.clips_extracted')
  CLIPS_NEEDED=$(echo "$RESPONSE" | jq -r '.clips_needed')
  SUCCESS_RATE=$(echo "$RESPONSE" | jq -r '.success_rate')

  echo "📊 Results:"
  echo "  - Clips extracted: $CLIPS_EXTRACTED / $CLIPS_NEEDED"
  echo "  - Success rate: $SUCCESS_RATE%"
  echo ""

  # Show JSONL files
  TRAINING_FILE=$(echo "$RESPONSE" | jq -r '.training_file')
  VALIDATION_FILE=$(echo "$RESPONSE" | jq -r '.validation_file')

  echo "📁 Generated files:"
  echo "  - Training: $TRAINING_FILE"
  echo "  - Validation: $VALIDATION_FILE"
  echo ""

  # Verify files exist
  echo "🔍 Verifying files in GCS..."
  if gsutil ls "$TRAINING_FILE" >/dev/null 2>&1; then
    echo "  ✅ Training file exists"
  else
    echo "  ⚠️ Training file not found"
  fi

  if gsutil ls "$VALIDATION_FILE" >/dev/null 2>&1; then
    echo "  ✅ Validation file exists"
  else
    echo "  ⚠️ Validation file not found"
  fi

else
  echo ""
  echo "=========================================="
  echo "❌ Test FAILED!"
  echo "=========================================="
  echo ""

  ERROR=$(echo "$RESPONSE" | jq -r '.error')
  echo "Error: $ERROR"
  echo ""
  echo "Check logs:"
  echo "  gcloud functions logs read $FUNCTION_NAME --gen2 --region=$REGION --limit=100"
  exit 1
fi
