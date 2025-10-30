"""
Cloud Function to combine JSONL files from multiple games
"""
import json
from google.cloud import storage
from flask import jsonify


def combine_jsonl(request):
    """
    Combines JSONL training files from multiple games.
    
    Expects JSON body:
    {
        "game_ids": ["id1", "id2", ...],
        "execution_dir": "cumulative-execution-12345"
    }
    """
    try:
        request_json = request.get_json()
        game_ids = request_json.get('game_ids', [])
        execution_dir = request_json.get('execution_dir')
        
        if not game_ids or not execution_dir:
            return jsonify({"error": "Missing game_ids or execution_dir"}), 400
        
        print(f"🚀 Combining JSONL files for {len(game_ids)} games")
        print(f"Execution directory: {execution_dir}")
        
        # Initialize GCS client
        storage_client = storage.Client()
        bucket = storage_client.bucket('uball-training-data')
        
        training_lines = []
        validation_lines = []
        
        # Fetch and combine files from each game
        for game_id in game_ids:
            print(f"📂 Processing game: {game_id}")
            
            # Find training file
            training_prefix = f"games/{game_id}/video_training_"
            training_blobs = list(bucket.list_blobs(prefix=training_prefix))
            
            if training_blobs:
                # Get the most recent training file
                latest_training = sorted(training_blobs, key=lambda b: b.time_created)[-1]
                print(f"  ✅ Found training file: {latest_training.name}")
                content = latest_training.download_as_text()
                training_lines.extend(content.strip().split('\n'))
            else:
                print(f"  ⚠️ No training file found for {game_id}")
            
            # Find validation file  
            validation_prefix = f"games/{game_id}/video_validation_"
            validation_blobs = list(bucket.list_blobs(prefix=validation_prefix))
            
            if validation_blobs:
                latest_validation = sorted(validation_blobs, key=lambda b: b.time_created)[-1]
                print(f"  ✅ Found validation file: {latest_validation.name}")
                content = latest_validation.download_as_text()
                validation_lines.extend(content.strip().split('\n'))
            else:
                print(f"  ⚠️ No validation file found for {game_id}")
        
        # Upload combined files
        training_path = f"{execution_dir}/combined_training.jsonl"
        validation_path = f"{execution_dir}/combined_validation.jsonl"
        
        print(f"\n📤 Uploading combined files...")
        print(f"  Training examples: {len(training_lines)}")
        print(f"  Validation examples: {len(validation_lines)}")
        
        if training_lines:
            training_blob = bucket.blob(training_path)
            training_blob.upload_from_string('\n'.join(training_lines))
            print(f"  ✅ Uploaded: gs://uball-training-data/{training_path}")
        
        if validation_lines:
            validation_blob = bucket.blob(validation_path)
            validation_blob.upload_from_string('\n'.join(validation_lines))
            print(f"  ✅ Uploaded: gs://uball-training-data/{validation_path}")
        
        result = {
            "success": True,
            "games_processed": len(game_ids),
            "training_examples": len(training_lines),
            "validation_examples": len(validation_lines),
            "training_file": f"gs://uball-training-data/{training_path}",
            "validation_file": f"gs://uball-training-data/{validation_path}"
        }
        
        print(f"\n✅ Combination complete!")
        return jsonify(result), 200
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

