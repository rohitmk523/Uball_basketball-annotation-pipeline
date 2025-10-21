#!/usr/bin/env python3
"""
Comprehensive validation script for workflow parameters and API responses.

This script validates:
1. Environment variables and configuration
2. GCP authentication and permissions
3. Vertex AI API response formats
4. Workflow syntax and structure
5. Storage bucket access
6. Service account permissions

Usage:
    python scripts/validation/validate_workflow_params.py [--fix-issues]
"""

import os
import sys
import json
import yaml
import requests
from pathlib import Path
from google.auth import default
from google.cloud import aiplatform, storage
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv(project_root / ".env.hybrid")

class WorkflowValidator:
    """Comprehensive workflow validation."""
    
    def __init__(self, fix_issues=False):
        """Initialize validator."""
        self.fix_issues = fix_issues
        self.errors = []
        self.warnings = []
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.region = os.getenv("GCP_LOCATION", "us-central1")
        
        # Get credentials
        try:
            self.credentials, _ = default()
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            self.credentials.refresh(request)
        except Exception as e:
            self.errors.append(f"❌ GCP Authentication failed: {e}")
            self.credentials = None
    
    def validate_environment(self):
        """Validate environment variables."""
        logger.info("🔍 Validating environment variables...")
        
        required_vars = {
            "GCP_PROJECT_ID": self.project_id,
            "GCP_LOCATION": self.region,
            "SUPABASE_URL": os.getenv("SUPABASE_URL"),
            "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY")
        }
        
        for var_name, value in required_vars.items():
            if not value:
                self.errors.append(f"❌ Missing environment variable: {var_name}")
            else:
                logger.info(f"✅ {var_name}: {value[:20]}...")
        
        # Optional variables
        optional_vars = {
            "VERTEX_AI_FINETUNED_ENDPOINT": os.getenv("VERTEX_AI_FINETUNED_ENDPOINT"),
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        }
        
        for var_name, value in optional_vars.items():
            if value:
                logger.info(f"✅ {var_name}: {value[:50]}...")
            else:
                self.warnings.append(f"⚠️  Optional variable not set: {var_name}")
    
    def validate_gcp_auth(self):
        """Validate GCP authentication and permissions."""
        logger.info("🔍 Validating GCP authentication...")
        
        if not self.credentials:
            return
        
        try:
            # Test Vertex AI access
            aiplatform.init(project=self.project_id, location=self.region)
            
            # List models to test permissions
            models = aiplatform.Model.list(limit=1)
            logger.info("✅ Vertex AI access verified")
            
            # Test storage access
            storage_client = storage.Client(project=self.project_id)
            bucket = storage_client.bucket("uball-training-data")
            
            # Try to access bucket
            try:
                list(bucket.list_blobs(max_results=1))
                logger.info("✅ GCS bucket access verified")
            except Exception as e:
                self.errors.append(f"❌ GCS bucket access failed: {e}")
                
        except Exception as e:
            self.errors.append(f"❌ GCP service access failed: {e}")
    
    def validate_vertex_ai_api_format(self):
        """Validate Vertex AI API response formats by testing with existing data."""
        logger.info("🔍 Validating Vertex AI API response formats...")
        
        if not self.credentials:
            return
        
        try:
            # Get a recent tuning job to test API format
            url = f"https://{self.region}-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.region}/tuningJobs"
            headers = {
                "Authorization": f"Bearer {self.credentials.token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                tuning_jobs = data.get('tuningJobs', [])
                
                if tuning_jobs:
                    # Test the most recent completed job
                    for job in tuning_jobs:
                        if job.get('state') == 'JOB_STATE_SUCCEEDED':
                            self._validate_tuning_job_structure(job)
                            break
                    else:
                        self.warnings.append("⚠️  No completed tuning jobs found to validate API format")
                else:
                    self.warnings.append("⚠️  No tuning jobs found")
                    
                logger.info("✅ Vertex AI Tuning API access verified")
            else:
                self.errors.append(f"❌ Vertex AI API access failed: {response.status_code}")
                
        except Exception as e:
            self.errors.append(f"❌ Vertex AI API validation failed: {e}")
    
    def _validate_tuning_job_structure(self, job):
        """Validate the structure of a tuning job response."""
        logger.info("🔍 Validating tuning job response structure...")
        
        required_fields = ['name', 'state', 'tunedModel']
        for field in required_fields:
            if field not in job:
                self.errors.append(f"❌ Missing field in tuning job: {field}")
            
        # Check tunedModel structure
        tuned_model = job.get('tunedModel', {})
        if 'model' not in tuned_model:
            self.errors.append("❌ Missing 'model' field in tunedModel")
        else:
            model_name = tuned_model['model']
            logger.info(f"✅ tunedModel.model format: {model_name}")
            
        if 'endpoint' in tuned_model:
            endpoint_name = tuned_model['endpoint']
            logger.info(f"✅ tunedModel.endpoint format: {endpoint_name}")
        
        logger.info("✅ Tuning job structure validated")
    
    def validate_workflow_syntax(self):
        """Validate workflow YAML syntax."""
        logger.info("🔍 Validating workflow YAML syntax...")
        
        workflow_path = project_root / "workflows" / "hybrid-training-pipeline.yaml"
        
        if not workflow_path.exists():
            self.errors.append(f"❌ Workflow file not found: {workflow_path}")
            return
        
        try:
            with open(workflow_path, 'r') as f:
                workflow_data = yaml.safe_load(f)
            
            # Check main structure
            if 'main' not in workflow_data:
                self.errors.append("❌ Missing 'main' section in workflow")
            
            # Check critical steps exist
            main_steps = workflow_data.get('main', {}).get('steps', [])
            step_names = [list(step.keys())[0] if isinstance(step, dict) else str(step) for step in main_steps]
            
            critical_steps = [
                'init', 'create_tuning_job', 'wait_tuning_completion', 
                'deploy_to_persistent_endpoint', 'return_success'
            ]
            
            for step in critical_steps:
                if step not in step_names:
                    self.errors.append(f"❌ Missing critical workflow step: {step}")
            
            # Check subworkflows
            required_subworkflows = [
                'monitor_tuning_job', 'get_trained_games_count', 
                'deploy_model_to_endpoint', 'get_latest_trained_model'
            ]
            
            for subworkflow in required_subworkflows:
                if subworkflow not in workflow_data:
                    self.errors.append(f"❌ Missing subworkflow: {subworkflow}")
            
            logger.info("✅ Workflow YAML syntax validated")
            
        except yaml.YAMLError as e:
            self.errors.append(f"❌ YAML syntax error: {e}")
        except Exception as e:
            self.errors.append(f"❌ Workflow validation failed: {e}")
    
    def validate_workflow_field_references(self):
        """Validate that workflow uses correct API field names."""
        logger.info("🔍 Validating workflow field references...")
        
        workflow_path = project_root / "workflows" / "hybrid-training-pipeline.yaml"
        
        try:
            with open(workflow_path, 'r') as f:
                content = f.read()
            
            # Check for correct tunedModel field usage
            if 'tunedModel.name' in content:
                self.errors.append("❌ Workflow uses incorrect field: tunedModel.name (should be tunedModel.model)")
            
            if 'tunedModel.model' in content:
                logger.info("✅ Workflow uses correct field: tunedModel.model")
            
            if 'tuned_model' in content and 'tunedModel.model' in content:
                logger.info("✅ Workflow correctly references tuned_model variable")
            
            # Check for common syntax issues
            problematic_patterns = [
                ('tuning_status.body.tuned_model.name', 'Should use tunedModel.model'),
                ('${tuning_status.body.tunedModel.name}', 'Should use tunedModel.model')
            ]
            
            for pattern, issue in problematic_patterns:
                if pattern in content:
                    self.errors.append(f"❌ Workflow syntax issue: {issue}")
            
            logger.info("✅ Workflow field references validated")
            
        except Exception as e:
            self.errors.append(f"❌ Field reference validation failed: {e}")
    
    def validate_storage_structure(self):
        """Validate GCS bucket structure and permissions."""
        logger.info("🔍 Validating storage structure...")
        
        if not self.credentials:
            return
        
        try:
            storage_client = storage.Client(project=self.project_id)
            bucket = storage_client.bucket("uball-training-data")
            
            # Check required directories/files
            required_paths = [
                "datasets/",
                "metadata/"
            ]
            
            blobs = list(bucket.list_blobs(max_results=100))
            existing_paths = {blob.name for blob in blobs}
            
            for path in required_paths:
                path_exists = any(blob_path.startswith(path) for blob_path in existing_paths)
                if path_exists:
                    logger.info(f"✅ Storage path exists: {path}")
                else:
                    self.warnings.append(f"⚠️  Storage path missing (will be created): {path}")
            
            # Check games_count.json specifically
            try:
                metadata_blob = bucket.blob("metadata/games_count.json")
                if metadata_blob.exists():
                    content = json.loads(metadata_blob.download_as_text())
                    logger.info(f"✅ games_count.json exists: {content.get('total', 0)} games")
                else:
                    self.warnings.append("⚠️  games_count.json not found (will be created)")
            except Exception as e:
                self.warnings.append(f"⚠️  games_count.json validation failed: {e}")
                
        except Exception as e:
            self.errors.append(f"❌ Storage validation failed: {e}")
    
    def validate_current_models_and_endpoints(self):
        """Validate current models and endpoints."""
        logger.info("🔍 Validating current models and endpoints...")
        
        if not self.credentials:
            return
        
        try:
            # Check existing models
            models = aiplatform.Model.list(filter='display_name~"basketball"')
            logger.info(f"✅ Found {len(models)} basketball models")
            
            for model in models[:3]:  # Show first 3
                logger.info(f"  📦 {model.display_name} ({model.resource_name})")
            
            # Check existing endpoints
            endpoints = aiplatform.Endpoint.list()
            basketball_endpoints = [ep for ep in endpoints if 'basketball' in ep.display_name.lower()]
            
            logger.info(f"✅ Found {len(basketball_endpoints)} basketball endpoints")
            
            for endpoint in basketball_endpoints:
                logger.info(f"  📍 {endpoint.display_name} ({endpoint.resource_name})")
                
                # Check deployed models
                try:
                    deployed_models = endpoint.list_models()
                    logger.info(f"    🤖 Deployed models: {len(deployed_models)}")
                except Exception as e:
                    self.warnings.append(f"⚠️  Could not list models for endpoint {endpoint.display_name}: {e}")
            
        except Exception as e:
            self.errors.append(f"❌ Models/endpoints validation failed: {e}")
    
    def run_validation(self):
        """Run complete validation."""
        logger.info("🚀 Starting comprehensive workflow validation...")
        logger.info("="*60)
        
        # Run all validations
        validations = [
            self.validate_environment,
            self.validate_gcp_auth,
            self.validate_vertex_ai_api_format,
            self.validate_workflow_syntax,
            self.validate_workflow_field_references,
            self.validate_storage_structure,
            self.validate_current_models_and_endpoints
        ]
        
        for validation in validations:
            try:
                validation()
            except Exception as e:
                self.errors.append(f"❌ Validation error: {e}")
        
        # Print summary
        self._print_summary()
        
        return len(self.errors) == 0
    
    def _print_summary(self):
        """Print validation summary."""
        logger.info("\n" + "="*60)
        logger.info("📋 VALIDATION SUMMARY")
        logger.info("="*60)
        
        if self.errors:
            logger.error(f"❌ ERRORS FOUND ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  {error}")
        
        if self.warnings:
            logger.warning(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  {warning}")
        
        if not self.errors and not self.warnings:
            logger.info("✅ ALL VALIDATIONS PASSED!")
            logger.info("🚀 Workflow is ready to run!")
        elif not self.errors:
            logger.info("✅ NO CRITICAL ERRORS FOUND!")
            logger.info("⚠️  Some warnings present, but workflow should work")
        else:
            logger.error("❌ CRITICAL ERRORS FOUND!")
            logger.error("🛑 Fix errors before running workflow")
        
        logger.info("="*60)

def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate workflow parameters")
    parser.add_argument("--fix-issues", action="store_true", help="Attempt to fix found issues")
    
    args = parser.parse_args()
    
    try:
        validator = WorkflowValidator(fix_issues=args.fix_issues)
        success = validator.run_validation()
        
        if success:
            logger.info("\n🎉 Ready to run workflow!")
            logger.info("Command: gcloud workflows run hybrid-training-pipeline --data='{\"game_id\": \"your-game-id\"}' --location=us-central1")
        else:
            logger.error("\n🛑 Please fix errors before running workflow")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()