#!/bin/bash
"""
Safe workflow runner - validates parameters before execution.

Usage:
    ./scripts/run_workflow_safe.sh <game_id>
    
Example:
    ./scripts/run_workflow_safe.sh test-game-123
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if game_id provided
if [ $# -eq 0 ]; then
    print_error "Game ID required!"
    echo "Usage: $0 <game_id>"
    echo "Example: $0 test-game-123"
    exit 1
fi

GAME_ID="$1"
LOCATION="us-central1"

print_status "🚀 Starting Safe Workflow Execution"
echo "===========================================" 

print_status "Game ID: $GAME_ID"
print_status "Location: $LOCATION"
echo

# Step 1: Environment check
print_status "Step 1: Checking environment..."
if [ -z "$GCP_PROJECT_ID" ]; then
    print_error "GCP_PROJECT_ID environment variable not set"
    exit 1
fi
print_success "Environment variables OK"

# Step 2: Authentication check
print_status "Step 2: Checking GCP authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
    print_error "No active GCP authentication found"
    print_status "Run: gcloud auth login"
    exit 1
fi
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
print_success "Authenticated as: $ACTIVE_ACCOUNT"

# Step 3: Project check
print_status "Step 3: Checking GCP project..."
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$GCP_PROJECT_ID" ]; then
    print_warning "Current project ($CURRENT_PROJECT) doesn't match GCP_PROJECT_ID ($GCP_PROJECT_ID)"
    print_status "Setting project to $GCP_PROJECT_ID..."
    gcloud config set project "$GCP_PROJECT_ID"
fi
print_success "Project: $GCP_PROJECT_ID"

# Step 4: Quick validation
print_status "Step 4: Running quick validation..."
if ! python scripts/validation/quick_check.py; then
    print_error "Quick validation failed!"
    echo
    print_status "Running comprehensive validation for details..."
    python scripts/validation/validate_workflow_params.py
    exit 1
fi

# Step 5: Workflow syntax check
print_status "Step 5: Checking workflow deployment..."
REVISION=$(gcloud workflows describe hybrid-training-pipeline --location=$LOCATION --format='value(revisionId)' 2>/dev/null || echo "")
if [ -z "$REVISION" ]; then
    print_error "Workflow not deployed!"
    print_status "Deploying workflow..."
    gcloud workflows deploy hybrid-training-pipeline --location=$LOCATION --source=workflows/hybrid-training-pipeline.yaml
    print_success "Workflow deployed"
else
    print_success "Workflow deployed (revision: $REVISION)"
fi

# Step 6: Pre-execution summary
echo
print_status "🎯 Pre-execution Summary:"
echo "  📋 Game ID: $GAME_ID"
echo "  🏗️  Project: $GCP_PROJECT_ID"
echo "  📍 Region: $LOCATION"
echo "  👤 Account: $ACTIVE_ACCOUNT"
echo "  🔄 Workflow: hybrid-training-pipeline ($REVISION)"
echo

# Step 7: Confirm execution
print_status "Ready to execute workflow!"
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Execution cancelled"
    exit 0
fi

# Step 8: Execute workflow
print_status "🚀 Executing workflow..."
echo "==========================================="

EXECUTION_DATA="{\"game_id\": \"$GAME_ID\"}"

if gcloud workflows run hybrid-training-pipeline --data="$EXECUTION_DATA" --location=$LOCATION; then
    print_success "Workflow execution started successfully!"
    echo
    print_status "📊 Monitor execution:"
    echo "  Console: https://console.cloud.google.com/workflows/workflow/$LOCATION/hybrid-training-pipeline"
    echo "  Logs: gcloud workflows executions list hybrid-training-pipeline --location=$LOCATION --limit=1"
else
    print_error "Workflow execution failed!"
    exit 1
fi

print_status "✨ Done!"