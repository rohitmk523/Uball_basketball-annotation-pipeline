#!/usr/bin/env python3
"""
Quick validation script - runs essential checks before workflow execution.

Usage:
    python scripts/validation/quick_check.py
"""

import os
import sys
from pathlib import Path
import requests
from google.auth import default
from google.cloud import aiplatform
import json

# Add project root to path and load environment
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env.hybrid")

def quick_validate():
    """Run quick essential validations."""
    print("🔍 Quick Validation Check...")
    print("-" * 40)
    
    errors = []
    
    # 1. Environment variables
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        errors.append("❌ GCP_PROJECT_ID not set")
    else:
        print(f"✅ Project ID: {project_id}")
    
    # 2. Authentication
    try:
        credentials, _ = default()
        # Create a proper request object
        import google.auth.transport.requests
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        print("✅ GCP Authentication: OK")
    except Exception as e:
        errors.append(f"❌ Auth failed: {e}")
        return errors
    
    # 3. Test Vertex AI API format
    try:
        region = "us-central1"
        url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/tuningJobs"
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{url}?pageSize=1", headers=headers)
        if response.status_code == 200:
            data = response.json()
            jobs = data.get('tuningJobs', [])
            if jobs:
                job = jobs[0]
                if 'tunedModel' in job and 'model' in job['tunedModel']:
                    print("✅ Vertex AI API format: tunedModel.model exists")
                else:
                    errors.append("❌ API format: tunedModel.model not found")
            print("✅ Vertex AI API: Accessible")
        else:
            errors.append(f"❌ Vertex AI API: {response.status_code}")
    except Exception as e:
        errors.append(f"❌ Vertex AI API test failed: {e}")
    
    # 4. Check workflow deployment
    try:
        result = os.popen(f"gcloud workflows describe hybrid-training-pipeline --location=us-central1 --format='value(revisionId)' 2>/dev/null").read().strip()
        if result:
            print(f"✅ Workflow deployed: revision {result}")
        else:
            errors.append("❌ Workflow not deployed")
    except Exception as e:
        errors.append(f"❌ Workflow check failed: {e}")
    
    # 5. Storage access
    try:
        from google.cloud import storage
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket("uball-training-data")
        list(bucket.list_blobs(max_results=1))
        print("✅ GCS Storage: Accessible")
    except Exception as e:
        errors.append(f"❌ Storage access failed: {e}")
    
    print("-" * 40)
    
    if errors:
        print("❌ VALIDATION FAILED!")
        for error in errors:
            print(f"  {error}")
        print("\n🛑 Fix errors before running workflow")
        return False
    else:
        print("✅ ALL QUICK CHECKS PASSED!")
        print("🚀 Ready to run workflow!")
        return True

if __name__ == "__main__":
    import sys
    success = quick_validate()
    if not success:
        sys.exit(1)