#!/usr/bin/env python3
"""
S3 to GCS Migration Script for Basketball Game Videos

This script migrates game videos from S3 to GCS without quality loss.

Usage:
    python migrate_s3_to_gcs.py --s3-path "Games/09-22-2025/game1/" --game-id "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab"

Source: s3://uball-videos-production/Games/09-22-2025/game1/
Destination: gs://uball-videos-production/Games/d6ba2cbb-da84-4614-82fc-ff58ba12d5ab/
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

import boto3
from google.cloud import storage
from botocore.exceptions import ClientError, NoCredentialsError
from tqdm import tqdm


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class S3ToGCSMigrator:
    """Migrate basketball game videos from S3 to GCS."""
    
    def __init__(self, 
                 aws_access_key: str,
                 aws_secret_key: str, 
                 aws_bucket: str,
                 aws_region: str,
                 gcp_service_account_path: str,
                 gcs_bucket: str):
        """
        Initialize migrator with AWS and GCP credentials.
        
        Args:
            aws_access_key: AWS access key ID
            aws_secret_key: AWS secret access key
            aws_bucket: S3 bucket name
            aws_region: AWS region
            gcp_service_account_path: Path to GCP service account JSON
            gcs_bucket: GCS bucket name
        """
        self.aws_bucket = aws_bucket
        self.gcs_bucket = gcs_bucket
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            logger.info("✅ S3 client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {e}")
            raise
        
        # Initialize GCS client
        try:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = gcp_service_account_path
            self.gcs_client = storage.Client()
            self.gcs_bucket_obj = self.gcs_client.bucket(gcs_bucket)
            logger.info("✅ GCS client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize GCS client: {e}")
            raise
    
    def list_s3_objects(self, s3_prefix: str) -> List[str]:
        """
        List all objects in S3 bucket with given prefix.
        
        Args:
            s3_prefix: S3 prefix path (e.g., "Games/09-22-2025/game1/")
            
        Returns:
            List of S3 object keys
        """
        try:
            logger.info(f"🔍 Listing objects in s3://{self.aws_bucket}/{s3_prefix}")
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.aws_bucket, Prefix=s3_prefix)
            
            objects = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Skip directories (keys ending with /)
                        if not obj['Key'].endswith('/'):
                            objects.append(obj['Key'])
            
            logger.info(f"📊 Found {len(objects)} objects in S3")
            return objects
            
        except ClientError as e:
            logger.error(f"❌ Error listing S3 objects: {e}")
            raise
    
    def file_exists_in_gcs(self, gcs_path: str) -> bool:
        """
        Check if a file already exists in GCS.
        
        Args:
            gcs_path: GCS file path to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            blob = self.gcs_bucket_obj.blob(gcs_path)
            return blob.exists()
        except Exception as e:
            logger.warning(f"⚠️ Could not check if file exists in GCS: {e}")
            return False

    def migrate_file(self, s3_key: str, gcs_destination: str, progress_bar: tqdm = None, skip_existing: bool = True) -> dict:
        """
        Migrate a single file from S3 to GCS with progress tracking and smart skipping.
        
        Args:
            s3_key: S3 object key
            gcs_destination: GCS destination path
            progress_bar: tqdm progress bar instance
            skip_existing: Skip files that already exist in GCS
            
        Returns:
            Dictionary with migration result: {"success": bool, "skipped": bool, "error": str}
        """
        filename = s3_key.split('/')[-1]
        
        try:
            # Check if file already exists in GCS
            if skip_existing and self.file_exists_in_gcs(gcs_destination):
                if progress_bar:
                    progress_bar.set_description(f"⏭️ Skipping {filename} (already exists)")
                    progress_bar.update(1)
                
                logger.info(f"⏭️ Skipping {filename}: Already exists in GCS")
                return {"success": True, "skipped": True, "error": None}
            
            # Update progress bar description
            if progress_bar:
                progress_bar.set_description(f"📥 Downloading {filename}")
            
            logger.info(f"🔄 Migrating: s3://{self.aws_bucket}/{s3_key} → gs://{self.gcs_bucket}/{gcs_destination}")
            
            # Download from S3 to memory
            response = self.s3_client.get_object(Bucket=self.aws_bucket, Key=s3_key)
            file_content = response['Body'].read()
            
            # Get content type and metadata
            content_type = response.get('ContentType', 'application/octet-stream')
            content_length = len(file_content)
            
            # Update progress bar for upload
            if progress_bar:
                progress_bar.set_description(f"📤 Uploading {filename} ({content_length/1024/1024:.1f}MB)")
            
            logger.info(f"📋 File info: {content_length} bytes, type: {content_type}")
            
            # Upload to GCS
            blob = self.gcs_bucket_obj.blob(gcs_destination)
            blob.upload_from_string(file_content, content_type=content_type)
            
            # Update progress bar completion
            if progress_bar:
                progress_bar.set_description(f"✅ Completed {filename}")
                progress_bar.update(1)
            
            logger.info(f"✅ Successfully migrated: {gcs_destination}")
            return {"success": True, "skipped": False, "error": None}
            
        except Exception as e:
            if progress_bar:
                progress_bar.set_description(f"❌ Failed {filename}")
                progress_bar.update(1)
            logger.error(f"❌ Failed to migrate {s3_key}: {e}")
            return {"success": False, "skipped": False, "error": str(e)}
    
    def migrate_game(self, s3_path: str, game_id: str, skip_existing: bool = True) -> dict:
        """
        Migrate entire game from S3 to GCS.
        
        Args:
            s3_path: S3 path relative to bucket (e.g., "Games/09-22-2025/game1/")
            game_id: Target game ID for GCS (e.g., "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab")
            
        Returns:
            Migration results dictionary
        """
        logger.info(f"🚀 Starting migration for game: {game_id}")
        logger.info(f"📂 Source: s3://{self.aws_bucket}/{s3_path}")
        logger.info(f"📂 Destination: gs://{self.gcs_bucket}/Games/{game_id}/")
        
        # Ensure s3_path ends with /
        if not s3_path.endswith('/'):
            s3_path += '/'
        
        # List all files in S3
        s3_objects = self.list_s3_objects(s3_path)
        
        if not s3_objects:
            logger.warning(f"⚠️ No objects found in s3://{self.aws_bucket}/{s3_path}")
            return {
                'success': False,
                'error': 'No objects found in S3 path',
                'migrated_files': 0,
                'failed_files': 0
            }
        
        # Migrate each file with progress bar and smart skipping
        migrated_count = 0
        skipped_count = 0
        failed_count = 0
        migrated_files = []
        skipped_files = []
        failed_files = []
        
        # Create progress bar
        print(f"\n🚀 Starting migration of {len(s3_objects)} files...")
        print("⚡ Smart skip enabled: Files already in GCS will be skipped")
        with tqdm(total=len(s3_objects), 
                  desc="🔄 Initializing", 
                  unit="file",
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} files [{elapsed}<{remaining}]",
                  colour="green") as pbar:
            
            for s3_key in s3_objects:
                # Get relative path within the game directory
                relative_path = s3_key[len(s3_path):]
                
                # Skip if empty (shouldn't happen but safety check)
                if not relative_path:
                    continue
                
                # Build GCS destination path
                gcs_destination = f"Games/{game_id}/{relative_path}"
                
                # Migrate the file with progress tracking and skip logic
                result = self.migrate_file(s3_key, gcs_destination, pbar, skip_existing=skip_existing)
                
                if result["success"]:
                    if result["skipped"]:
                        skipped_count += 1
                        skipped_files.append({
                            'source': f"s3://{self.aws_bucket}/{s3_key}",
                            'destination': f"gs://{self.gcs_bucket}/{gcs_destination}",
                            'reason': 'already_exists'
                        })
                    else:
                        migrated_count += 1
                        migrated_files.append({
                            'source': f"s3://{self.aws_bucket}/{s3_key}",
                            'destination': f"gs://{self.gcs_bucket}/{gcs_destination}"
                        })
                else:
                    failed_count += 1
                    failed_files.append({
                        'file': s3_key,
                        'error': result["error"]
                    })
            
            # Final progress bar update
            pbar.set_description("🎉 Migration completed!")
        
        # Summary
        total_files = len(s3_objects)
        completed_files = migrated_count + skipped_count
        success_rate = (completed_files / total_files * 100) if total_files > 0 else 0
        
        logger.info(f"🎉 Migration completed!")
        logger.info(f"📊 Results: {migrated_count} migrated + {skipped_count} skipped = {completed_files}/{total_files} files processed ({success_rate:.1f}%)")
        
        if skipped_count > 0:
            logger.info(f"⏭️ Skipped {skipped_count} files (already exist in GCS)")
        
        if failed_files:
            logger.warning(f"⚠️ Failed files: {[f['file'] for f in failed_files]}")
        
        return {
            'success': failed_count == 0,
            'game_id': game_id,
            'source_path': f"s3://{self.aws_bucket}/{s3_path}",
            'destination_path': f"gs://{self.gcs_bucket}/Games/{game_id}/",
            'total_files': total_files,
            'migrated_files': migrated_count,
            'skipped_files': skipped_count,
            'failed_files': failed_count,
            'success_rate': success_rate,
            'migrated_list': migrated_files,
            'skipped_list': skipped_files,
            'failed_list': failed_files
        }


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description='Migrate basketball game videos from S3 to GCS')
    parser.add_argument('--s3-path', required=True, help='S3 path relative to bucket (e.g., "Games/09-22-2025/game1/")')
    parser.add_argument('--game-id', required=True, help='Target game ID for GCS (e.g., "d6ba2cbb-da84-4614-82fc-ff58ba12d5ab")')
    parser.add_argument('--aws-access-key', help='AWS access key (or use AWS_ACCESS_KEY_ID env var)')
    parser.add_argument('--aws-secret-key', help='AWS secret key (or use AWS_SECRET_ACCESS_KEY env var)')
    parser.add_argument('--aws-bucket', default='uball-videos-production', help='AWS S3 bucket name')
    parser.add_argument('--aws-region', default='us-east-1', help='AWS region')
    parser.add_argument('--gcp-service-account', help='Path to GCP service account JSON file')
    parser.add_argument('--gcs-bucket', default='uball-videos-production', help='GCS bucket name')
    parser.add_argument('--force', action='store_true', help='Force migration even if files already exist in GCS')
    
    args = parser.parse_args()
    
    # Get AWS credentials
    aws_access_key = args.aws_access_key or os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = args.aws_secret_key or os.getenv('AWS_SECRET_ACCESS_KEY')
    
    if not aws_access_key or not aws_secret_key:
        logger.error("❌ AWS credentials required. Provide via --aws-access-key/--aws-secret-key or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY env vars")
        sys.exit(1)
    
    # Get GCP service account path
    gcp_service_account = args.gcp_service_account or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not gcp_service_account:
        # Try default location
        default_path = '/Users/rohitkale/Cellstrat/GitHub_Repositories/Uball_basketball-annotation-pipeline/credentials/service-account-key.json'
        if os.path.exists(default_path):
            gcp_service_account = default_path
        else:
            logger.error("❌ GCP service account JSON required. Provide via --gcp-service-account or GOOGLE_APPLICATION_CREDENTIALS env var")
            sys.exit(1)
    
    if not os.path.exists(gcp_service_account):
        logger.error(f"❌ GCP service account file not found: {gcp_service_account}")
        sys.exit(1)
    
    try:
        # Initialize migrator
        migrator = S3ToGCSMigrator(
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key,
            aws_bucket=args.aws_bucket,
            aws_region=args.aws_region,
            gcp_service_account_path=gcp_service_account,
            gcs_bucket=args.gcs_bucket
        )
        
        # Perform migration
        skip_existing = not args.force  # If --force is used, don't skip existing files
        result = migrator.migrate_game(args.s3_path, args.game_id, skip_existing=skip_existing)
        
        # Print final result
        if result['success']:
            logger.info(f"🎉 Migration successful! Game {args.game_id} is ready for training.")
            print(f"\n✅ MIGRATION COMPLETE")
            print(f"Game ID: {result['game_id']}")
            print(f"Files migrated: {result['migrated_files']}/{result['total_files']}")
            print(f"Destination: {result['destination_path']}")
        else:
            logger.error("❌ Migration failed!")
            print(f"\n❌ MIGRATION FAILED")
            print(f"Failed files: {result['failed_files']}")
            if result.get('failed_list'):
                for failed_file in result['failed_list']:
                    print(f"  - {failed_file}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Migration failed with error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()