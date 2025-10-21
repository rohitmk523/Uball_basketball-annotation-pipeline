#!/usr/bin/env python3
"""
Simple validation script - checks essential parameters without API calls.

Usage:
    python scripts/validation/simple_check.py
"""

import os
import sys
import yaml
from pathlib import Path

# Add project root to path and load environment
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env.hybrid")

def simple_validate():
    """Run simple essential validations."""
    print("🔍 Simple Validation Check...")
    print("-" * 40)
    
    errors = []
    warnings = []
    
    # 1. Environment variables
    required_vars = {
        "GCP_PROJECT_ID": os.getenv("GCP_PROJECT_ID"),
        "GCP_LOCATION": os.getenv("GCP_LOCATION"),
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY")
    }
    
    for var_name, value in required_vars.items():
        if not value:
            errors.append(f"❌ Missing: {var_name}")
        else:
            print(f"✅ {var_name}: {value[:20]}...")
    
    # 2. Optional variables
    optional_vars = {
        "VERTEX_AI_FINETUNED_ENDPOINT": os.getenv("VERTEX_AI_FINETUNED_ENDPOINT"),
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    }
    
    for var_name, value in optional_vars.items():
        if value:
            print(f"✅ {var_name}: {value[:30]}...")
        else:
            warnings.append(f"⚠️  Optional not set: {var_name}")
    
    # 3. Workflow file exists and syntax
    workflow_path = project_root / "workflows" / "hybrid-training-pipeline.yaml"
    if not workflow_path.exists():
        errors.append(f"❌ Workflow file not found: {workflow_path}")
    else:
        try:
            with open(workflow_path, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            # Check main structure
            if 'main' not in workflow_data:
                errors.append("❌ Missing 'main' section in workflow")
            else:
                print("✅ Workflow YAML: Valid syntax")
            
            # Check critical field usage
            with open(workflow_path, 'r') as f:
                content = f.read()
            
            if 'tunedModel.model' in content:
                print("✅ Workflow: Uses correct API field (tunedModel.model)")
            else:
                errors.append("❌ Workflow: Missing correct API field reference")
            
            if 'tunedModel.name' in content:
                errors.append("❌ Workflow: Uses incorrect field (tunedModel.name)")
            
        except yaml.YAMLError as e:
            errors.append(f"❌ YAML syntax error: {e}")
        except Exception as e:
            errors.append(f"❌ Workflow validation failed: {e}")
    
    # 4. Check if gcloud is available
    try:
        import subprocess
        result = subprocess.run(['gcloud', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ gcloud CLI: Available")
        else:
            warnings.append("⚠️  gcloud CLI: Not available")
    except FileNotFoundError:
        warnings.append("⚠️  gcloud CLI: Not installed")
    
    # 5. Check authentication status
    try:
        result = subprocess.run(['gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            account = result.stdout.strip().split('\n')[0]
            print(f"✅ GCP Auth: {account}")
        else:
            warnings.append("⚠️  GCP Auth: No active account")
    except Exception:
        warnings.append("⚠️  GCP Auth: Cannot check status")
    
    # 6. Check project setting
    try:
        result = subprocess.run(['gcloud', 'config', 'get-value', 'project'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            current_project = result.stdout.strip()
            expected_project = os.getenv("GCP_PROJECT_ID")
            if current_project == expected_project:
                print(f"✅ GCP Project: {current_project}")
            else:
                warnings.append(f"⚠️  Project mismatch: gcloud={current_project}, env={expected_project}")
    except Exception:
        warnings.append("⚠️  Cannot check gcloud project")
    
    print("-" * 40)
    
    # Print summary
    if errors:
        print("❌ VALIDATION FAILED!")
        for error in errors:
            print(f"  {error}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  {warning}")
    
    if not errors:
        print("✅ ESSENTIAL VALIDATIONS PASSED!")
        print("🚀 Workflow should be ready to run!")
        
        print("\n📋 Next steps:")
        print("1. Run workflow: gcloud workflows run hybrid-training-pipeline --data='{\"game_id\": \"test-123\"}' --location=us-central1")
        print("2. Monitor: https://console.cloud.google.com/workflows")
        
        return True
    else:
        print("\n🛑 Fix errors before running workflow")
        return False

if __name__ == "__main__":
    success = simple_validate()
    if not success:
        sys.exit(1)