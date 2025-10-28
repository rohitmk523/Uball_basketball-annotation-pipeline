#!/usr/bin/env python3
"""
Merge training data from multiple games for cumulative training.

This script:
1. Takes a list of game_ids
2. Finds all training/validation JSONL files in GCS for those games
3. Merges them into cumulative training/validation files
4. Uploads to GCS for Vertex AI Tuning Jobs
"""

import sys
import json
import argparse
from datetime import datetime
from google.cloud import storage
from typing import List, Tuple

def merge_game_data(
    game_ids: List[str],
    project_id: str,
    bucket_name: str = "uball-training-data"
) -> Tuple[str, str]:
    """
    Merge training data from multiple games.
    
    Args:
        game_ids: List of game IDs to merge
        project_id: GCP project ID
        bucket_name: GCS bucket name
        
    Returns:
        Tuple of (training_file_uri, validation_file_uri)
    """
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    
    print(f"🔍 Merging data for {len(game_ids)} games: {game_ids}")
    
    # Collect all training and validation data
    all_training_data = []
    all_validation_data = []
    
    for game_id in game_ids:
        print(f"\n📂 Processing game: {game_id}")
        
        # Find training files for this game
        training_prefix = f"games/{game_id}/video_training_"
        validation_prefix = f"games/{game_id}/video_validation_"
        
        # Get latest training file
        training_blobs = list(bucket.list_blobs(prefix=training_prefix))
        if training_blobs:
            latest_training = sorted(training_blobs, key=lambda b: b.time_created, reverse=True)[0]
            print(f"  ✓ Training file: {latest_training.name}")
            
            # Download and parse
            content = latest_training.download_as_string().decode('utf-8')
            for line in content.strip().split('\n'):
                if line.strip():
                    all_training_data.append(json.loads(line))
        else:
            print(f"  ⚠️  No training files found for {game_id}")
        
        # Get latest validation file
        validation_blobs = list(bucket.list_blobs(prefix=validation_prefix))
        if validation_blobs:
            latest_validation = sorted(validation_blobs, key=lambda b: b.time_created, reverse=True)[0]
            print(f"  ✓ Validation file: {latest_validation.name}")
            
            # Download and parse
            content = latest_validation.download_as_string().decode('utf-8')
            for line in content.strip().split('\n'):
                if line.strip():
                    all_validation_data.append(json.loads(line))
        else:
            print(f"  ⚠️  No validation files found for {game_id}")
    
    print(f"\n📊 Total accumulated data:")
    print(f"  Training examples: {len(all_training_data)}")
    print(f"  Validation examples: {len(all_validation_data)}")
    
    # Create merged file names
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    games_str = "_".join(game_ids[:3])  # First 3 game IDs
    if len(game_ids) > 3:
        games_str += f"_plus{len(game_ids)-3}more"
    
    training_filename = f"cumulative/video_training_cumulative_{len(game_ids)}games_{timestamp}.jsonl"
    validation_filename = f"cumulative/video_validation_cumulative_{len(game_ids)}games_{timestamp}.jsonl"
    
    # Upload merged training data
    print(f"\n⬆️  Uploading merged files to GCS...")
    training_blob = bucket.blob(training_filename)
    training_content = '\n'.join(json.dumps(item) for item in all_training_data)
    training_blob.upload_from_string(training_content, content_type='application/jsonl')
    training_uri = f"gs://{bucket_name}/{training_filename}"
    print(f"  ✓ Training: {training_uri}")
    
    # Upload merged validation data
    validation_blob = bucket.blob(validation_filename)
    validation_content = '\n'.join(json.dumps(item) for item in all_validation_data)
    validation_blob.upload_from_string(validation_content, content_type='application/jsonl')
    validation_uri = f"gs://{bucket_name}/{validation_filename}"
    print(f"  ✓ Validation: {validation_uri}")
    
    # Save metadata
    metadata = {
        "game_ids": game_ids,
        "total_games": len(game_ids),
        "training_examples": len(all_training_data),
        "validation_examples": len(all_validation_data),
        "training_file": training_uri,
        "validation_file": validation_uri,
        "created_at": timestamp
    }
    
    metadata_filename = f"cumulative/metadata_cumulative_{len(game_ids)}games_{timestamp}.json"
    metadata_blob = bucket.blob(metadata_filename)
    metadata_blob.upload_from_string(json.dumps(metadata, indent=2), content_type='application/json')
    print(f"  ✓ Metadata: gs://{bucket_name}/{metadata_filename}")
    
    print(f"\n✅ Data merge complete!")
    
    return training_uri, validation_uri


def main():
    parser = argparse.ArgumentParser(
        description="Merge training data from multiple basketball games"
    )
    parser.add_argument(
        'game_ids',
        nargs='+',
        help='Game IDs to merge (space-separated)'
    )
    parser.add_argument(
        '--project-id',
        default='refined-circuit-474617-s8',
        help='GCP project ID'
    )
    parser.add_argument(
        '--bucket',
        default='uball-training-data',
        help='GCS bucket name'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🏀 Basketball Training Data Merger - Cumulative Training")
    print("=" * 80)
    
    training_uri, validation_uri = merge_game_data(
        game_ids=args.game_ids,
        project_id=args.project_id,
        bucket_name=args.bucket
    )
    
    print("\n" + "=" * 80)
    print("📋 Use these URIs for training:")
    print(f"  Training:   {training_uri}")
    print(f"  Validation: {validation_uri}")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

