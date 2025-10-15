#!/bin/bash

# Deploy Google Cloud Workflows for training pipeline
# Usage: ./deploy_workflows.sh

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"refined-circuit-474617-s8"}
REGION=${GCP_LOCATION:-"us-central1"}
WORKFLOW_NAME="basketball-training-pipeline"
CLOUD_RUN_URL=${CLOUD_RUN_URL:-"https://your-service-name-hash-uc.a.run.app"}

echo "🔄 Deploying Google Cloud Workflows..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Workflow: $WORKFLOW_NAME"

# Enable required APIs
echo "📦 Enabling required APIs..."
gcloud services enable workflows.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID

# Deploy the workflow
echo "🚀 Deploying workflow..."
gcloud workflows deploy $WORKFLOW_NAME \
    --source=workflows/training-pipeline.yaml \
    --location=$REGION \
    --project=$PROJECT_ID

echo "✅ Workflow deployed successfully!"

# Create a Cloud Function trigger (optional)
cat > /tmp/trigger_function.py << EOF
import functions_framework
from google.cloud import workflows_v1
import json

@functions_framework.http
def trigger_training_pipeline(request):
    """HTTP Cloud Function to trigger training pipeline."""
    
    # Parse request
    request_json = request.get_json(silent=True)
    if not request_json or 'game_id' not in request_json:
        return {'error': 'game_id is required'}, 400
    
    game_id = request_json['game_id']
    
    # Initialize workflows client
    client = workflows_v1.WorkflowsClient()
    
    # Execute workflow
    execution = client.create_execution(
        parent=f"projects/$PROJECT_ID/locations/$REGION/workflows/$WORKFLOW_NAME",
        execution={
            "argument": json.dumps({
                "game_id": game_id,
                "api_url": "$CLOUD_RUN_URL"
            })
        }
    )
    
    return {
        'message': f'Training pipeline started for game {game_id}',
        'execution_name': execution.name,
        'workflow_url': f'https://console.cloud.google.com/workflows/workflow/$REGION/$WORKFLOW_NAME'
    }
EOF

echo "📄 Cloud Function trigger code generated at /tmp/trigger_function.py"

echo ""
echo "🎉 Deployment Complete!"
echo ""
echo "Next steps:"
echo "1. Update CLOUD_RUN_URL in the script with your actual Cloud Run URL"
echo "2. Trigger the workflow:"
echo "   gcloud workflows run $WORKFLOW_NAME \\"
echo "     --data='{\"game_id\":\"a3c9c041-6762-450a-8444-413767bb6428\",\"api_url\":\"$CLOUD_RUN_URL\"}' \\"
echo "     --location=$REGION"
echo ""
echo "3. Monitor in console:"
echo "   https://console.cloud.google.com/workflows/workflow/$REGION/$WORKFLOW_NAME"